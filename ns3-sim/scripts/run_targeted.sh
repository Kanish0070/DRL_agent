#!/usr/bin/env bash
# Targeted scenarios: DQN's niche (lossy links), fresh eval seeds 500-519 that were not used to choose them.
# T1 = weak links (S1 settings), T2 = training-level loss (S5 settings), T3 = far nodes (distance pilot S10 settings).
# Writes to results/ns3_targeted/ only; the main campaign is untouched.
set -euo pipefail
NS3_DIR="${NS3_DIR:-$(ls -d "$HOME"/Downloads/ns-allinone-*/ns-3.* 2>/dev/null | tail -n1 || true)}"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ROOT="${RESULTS_ROOT:-${PROJECT_ROOT}/results/ns3_targeted}"
ART="${PROJECT_ROOT}/deploy/artifacts"
N_CORES="${N_CORES:-$(nproc 2>/dev/null || echo 4)}"
BASE="--slotDuration=0.1 --simTime=300"
declare -A SC=(
    [T1]="--txPower=-5.0 --distanceScale=1.0"
    [T2]="--txPower=-7.0 --distanceScale=1.0"
    [T3]="--txPower=20 --distanceScale=6"
)
JOB="$(mktemp)"; trap 'rm -f "$JOB"' EXIT
for sc in T1 T2 T3; do
    for s in $(seq 500 519); do
        for pol in cag fpq rr; do
            o="$ROOT/$sc/$pol/seed$s"; mkdir -p "$o"
            echo "--scheduler=$pol --policyId=$pol --seed=$s $BASE ${SC[$sc]} --csvOutput=$o/log.csv" >> "$JOB"
        done
        for d in 0 1 2 3 4; do
            o="$ROOT/$sc/dqn_seed$d/seed$s"; mkdir -p "$o"
            echo "--scheduler=dqn --policyFile=$ART/dqn_seed$d.txt --policyId=dqn_seed$d --seed=$s $BASE ${SC[$sc]} --csvOutput=$o/log.csv" >> "$JOB"
        done
    done
done
SIM_BIN="$(ls "$NS3_DIR"/build/scratch/aoi-scheduler/ns3*-aoi-scheduler-sim-* | head -n1)"; export SIM_BIN
echo "$(wc -l < "$JOB") runs"
xargs -P "$N_CORES" -I{} bash -c '"$SIM_BIN" --enableNetAnim=false {} > /dev/null 2>&1 || echo "[FAILED] {}"' < "$JOB"
echo "done: $(find "$ROOT" -name log.csv | wc -l) logs"
