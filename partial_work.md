# Partial Work Tracker (Handoff Document)

This document tracks the exact state of tasks that are currently `🔵 IN PROGRESS` in `task.md`. Since multiple team members and AI agents are collaborating via GitHub, this file serves as the continuous "handoff" point so no context is lost.

## How to use this file:

When you pause work on a task before it is finished, add an entry here detailing:

- The Task ID
- What was accomplished
- What is currently broken, incomplete, or untested
- The exact next steps required to resume work

When resuming work, read this file first. When a task is completed, remove its entry from this file.

---

## Active Handoffs

### T5.5 — Final DQN Training Runs (compute-only)
- **What was accomplished**: All training infrastructure (`rl/train.py`, `rl/monitors.py`, `rl/callbacks.py`, `rl/sweep.py`, `rl/reference_dqn.py`, `rl/ablations.py`) is fully implemented and ready.
- **What is incomplete**: The actual compute run over all 5 training seeds has not been executed (it takes significant wall-clock time).
- **Next steps**: Run `python -m rl.train --all-seeds` to train all 5 seeds. Models saved to `models/dqn_seed{N}.zip`. Then run `python -m rl.reference_dqn --seed 0` to verify cross-check within 15%.

### T6 sweeps + figures — Execution pending trained models
- **What was accomplished**: Full evaluation harness (`eval/run.py`), statistics (`eval/stats.py`), and figure generation (`eval/figures.py`) are implemented.
- **What is incomplete**: Cannot run the main sweep or figure generation until DQN models from T5.5 exist. The shuffled-label control and full CI computation require populated `results/` directories.
- **Next steps**: After training, run each baseline: `python -m eval.run --scheduler rr --seed 100`, etc. Then run `python -m eval.figures --results-dir results --out-dir figures`.

### T7.3 — Parity gate positive test
- **What was accomplished**: `tests/test_parity.py` contains a complete positive parity test that `skipif` skips gracefully when no model exists.
- **What is incomplete**: Requires a trained model in `models/` to actually execute. The test will auto-run once T5.5 is complete.
- **Next steps**: After T5.5 completes, run `pytest tests/test_parity.py -v` — the previously-skipped positive test will now execute.

### T8.8 — ESP32 Bring-up
- **What was accomplished**: Complete firmware source tree implemented (T8.1–T8.7): `node_config.h`, `packet.h`, `lcfs_buffer.h`, `network_task.c`, `sensor_task.c`, `heartbeat_task.c`, `state.c`, and `firmware/tests/test_firmware_host.c` (14 Unity tests).
- **What is incomplete**: Physical flashing and hardware bring-up (T8.8). This requires an ESP32 board and ESP-IDF toolchain installed.
- **Next steps**: Install ESP-IDF, then `idf.py -DCONFIG_NODE_ID=0 flash monitor` for each of the 4 node IDs.
