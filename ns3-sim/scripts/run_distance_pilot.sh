#!/usr/bin/env bash
# Distance pilot (docs/DISTANCE_PILOT.md): S10-S11 x {cag, fpq, rr, dqn_seed0-4} x eval seeds 200-204.
# Writes to results/ns3_distance_pilot/ only; the main campaign results are not touched.
set -euo pipefail
NS3_DIR="${NS3_DIR:-$(ls -d "$HOME"/Downloads/ns-allinone-*/ns-3.* "$HOME"/ns3/ns-allinone-*/ns-3.* 2>/dev/null | tail -n1 || true)}"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RESULTS_ROOT="${RESULTS_ROOT:-${PROJECT_ROOT}/results/ns3_distance_pilot}"
ARTIFACTS_DIR="${PROJECT_ROOT}/deploy/artifacts"
N_CORES="${N_CORES:-$(nproc 2>/dev/null || echo 4)}"
SEEDS=(200 201 202 203 204)
BASE_FLAGS="--slotDuration=0.1 --simTime=300 --txPower=20"

declare -A SC_FLAGS=(
    [S10]="--distanceScale=6"
    [S11]="--distanceScale=10"
)

JOB_FILE="$(mktemp)"; trap 'rm -f "${JOB_FILE}"' EXIT
for sc in S10 S11; do
    for pol in cag fpq rr; do
        for s in "${SEEDS[@]}"; do
            out="${RESULTS_ROOT}/${sc}/${pol}/seed${s}"; mkdir -p "$out"
            echo "--scheduler=${pol} --policyId=${pol} --seed=${s} ${BASE_FLAGS} ${SC_FLAGS[$sc]} --csvOutput=${out}/log.csv" >> "$JOB_FILE"
        done
    done
    for d in 0 1 2 3 4; do
        for s in "${SEEDS[@]}"; do
            out="${RESULTS_ROOT}/${sc}/dqn_seed${d}/seed${s}"; mkdir -p "$out"
            echo "--scheduler=dqn --policyFile=${ARTIFACTS_DIR}/dqn_seed${d}.txt --policyId=dqn_seed${d} --seed=${s} ${BASE_FLAGS} ${SC_FLAGS[$sc]} --csvOutput=${out}/log.csv" >> "$JOB_FILE"
        done
    done
done
SIM_BIN="$(ls "${NS3_DIR}"/build/scratch/aoi-scheduler/ns3*-aoi-scheduler-sim-* | head -n1)"; export SIM_BIN
echo "$(wc -l < "$JOB_FILE") runs, ${N_CORES} workers, binary ${SIM_BIN}"
xargs -P "${N_CORES}" -I{} bash -c '"${SIM_BIN}" --enableNetAnim=false {} > /dev/null 2>&1 || echo "[FAILED] {}"' < "$JOB_FILE"
echo "done: $(find "$RESULTS_ROOT" -name log.csv | wc -l) logs"
