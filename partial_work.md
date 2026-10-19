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


### T8.8 — ESP32 Bring-up

- **What was accomplished**: Complete firmware source tree implemented (T8.1–T8.7): `node_config.h`, `packet.h`, `lcfs_buffer.h`, `network_task.c`, `sensor_task.c`, `heartbeat_task.c`, `state.c`, and `firmware/tests/test_firmware_host.c` (14 Unity tests).
- **What is incomplete**: Physical flashing and hardware bring-up (T8.8). This requires an ESP32 board and ESP-IDF toolchain installed.
- **Next steps**: Install ESP-IDF, then `idf.py -DCONFIG_NODE_ID=0 flash monitor` for each of the 4 node IDs.
