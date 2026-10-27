> **Note:** All results presented here reflect simulation under assumed channel parameters, pending a real hardware campaign.

# AoI DRL Scheduler

DRL-Based Age-of-Information-Aware Cross-Layer Scheduler for mixed-criticality wireless IoT networks.

## Setup

This project uses Python 3.11 and is designed to run both on a laptop (for training/simulation) and a Raspberry Pi Zero 2W (for deployment).

### 1. Create a Virtual Environment

```bash
python3.11 -m venv venv
# Windows:
.\venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate
```

### 2. Install Dependencies

Depending on what part of the project you are working on, install the necessary dependencies:

**For Simulation & Training (Laptop):**
```bash
pip install -e .[train,dev]
```

**For Gateway Deployment (Raspberry Pi):**
*(Note: PyTorch is explicitly excluded to save space and avoid ARM wheel issues on the Pi Zero)*
```bash
pip install -e .
```

### 3. Pre-commit Hooks

Ensure code formatting remains consistent by installing the pre-commit hooks:
```bash
pre-commit install
```

## Running the Live Demo & NS-3 Evaluation

The DQN runs **inside ns-3 as a C++ forward pass** (`ns3-sim/dqn-policy.h`), not through gym or Python.
The dashboard shows ns-3 data only: live UDP telemetry, or recorded ns-3 runs.
See [`docs/DEMO_RUNBOOK.md`](docs/DEMO_RUNBOOK.md) for the panel script.

```bash
bash tools/rehearse.sh                    # once (~15 s): record S0-S4 + best-case runs, build the Evidence data
bash tools/run_live_demo.sh --compare     # LIVE: RR | Max-Weight | CAG | DQN as real-time ns-3 runs (120 s)
python3 tools/demo_server.py --open-browser --live   # fallback: replay recordings, no ns-3 needed (works offline)
```

Dashboard: pick a **Scenario** (S0-S4 or the 120 s demo timeline) to see its network effects (jammer, walking node,
dead node, link quality rings); **Side-by-Side** compares the four schedulers on the same run; **Evidence** shows the
1000-run campaign and the best-case runs (labelled as selected). Needs a built ns-3 (set `NS3_DIR` if it is not found).
Single scheduler live: `bash tools/run_live_demo.sh 8000 9999 1 dqn` (port, UDP port, DQN seed, scheduler).

### NS-3 Evaluation Campaign (Scenarios S0–S4)
To execute the full evaluation matrix across all policies (RR, FPQ, Max-Weight, CAG, Random, DQN) and seeds:

```bash
bash ns3-sim/scripts/run_campaign.sh
```

