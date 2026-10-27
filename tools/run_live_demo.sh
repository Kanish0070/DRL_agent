#!/usr/bin/env bash
# ==============================================================================
# Live Demo Launcher: Realtime NS-3 + Live Dashboard (Task N6.1)
#
#   bash tools/run_live_demo.sh                     # one scheduler (DQN) live, 120 s
#   bash tools/run_live_demo.sh --compare           # RR | Max-Weight | CAG | DQN as 4 live ns-3 runs, same seed + scenario
#   bash tools/run_live_demo.sh [--compare] PORT UDP_PORT DQN_SEED SCHEDULER
#
# The DQN runs inside ns-3 as a C++ forward pass (dqn-policy.h); no Python/gym at run time.
# ==============================================================================
set -euo pipefail

COMPARE=0
if [ "${1:-}" == "--compare" ]; then COMPARE=1; shift; fi
PORT="${1:-8000}"
UDP_PORT="${2:-9999}"
POLICY_SEED="${3:-1}"
SCHEDULER="${4:-dqn}"
EVAL_SEED="${EVAL_SEED:-100}"

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NS3_DIR="${NS3_DIR:-}"
SCENARIO="${PROJECT_ROOT}/ns3-sim/scenarios/demo.json"
POLICY_TXT="${PROJECT_ROOT}/deploy/artifacts/dqn_seed${POLICY_SEED}.txt"
OUT_DIR="${PROJECT_ROOT}/ns3-sim/results/demo"
mkdir -p "${OUT_DIR}"

# Locate a built simulator: $NS3_DIR first, then common install locations.
SIM_BIN=""
for cand in ${NS3_DIR:+"${NS3_DIR}"} "$HOME"/Downloads/ns-allinone-*/ns-3.* "$HOME"/ns3/ns-allinone-*/ns-3.*; do
    b="$(ls "${cand}"/build/scratch/aoi-scheduler/ns3*-aoi-scheduler-sim-* 2>/dev/null | head -n1 || true)"
    if [ -n "${b}" ]; then SIM_BIN="${b}"; break; fi
done
if [ -z "${SIM_BIN}" ]; then
    echo "ERROR: no built ns-3 simulator found. Set NS3_DIR=/path/to/ns-3.xx (built, with scratch/aoi-scheduler linked)." >&2
    exit 1
fi

echo "========================================================"
echo " AoI DRL Scheduler -- Realtime NS-3 Live Demo"
echo " Dashboard : http://localhost:${PORT}/?source=live$([ ${COMPARE} -eq 1 ] && echo '&compare=1')"
echo " Telemetry : UDP 127.0.0.1:${UDP_PORT}"
echo " Simulator : ${SIM_BIN}"
if [ ${COMPARE} -eq 1 ]; then echo " Schedulers: rr | maxweight | cag | dqn_seed${POLICY_SEED} (same eval seed ${EVAL_SEED})"
else echo " Scheduler : ${SCHEDULER}$([ "${SCHEDULER}" == dqn ] && echo " (dqn_seed${POLICY_SEED})")"; fi
echo "========================================================"

PIDS=()
cleanup() {
    echo ""
    echo "[Cleanup] Stopping demo server and simulators..."
    for p in "${PIDS[@]}"; do kill -TERM "${p}" 2>/dev/null || true; done
    wait 2>/dev/null || true
    echo "Done."
}
trap cleanup EXIT INT TERM

echo "[1/2] Starting telemetry server..."
BROWSER_ARGS=(--open-browser --open-query "?source=live$([ ${COMPARE} -eq 1 ] && echo '&compare=1')")
[ -n "${NO_BROWSER:-}" ] && BROWSER_ARGS=()   # NO_BROWSER=1: don't open a browser window (testing)
python3 "${PROJECT_ROOT}/tools/demo_server.py" --live --port "${PORT}" --udp-port "${UDP_PORT}" \
    --replay "${PROJECT_ROOT}/ns3-sim/results" "${BROWSER_ARGS[@]}" &
PIDS+=($!)
sleep 1.5

run_sim() {   # run_sim <scheduler> <policyId> [policyFile]
    local pol="$1" pid="$2" file="${3:-}"
    local extra=()
    [ -n "${file}" ] && extra=(--policyFile="${file}")
    "${SIM_BIN}" --enableNetAnim=false --realtime=true --liveUdpPort="${UDP_PORT}" \
        --scenarioFile="${SCENARIO}" --scheduler="${pol}" --policyId="${pid}" --seed="${EVAL_SEED}" \
        "${extra[@]}" --csvOutput="${OUT_DIR}/live_${pid}.csv" > "${OUT_DIR}/live_${pid}.log" 2>&1
}

echo "[2/2] Launching realtime NS-3 simulation(s) -- 120 s..."
if [ ${COMPARE} -eq 1 ]; then
    run_sim rr rr & PIDS+=($!)
    run_sim maxweight maxweight & PIDS+=($!)
    run_sim cag cag & PIDS+=($!)
    run_sim dqn "dqn_seed${POLICY_SEED}" "${POLICY_TXT}" & PIDS+=($!)
    wait "${PIDS[@]:1}"
else
    if [ "${SCHEDULER}" == "dqn" ]; then run_sim dqn "dqn_seed${POLICY_SEED}" "${POLICY_TXT}"
    else run_sim "${SCHEDULER}" "${SCHEDULER}"; fi
fi

echo "========================================================"
echo " Realtime simulation finished. Dashboard stays up -- Ctrl+C to close."
echo "========================================================"
wait "${PIDS[0]}"
