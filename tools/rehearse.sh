#!/usr/bin/env bash
# One command to get demo-ready: records every scenario + best-case run (about 15 s), rebuilds the
# best-case analysis, then prints how to start the demo. Safe to re-run.
#
#   bash tools/rehearse.sh                 # record + analyse
#   bash tools/rehearse.sh --start         # ... then start the replay dashboard (no live ns-3)
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"
DQN_SEED="${DQN_SEED:-1}"

echo "[1/3] Best-case analysis from the 1000-run campaign..."
python3 ns3-sim/analysis/find_best_cases.py > /dev/null
echo "[2/3] Recording S0-S4 + demo timeline (rr / max-weight / cag / dqn_seed${DQN_SEED})..."
python3 ns3-sim/scripts/record_runs.py --scenarios --dqn-seed "${DQN_SEED}" | tail -1
echo "[3/3] Re-recording the selected best-case runs..."
python3 ns3-sim/scripts/record_runs.py --best-cases | tail -1

cat <<EOT

Ready. Start the demo:
  bash tools/run_live_demo.sh --compare     # live: RR | Max-Weight | CAG | DQN as real-time ns-3 runs (120 s)
  python3 tools/demo_server.py --open-browser --live   # offline replay of the recordings (no ns-3 running)
EOT
[ "${1:-}" == "--start" ] && exec python3 tools/demo_server.py --live --open-browser --open-query "?scenario=demo&compare=1"
exit 0
