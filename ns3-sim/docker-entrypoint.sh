#!/usr/bin/env bash
# ==============================================================================
# Docker Entrypoint for NS-3 AoI Scheduler
# Ensures scratch/aoi-scheduler is symlinked and environment is ready
# ==============================================================================
set -e

NS3_DIR="${NS3_DIR:-/opt/ns3/ns-allinone-3.41/ns-3.41}"
PROJECT_ROOT="/workspace/DRL_agent"

# 1. Symlink project ns3-sim into NS-3 scratch directory if not already linked
if [ -d "${PROJECT_ROOT}/ns3-sim" ] && [ -d "${NS3_DIR}/scratch" ]; then
    ln -sfn "${PROJECT_ROOT}/ns3-sim" "${NS3_DIR}/scratch/aoi-scheduler"
fi

# 2. If 'test' argument is supplied, run the full verification suite
if [ "$1" = "test" ]; then
    echo "========================================================"
    echo " Running Full Turnkey Cross-Platform Test Suite"
    echo "========================================================"
    
    cd "${PROJECT_ROOT}"
    echo "[1/4] Running Python Contract and Logic Tests..."
    pytest tests/test_contract_hygiene.py tests/test_aoi.py tests/test_metrics.py tests/test_state_spec.py -v

    echo "[2/4] Running C++ vs NumPy Parity Gate (Linux g++)..."
    pytest tests/test_ns3_policy_parity.py -v

    echo "[3/4] Compiling NS-3 Simulation with DQN Policy..."
    cd "${NS3_DIR}"
    ./ns3 build scratch/aoi-scheduler/aoi-scheduler-sim

    echo "[4/4] Executing 5-Second Smoke Test Simulation (DQN)..."
    ./ns3 run "scratch/aoi-scheduler/aoi-scheduler-sim \
        --scheduler=dqn \
        --policyFile=${PROJECT_ROOT}/deploy/artifacts/dqn_seed0.txt \
        --policyId=dqn_seed0 \
        --simTime=5 \
        --csvOutput=${PROJECT_ROOT}/ns3-sim/results/smoke_test.csv"
    
    echo "========================================================"
    echo " All Cross-Platform Tests Passed Successfully!"
    echo "========================================================"
    exit 0
fi

# Default: execute user command
exec "$@"
