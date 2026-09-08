#!/bin/bash
# Full scheduler-comparison campaign: runs every baseline scheduler across
# several seeds, then generates all review-panel plots from the results.
#
# Usage:
#   bash ns3-sim/scripts/run_all_schedulers.sh
#
# Assumes ns3-sim/scripts/ns3_setup.sh has already installed NS-3 and
# symlinked this project into its scratch/ directory.
set -euo pipefail

NS3_VERSION="3.41"
NS3_HOME="${NS3_HOME:-$HOME/ns3}"
NS3_DIR="${NS3_HOME}/ns-allinone-${NS3_VERSION}/ns-${NS3_VERSION}"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RESULTS_DIR="${PROJECT_ROOT}/ns3-sim/results"

SCHEDULERS=("rr" "fpq" "maxweight" "cag" "random")
SEEDS=(0 1 2 3 4)
SIM_TIME=300
SLOT_DURATION=0.1

mkdir -p "${RESULTS_DIR}"

echo "========================================"
echo " AoI DRL Scheduler -- Full Campaign"
echo " ${#SCHEDULERS[@]} schedulers x ${#SEEDS[@]} seeds"
echo "========================================"

for sched in "${SCHEDULERS[@]}"; do
    for seed in "${SEEDS[@]}"; do
        CSV_OUT="${RESULTS_DIR}/${sched}_seed${seed}.csv"
        echo "[RUN] scheduler=${sched} seed=${seed} -> ${CSV_OUT}"

        (cd "${NS3_DIR}" && ./ns3 run "scratch/aoi-scheduler/aoi-scheduler-sim \
            --scheduler=${sched} \
            --slotDuration=${SLOT_DURATION} \
            --simTime=${SIM_TIME} \
            --seed=${seed} \
            --enableNetAnim=false \
            --csvOutput=${CSV_OUT}")

        echo "[DONE] ${CSV_OUT} ($(wc -l < "${CSV_OUT}") rows)"
    done
done

# One more short run with NetAnim enabled, for the topology animation demo.
echo "[RUN] NetAnim topology capture (cag, seed=0, 30s)..."
(cd "${NS3_DIR}" && ./ns3 run "scratch/aoi-scheduler/aoi-scheduler-sim \
    --scheduler=cag --seed=0 --simTime=30 \
    --enableNetAnim=true \
    --csvOutput=${RESULTS_DIR}/cag_netanim.csv")

echo ""
echo "========================================"
echo " Generating analysis plots..."
echo "========================================"

cd "${PROJECT_ROOT}"
python3 ns3-sim/analysis/plot_scheduler_comparison.py "${RESULTS_DIR}"
for sched in "${SCHEDULERS[@]}"; do
    python3 ns3-sim/analysis/plot_aoi_sawtooth.py "${RESULTS_DIR}/${sched}_seed0.csv"
done
python3 ns3-sim/analysis/generate_flowmon_plots.py "${RESULTS_DIR}/flowmon-results.xml"
python3 ns3-sim/analysis/validate_against_contracts.py "${RESULTS_DIR}/rr_seed0.csv"

echo ""
echo "========================================"
echo " Campaign complete. All plots saved to ${RESULTS_DIR}"
echo "========================================"
