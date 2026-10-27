"""Interactive Demo & Replay Server (Task N5.1).

Serves the evaluation dashboard UI, streams replay runs from CSV logs,
and listens on UDP 9999 for live telemetry from ns-3 (N6 live hook).

Usage:
    python -m tools.demo_server --replay results/
    python -m tools.demo_server --live --port 8080
"""
import argparse
import collections
import csv
import http.server
import importlib.util
import json
import os
import re
from pathlib import Path
import socket
import socketserver
import subprocess
import sys
import threading
import urllib.parse
import time
import webbrowser


STATIC_DIR = Path(__file__).resolve().parent.parent / "dashboard" / "static"
SCENARIO_PATH = Path(__file__).resolve().parent.parent / "ns3-sim" / "scenarios" / "demo.json"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCENARIO_RUNS = PROJECT_ROOT / "ns3-sim" / "results" / "scenarios"    # <S>/<policy>.csv (record_runs.py --scenarios)
BEST_CASE_RUNS = PROJECT_ROOT / "ns3-sim" / "results" / "best_cases"  # <id>/<policy>.csv (record_runs.py --best-cases)
SUMMARY_JSON = PROJECT_ROOT / "results" / "ns3_campaign" / "summary" / "best_cases.json"
SAFE_NAME = re.compile(r"^[A-Za-z0-9_.-]+$")


class LiveTelemetryListener(threading.Thread):
    """Background UDP listener on port 9999 for real-time datagrams from ns-3."""

    def __init__(self, port: int = 9999):
        super().__init__(daemon=True)
        self.port = port
        self.latest_frame = None
        self.running = True
        self.seq = 0
        self.run_id = 0
        self.frames = collections.deque(maxlen=8000)  # (seq, frame); room for 3 parallel runs x 2000 slots
        self.lock = threading.Lock()

    def frames_since(self, since: int):
        with self.lock:
            out = [f for (q, f) in self.frames if q > since]
            return out, self.seq

    def reset(self):
        """Start a fresh run: drop buffered frames and bump run_id so browsers clear their state."""
        with self.lock:
            self.frames.clear()
            self.latest_frame = None
            self.run_id += 1

    def run(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.bind(("127.0.0.1", self.port))
            sock.settimeout(0.5)
            print(f"[demo_server] Live UDP listener bound on 127.0.0.1:{self.port}")
            while self.running:
                try:
                    data, _ = sock.recvfrom(4096)
                except socket.timeout:
                    continue
                try:
                    frame = json.loads(data.decode("utf-8"))
                except Exception:
                    continue
                with self.lock:
                    self.seq += 1
                    self.latest_frame = frame
                    self.frames.append((self.seq, frame))
        except Exception as e:
            print(f"[demo_server] UDP socket note: {e}")
        finally:
            sock.close()


def _load_recorder():
    spec = importlib.util.spec_from_file_location("record_runs", PROJECT_ROOT / "ns3-sim" / "scripts" / "record_runs.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class LiveRunner:
    """Starts / stops real-time ns-3 runs on request from the dashboard (whitelisted parameters only)."""
    MODES = ("compare", "rr", "maxweight", "cag", "dqn")

    def __init__(self, listener):
        self.listener = listener
        self.procs = []
        self.info = {"scenario": None, "mode": None, "dqn_seed": None, "started": None}
        self.lock = threading.Lock()
        self.rec = _load_recorder()

    def running(self):
        return any(p.poll() is None for p in self.procs)

    def status(self):
        return {"running": self.running(), "run_id": self.listener.run_id if self.listener else 0, **self.info}

    def stop(self):
        for p in self.procs:
            if p.poll() is None:
                p.terminate()
        for p in self.procs:
            try:
                p.wait(timeout=3)
            except subprocess.TimeoutExpired:
                p.kill()
        self.procs = []

    def start(self, scenario: str, mode: str, dqn_seed: int, eval_seed: int = 100):
        rec = self.rec
        if self.listener is None:
            raise ValueError("server was not started with --live")
        if scenario != "demo" and scenario not in rec.SCENARIOS:
            raise ValueError(f"unknown scenario {scenario!r}")
        if mode not in self.MODES:
            raise ValueError(f"unknown mode {mode!r}")
        if dqn_seed not in range(5):
            raise ValueError("dqn_seed must be 0-4")
        try:
            binary = rec.find_binary()
        except SystemExit as e:
            raise ValueError(str(e))
        with self.lock:
            self.stop()
            self.listener.reset()
            flags = rec.DEMO_FLAGS if scenario == "demo" else rec.SCENARIOS[scenario]
            flags += f" --realtime=true --liveUdpPort={self.listener.port}"
            sim_time = None if scenario == "demo" else 120
            out_dir = PROJECT_ROOT / "ns3-sim" / "results" / "live"
            pols = ["rr", "maxweight", "cag", "dqn"] if mode == "compare" else [mode]
            for pol in pols:
                pid = f"dqn_seed{dqn_seed}" if pol == "dqn" else pol
                pfile = rec.ART / f"{pid}.txt" if pol == "dqn" else None
                cmd = rec.job(binary, out_dir / f"{pid}.csv", pol, pid, flags, sim_time, eval_seed, pfile)
                self.procs.append(subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
            self.info = {"scenario": scenario, "mode": mode, "dqn_seed": dqn_seed, "started": time.time()}
        return self.status()


class DemoHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    """Custom HTTP handler serving dashboard and REST APIs."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass

    def do_POST(self):
        route = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(route.query)
        runner = getattr(self.server, "runner", None)
        if runner is None:
            return self._json({"error": "server not started with --live"}, 400)
        if route.path == "/api/live/start":
            try:
                st = runner.start(q.get("scenario", ["demo"])[0], q.get("mode", ["compare"])[0],
                                  int(q.get("seed", ["1"])[0]))
            except (ValueError, OSError) as e:
                return self._json({"error": str(e)}, 400)
            return self._json(st)
        if route.path == "/api/live/stop":
            runner.stop()
            return self._json(runner.status())
        return self._json({"error": "not found"}, 404)

    def _run_set(self, base: Path, name: str):
        """All recorded policies of one scenario / best case: {policy: [frames]}."""
        if not SAFE_NAME.match(name or ""):
            return None
        d = base / name
        if not d.is_dir():
            return None
        return {p.stem: load_replay_csv(p) for p in sorted(d.glob("*.csv"))}

    def do_GET(self):
        route = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(route.query)
        if route.path == "/api/sets":
            sc = sorted(p.name for p in SCENARIO_RUNS.iterdir() if p.is_dir()) if SCENARIO_RUNS.is_dir() else []
            bc = sorted(p.name for p in BEST_CASE_RUNS.iterdir() if p.is_dir()) if BEST_CASE_RUNS.is_dir() else []
            return self._json({"scenarios": sc, "best_cases": bc})
        if route.path == "/api/set":
            kind = q.get("kind", ["scenario"])[0]
            base = BEST_CASE_RUNS if kind == "best" else SCENARIO_RUNS
            runs = self._run_set(base, q.get("name", [""])[0])
            if runs is None:
                return self._json({"error": "not recorded - run: python3 ns3-sim/scripts/record_runs.py --scenarios --best-cases"}, 404)
            return self._json({"runs": runs})
        if route.path == "/api/live/status":
            runner = getattr(self.server, "runner", None)
            return self._json(runner.status() if runner else {"running": False, "error": "server not started with --live"})
        if route.path == "/api/summary":
            if not SUMMARY_JSON.exists():
                return self._json({"error": "run: python3 ns3-sim/analysis/find_best_cases.py"}, 404)
            return self._json(json.loads(SUMMARY_JSON.read_text(encoding="utf-8")))

        if self.path == "/" or self.path == "/index.html":
            self.path = "/index.html"
            return super().do_GET()

        if self.path.startswith("/api/scenario"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            if SCENARIO_PATH.exists():
                with open(SCENARIO_PATH, "r", encoding="utf-8") as f:
                    self.wfile.write(f.read().encode("utf-8"))
            else:
                self.wfile.write(json.dumps({"error": "Scenario not found"}).encode("utf-8"))
            return

        if self.path.startswith("/api/status"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            status = {
                "server": "AoI DRL Scheduler Demo Server",
                "version": "1.0",
                "static_dir": str(STATIC_DIR),
                "scenario_file": str(SCENARIO_PATH),
                "live_telemetry_active": hasattr(self.server, "listener") and self.server.listener is not None,
            }
            self.wfile.write(json.dumps(status).encode("utf-8"))
            return

        if self.path.startswith("/api/frames"):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            since = int(q.get("since", ["0"])[0])
            listener = getattr(self.server, "listener", None)
            if listener is None:
                return self._json({"frames": [], "next": 0, "live": False})
            frames, nxt = listener.frames_since(since)
            return self._json({"frames": frames, "next": nxt, "live": True, "run_id": listener.run_id})

        if self.path.startswith("/api/replays"):
            d = Path(self.server.replay_dir)
            files = sorted(p.name for p in d.rglob("*.csv")) if d.is_dir() else []
            return self._json({"dir": str(d), "files": files})

        if self.path.startswith("/api/replay"):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            name = q.get("file", [""])[0]
            d = Path(self.server.replay_dir).resolve()
            target = next((p for p in d.rglob("*.csv") if p.name == name), None)
            if target is None:
                return self._json({"error": "not found"}, 404)
            return self._json({"file": name, "frames": load_replay_csv(target)})

        if self.path.startswith("/api/live_frame"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            frame = self.server.listener.latest_frame if getattr(self.server, "listener", None) else None
            self.wfile.write(json.dumps(frame or {}).encode("utf-8"))
            return

        return super().do_GET()


def load_replay_csv(path: Path):
    """Convert a scheduler SLOT_LOG CSV into the same frame dicts ns-3 streams live."""
    frames = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                frames.append({
                    "slot_id": int(row["slot_id"]),
                    "timestamp": float(row["timestamp_pi"]),
                    "policy_id": row["policy_id"],
                    "granted": int(row["action_granted_node"]),
                    "shield": int(row["shield_fired"]),
                    "delivered": int(row["delivered_node"]),
                    "delivered_age_us": float(row.get("delivered_age_us") or 0),
                    "aoi": [float(row[f"aoi_n{i}"]) for i in range(1, 5)],
                    "rssi": [float(row[f"rssi_n{i}"]) for i in range(1, 5)],
                })
            except (KeyError, ValueError):
                continue
    return frames


def run_server(port: int = 8000, replay_dir: str = "results", live: bool = False,
               open_browser: bool = False, udp_port: int = 9999, open_query: str = ""):
    listener = None
    if live:
        listener = LiveTelemetryListener(port=udp_port)
        listener.start()

    class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
        daemon_threads = True

    server = ThreadedHTTPServer(("127.0.0.1", port), DemoHTTPRequestHandler)   # loopback only: the page can start ns-3
    server.listener = listener
    server.runner = LiveRunner(listener) if listener else None
    server.replay_dir = replay_dir

    url = f"http://localhost:{port}/"
    open_url = url + (open_query or ("?source=live" if live else ""))
    print(f"\n========================================================")
    print(f"  AoI DRL Scheduler Evaluation Dashboard Server")
    print(f"  Running at: {url}")
    print(f"  Mode: {'LIVE (UDP 9999 active)' if live else 'REPLAY (Self-contained)'}")
    print(f"  Replay Directory: {replay_dir}")
    print(f"  Press Ctrl+C to stop.")
    print(f"========================================================\n")

    if open_browser:
        threading.Timer(0.5, lambda: webbrowser.open(open_url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[demo_server] Shutting down...")
    finally:
        if server.runner:
            server.runner.stop()
        if listener:
            listener.running = False
        server.server_close()


def main():
    parser = argparse.ArgumentParser(description="AoI DRL Scheduler Demo & Replay Server (N5.1)")
    parser.add_argument("--port", type=int, default=8000, help="Web server port (default 8000)")
    parser.add_argument("--replay", default="results", help="Directory of recorded CSV runs")
    parser.add_argument("--udp-port", type=int, default=9999, help="UDP port for live ns-3 telemetry")
    parser.add_argument("--live", action="store_true", help="Enable UDP listener for live ns-3 datagrams")
    parser.add_argument("--open-query", default="", help="query string for the browser URL, e.g. '?source=live&compare=1'")
    parser.add_argument("--open-browser", action="store_true", help="Open browser on startup")
    args = parser.parse_args()

    run_server(port=args.port, replay_dir=args.replay, live=args.live,
               open_browser=args.open_browser, udp_port=args.udp_port, open_query=args.open_query)


if __name__ == "__main__":
    main()
