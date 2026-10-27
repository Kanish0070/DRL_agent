#!/usr/bin/env bash
# ==============================================================================
# Live Demo Launcher: Realtime NS-3 + Live Dashboard (Task N6.1)
# ==============================================================================
set -euo pipefail

PORT="${1:-8000}"
UDP_PORT="${2:-9999}"
POLICY_SEED="${3:-0}"
SCHEDULER="${4:-dqn}"

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NS3_VERSION="3.41"
NS3_HOME="${NS3_HOME:-$HOME/ns3}"
NS3_DIR="${NS3_DIR:-${NS3_HOME}/ns-allinone-${NS3_VERSION}/ns-${NS3_VERSION}}"
if [ ! -x "${NS3_DIR}/ns3" ]; then
    # Fall back to any other built ns-3 that has this project linked into scratch/
    for cand in "$HOME"/Downloads/ns-allinone-*/ns-3.* "$HOME"/ns3/ns-allinone-*/ns-3.*; do
        if [ -x "${cand}/ns3" ] && [ -e "${cand}/scratch/aoi-scheduler" ]; then NS3_DIR="${cand}"; break; fi
    done
fi
if [ ! -x "${NS3_DIR}/ns3" ]; then
    echo "ERROR: no ns-3 found. Set NS3_DIR=/path/to/ns-3.xx (with scratch/aoi-scheduler linked)." >&2
    exit 1
fi
echo "Using ns-3 at: ${NS3_DIR}"
SCENARIO="${PROJECT_ROOT}/ns3-sim/scenarios/demo.json"
POLICY_TXT="${PROJECT_ROOT}/deploy/artifacts/dqn_seed${POLICY_SEED}.txt"
OUT_CSV="${PROJECT_ROOT}/ns3-sim/results/demo/live_log.csv"

mkdir -p "${PROJECT_ROOT}/ns3-sim/results/demo"

echo "========================================================"
echo " AoI DRL Scheduler -- Realtime NS-3 Live Demo (N6.1)"
echo " Dashboard: http://localhost:${PORT}"
echo " Telemetry: UDP 127.0.0.1:${UDP_PORT}"
echo " Scheduler: ${SCHEDULER}"
echo "========================================================"

# 1. Start Demo Telemetry Server in the background
echo "[1/2] Starting telemetry server..."
python3 "${PROJECT_ROOT}/tools/demo_server.py" \
    --live \
    --port "${PORT}" \
    --udp-port "${UDP_PORT}" \
    --open-browser &
SERVER_PID=$!

cleanup() {
    echo ""
    echo "[Cleanup] Stopping demo server (PID: ${SERVER_PID})..."
    kill -TERM "${SERVER_PID}" 2>/dev/null || true
    wait "${SERVER_PID}" 2>/dev/null || true
    echo "Done."
}
trap cleanup EXIT INT TERM

sleep 1.5

# 2. Start Realtime NS-3 Simulation
echo "[2/2] Launching realtime NS-3 simulation..."
POLICY_FLAG=""
if [ "${SCHEDULER}" == "dqn" ]; then
    POLICY_FLAG="--policyFile=${POLICY_TXT} --policyId=dqn_seed${POLICY_SEED}"
fi

(cd "${NS3_DIR}" && ./ns3 run "scratch/aoi-scheduler/aoi-scheduler-sim \
    --realtime=true \
    --liveUdpPort=${UDP_PORT} \
    --scenarioFile=${SCENARIO} \
    --scheduler=${SCHEDULER} \
    ${POLICY_FLAG} \
    --csvOutput=${OUT_CSV}")

echo "========================================================"
echo " Realtime simulation finished."
echo " Press Ctrl+C to close the dashboard server."
echo "========================================================"

wait "${SERVER_PID}"
