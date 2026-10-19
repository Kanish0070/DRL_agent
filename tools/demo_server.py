"""Interactive Demo & Replay Server (Task N5.1).

Serves the evaluation dashboard UI, streams replay runs from CSV logs,
and listens on UDP 9999 for live telemetry from ns-3 (N6 live hook).

Usage:
    python -m tools.demo_server --replay results/
    python -m tools.demo_server --live --port 8080
"""
import argparse
import http.server
import json
import os
from pathlib import Path
import socket
import socketserver
import sys
import threading
import time
import webbrowser


STATIC_DIR = Path(__file__).resolve().parent.parent / "dashboard" / "static"
SCENARIO_PATH = Path(__file__).resolve().parent.parent / "ns3-sim" / "scenarios" / "demo.json"


class LiveTelemetryListener(threading.Thread):
    """Background UDP listener on port 9999 for real-time datagrams from ns-3."""

    def __init__(self, port: int = 9999):
        super().__init__(daemon=True)
        self.port = port
        self.latest_frame = None
        self.running = True

    def run(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.bind(("127.0.0.1", self.port))
            print(f"[demo_server] Live UDP listener bound on 127.0.0.1:{self.port}")
            while self.running:
                data, _ = sock.recvfrom(4096)
                try:
                    self.latest_frame = json.loads(data.decode("utf-8"))
                except Exception:
                    pass
        except Exception as e:
            print(f"[demo_server] UDP socket note: {e}")
        finally:
            sock.close()


class DemoHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    """Custom HTTP handler serving dashboard and REST APIs."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def do_GET(self):
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

        if self.path.startswith("/api/live_frame"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            frame = self.server.listener.latest_frame if getattr(self.server, "listener", None) else None
            self.wfile.write(json.dumps(frame or {}).encode("utf-8"))
            return

        return super().do_GET()


def run_server(port: int = 8000, replay_dir: str = "results", live: bool = False, open_browser: bool = False):
    listener = None
    if live:
        listener = LiveTelemetryListener(port=9999)
        listener.start()

    class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
        daemon_threads = True

    server = ThreadedHTTPServer(("0.0.0.0", port), DemoHTTPRequestHandler)
    server.listener = listener

    url = f"http://localhost:{port}/"
    print(f"\n========================================================")
    print(f"  AoI DRL Scheduler Evaluation Dashboard Server")
    print(f"  Running at: {url}")
    print(f"  Mode: {'LIVE (UDP 9999 active)' if live else 'REPLAY (Self-contained)'}")
    print(f"  Replay Directory: {replay_dir}")
    print(f"  Press Ctrl+C to stop.")
    print(f"========================================================\n")

    if open_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[demo_server] Shutting down...")
    finally:
        if listener:
            listener.running = False
        server.server_close()


def main():
    parser = argparse.ArgumentParser(description="AoI DRL Scheduler Demo & Replay Server (N5.1)")
    parser.add_argument("--port", type=int, default=8000, help="Web server port (default 8000)")
    parser.add_argument("--replay", default="results", help="Directory of recorded CSV runs")
    parser.add_argument("--live", action="store_true", help="Enable UDP listener for live ns-3 datagrams")
    parser.add_argument("--open-browser", action="store_true", help="Open browser on startup")
    args = parser.parse_args()

    run_server(port=args.port, replay_dir=args.replay, live=args.live, open_browser=args.open_browser)


if __name__ == "__main__":
    main()
