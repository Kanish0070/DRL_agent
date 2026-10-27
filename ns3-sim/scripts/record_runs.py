#!/usr/bin/env python3
"""Record ns-3 runs for the dashboard's replay mode (no --realtime, so each run takes seconds).

  python3 ns3-sim/scripts/record_runs.py --scenarios            # S0-S4 + demo timeline x rr/maxweight/cag/dqn
  python3 ns3-sim/scripts/record_runs.py --best-cases           # re-record the selected best-case runs
Outputs: ns3-sim/results/scenarios/<S>/<policy>.csv and ns3-sim/results/best_cases/<id>/<policy>.csv
"""
import argparse
import concurrent.futures as cf
import glob
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ART = ROOT / "deploy" / "artifacts"

# Scenario flags mirror ns3-sim/scripts/run_campaign.sh exactly (only simTime differs for the short recordings).
SCENARIOS = {
    "S0": "--txPower=20.0 --distanceScale=1.0",
    "S1": "--txPower=-5.0 --distanceScale=1.0",
    "S2": "--interferer=cochannel --intfStart=30 --intfStop=150 --intfRateMbps=2.0 --intfLossNode=3 --intfLoss=0.2",
    "S3": "--txPower=5.0 --mobileNode=3 --mobileSpeed=1.0",
    "S4": "--failNode=1 --failAt=60 --recoverAt=90",
}
DEMO_FLAGS = f"--scenarioFile={ROOT / 'ns3-sim' / 'scenarios' / 'demo.json'}"
HEURISTICS = ["rr", "maxweight", "cag"]


def find_binary():
    cands = []
    if os.environ.get("NS3_DIR"):
        cands.append(Path(os.environ["NS3_DIR"]))
    home = Path.home()
    cands += [Path(p) for p in glob.glob(str(home / "Downloads/ns-allinone-*/ns-3.*"))]
    cands += [Path(p) for p in glob.glob(str(home / "ns3/ns-allinone-*/ns-3.*"))]
    for c in cands:
        bins = sorted(glob.glob(str(c / "build/scratch/aoi-scheduler/ns3*-aoi-scheduler-sim-*")))
        if bins:
            return bins[0]
    sys.exit("ERROR: no built ns-3 simulator found. Set NS3_DIR=/path/to/ns-3.xx (built, with scratch/aoi-scheduler linked).")


def job(binary, out, scheduler, policy_id, flags, sim_time, seed, policy_file=None):
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [binary, "--enableNetAnim=false", f"--scheduler={scheduler}", f"--policyId={policy_id}",
           f"--seed={seed}", f"--csvOutput={out}"] + flags.split()
    if sim_time:
        cmd.append(f"--simTime={sim_time}")
    if policy_file:
        cmd.append(f"--policyFile={policy_file}")
    return cmd


def run_all(cmds, workers):
    t0 = time.time()
    def one(cmd):
        t = time.time()
        r = subprocess.run(cmd, capture_output=True, text=True)
        return cmd, r.returncode, time.time() - t
    ok = 0
    with cf.ThreadPoolExecutor(workers) as ex:
        for cmd, rc, dt in ex.map(one, cmds):
            tag = next(a for a in cmd if a.startswith("--csvOutput=")).split("=", 1)[1]
            print(f"  [{'ok' if rc == 0 else 'FAILED'}] {dt:5.1f}s  {Path(tag).relative_to(ROOT)}")
            ok += rc == 0
    print(f"{ok}/{len(cmds)} runs ok in {time.time() - t0:.1f}s wall")
    return ok == len(cmds)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenarios", action="store_true")
    ap.add_argument("--best-cases", action="store_true")
    ap.add_argument("--dqn-seed", type=int, default=1, help="DQN training seed (0-4) used in recordings")
    ap.add_argument("--eval-seed", type=int, default=100)
    ap.add_argument("--sim-time", type=float, default=120.0, help="seconds per scenario recording")
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 4)
    args = ap.parse_args()
    if not (args.scenarios or args.best_cases):
        ap.error("pass --scenarios and/or --best-cases")
    binary = find_binary()
    print("Simulator:", binary)
    cmds = []
    if args.scenarios:
        dq = f"dqn_seed{args.dqn_seed}"
        base = ROOT / "ns3-sim" / "results" / "scenarios"
        for sc, flags in {**SCENARIOS, "demo": DEMO_FLAGS}.items():
            st = None if sc == "demo" else args.sim_time
            for pol in HEURISTICS:
                cmds.append(job(binary, base / sc / f"{pol}.csv", pol, pol, flags, st, args.eval_seed))
            cmds.append(job(binary, base / sc / "dqn.csv", "dqn", dq, flags, st, args.eval_seed, ART / f"{dq}.txt"))
    if args.best_cases:
        js = ROOT / "results" / "ns3_campaign" / "summary" / "best_cases.json"
        cases = json.loads(js.read_text())["selected_cases"]
        base = ROOT / "ns3-sim" / "results" / "best_cases"
        for c in cases:
            flags = SCENARIOS[c["scenario"]]
            d = base / c["id"]
            dq = f"dqn_seed{c['dqn_seed']}"
            cmds.append(job(binary, d / "dqn.csv", "dqn", dq, flags, 300, c["eval_seed"], ART / f"{dq}.txt"))
            for pol in {c["best_heuristic"], "rr"}:
                cmds.append(job(binary, d / f"{pol}.csv", pol, pol, flags, 300, c["eval_seed"]))
    sys.exit(0 if run_all(cmds, args.workers) else 1)


if __name__ == "__main__":
    main()
