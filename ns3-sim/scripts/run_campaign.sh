#!/usr/bin/env bash
# ==============================================================================
# NS-3 Evaluation Campaign: Scenario Matrix S0-S4 across all baselines & DQN
# Tasks: N2.5, N4.2
# ==============================================================================
set -euo pipefail

NS3_VERSION="3.41"
NS3_HOME="${NS3_HOME:-$HOME/ns3}"
NS3_DIR="${NS3_DIR:-${NS3_HOME}/ns-allinone-${NS3_VERSION}/ns-${NS3_VERSION}}"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RESULTS_ROOT="${RESULTS_ROOT:-${PROJECT_ROOT}/results/ns3_campaign}"
CONFIG_FILE="${PROJECT_ROOT}/config/system.yaml"
ARTIFACTS_DIR="${PROJECT_ROOT}/deploy/artifacts"

SIM_TIME=300
SLOT_DURATION=0.1
N_CORES="${N_CORES:-$(nproc 2>/dev/null || echo 4)}"

echo "========================================================"
echo " AoI DRL Scheduler -- NS-3 Evaluation Campaign"
echo " Parallel Execution: ${N_CORES} workers"
echo "========================================================"

# Read eval_seeds from config/system.yaml
SEEDS=($(python3 -c "
import yaml
try:
    with open('${CONFIG_FILE}') as f:
        cfg = yaml.safe_load(f)
    print(' '.join(str(s) for s in cfg['rl']['eval_seeds']))
except Exception:
    print(' '.join(str(s) for s in range(100, 120)))
"))

echo "Evaluation seeds (${#SEEDS[@]}): ${SEEDS[*]}"

# Scenarios to evaluate (S0 to S4)
SCENARIOS=("S0" "S1" "S2" "S3" "S4")

# Policies: 5 baselines + 5 DQN seeds
BASELINES=("rr" "fpq" "maxweight" "cag" "random")
DQN_SEEDS=(0 1 2 3 4)

# Build job list
JOB_FILE="$(mktemp)"
trap 'rm -f "${JOB_FILE}"' EXIT

for sc in "${SCENARIOS[@]}"; do
    # Scenario flag settings
    SC_FLAGS="--slotDuration=${SLOT_DURATION} --simTime=${SIM_TIME}"
    # Scenario flags. S1/S3 TX powers were chosen from measured RSSI only (never from scheduler results):
    # S1 puts the far nodes at about -75..-79 dBm (target band -85..-78); S3 lets STA-4's walk reach about -80 dBm
    # while staying associated (at 0 dBm it loses association at the edge and never rejoins).
    case "$sc" in
        "S0")  # Nominal: 5/8/12/18 m, 20 dBm
            SC_FLAGS="${SC_FLAGS} --txPower=20.0 --distanceScale=1.0"
            ;;
        "S1")  # Weak links
            SC_FLAGS="${SC_FLAGS} --txPower=-5.0 --distanceScale=1.0"
            ;;
        "S2")  # Co-channel interferer 30-150 s; ~20% extra loss on routine STA-4 while it is on
            SC_FLAGS="${SC_FLAGS} --interferer=cochannel --intfStart=30 --intfStop=150 --intfRateMbps=2.0 --intfLossNode=3 --intfLoss=0.2"
            ;;
        "S3")  # Routine STA-4 walks to the cell edge and back (1 m/s)
            SC_FLAGS="${SC_FLAGS} --txPower=5.0 --mobileNode=3 --mobileSpeed=1.0"
            ;;
        "S4")  # Fault: urgent STA-2 down 60-90 s
            SC_FLAGS="${SC_FLAGS} --failNode=1 --failAt=60 --recoverAt=90"
            ;;
    esac

    # 1. Baselines
    for pol in "${BASELINES[@]}"; do
        for s in "${SEEDS[@]}"; do
            OUT_DIR="${RESULTS_ROOT}/${sc}/${pol}/seed${s}"
            mkdir -p "${OUT_DIR}"
            echo "--scheduler=${pol} --policyId=${pol} --seed=${s} ${SC_FLAGS} --csvOutput=${OUT_DIR}/log.csv" >> "${JOB_FILE}"
        done
    done

    # 2. DQN Seeds
    for dqn_s in "${DQN_SEEDS[@]}"; do
        POL_ID="dqn_seed${dqn_s}"
        TXT_FILE="${ARTIFACTS_DIR}/${POL_ID}.txt"
        if [ ! -f "${TXT_FILE}" ]; then
            continue
        fi
        for s in "${SEEDS[@]}"; do
            OUT_DIR="${RESULTS_ROOT}/${sc}/${POL_ID}/seed${s}"
            mkdir -p "${OUT_DIR}"
            echo "--scheduler=dqn --policyFile=${TXT_FILE} --policyId=${POL_ID} --seed=${s} ${SC_FLAGS} --csvOutput=${OUT_DIR}/log.csv" >> "${JOB_FILE}"
        done
    done
done

TOTAL_JOBS=$(wc -l < "${JOB_FILE}")
echo "Generated ${TOTAL_JOBS} evaluation runs in queue."

# Run the prebuilt simulator binary directly (one process per job, in parallel).
SIM_BIN="$(ls "${NS3_DIR}"/build/scratch/aoi-scheduler/ns3*-aoi-scheduler-sim-* 2>/dev/null | head -n1)"
if [ -z "${SIM_BIN}" ]; then
    (cd "${NS3_DIR}" && ./ns3 build scratch/aoi-scheduler/aoi-scheduler-sim)
    SIM_BIN="$(ls "${NS3_DIR}"/build/scratch/aoi-scheduler/ns3*-aoi-scheduler-sim-* | head -n1)"
fi
echo "Simulator binary: ${SIM_BIN}"
export SIM_BIN
xargs -P "${N_CORES}" -I{} bash -c '"${SIM_BIN}" --enableNetAnim=false {} > /dev/null 2>&1 || echo "[FAILED] {}"' < "${JOB_FILE}"

echo "========================================================"
echo " All simulation runs completed."
echo " Generating gap analysis and figures..."
echo "========================================================"

cd "${PROJECT_ROOT}"
python3 tools/ns3_summarize.py --results-root "${RESULTS_ROOT}"

echo "========================================================"
echo " Campaign complete! Results stored under ${RESULTS_ROOT}"
echo "========================================================"
