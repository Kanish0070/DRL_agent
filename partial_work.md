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

### P1 — Methodology Decision (NOT YET STARTED, pre-work note)

**Date:** 2026-09-22
**Decision:** Raspberry Pi Zero 2W is **not currently available**. P1 will proceed
using a **NS3 + ESP32 hybrid** approach, approved and documented.

**What was done:**
- Full methodology document written: `docs/P1_NS3_ESP32_DELAY_CHARACTERISATION.md`
- All T1.1–T1.7 tasks remapped to laptop+ESP32 (real timing) + NS3 (PDR sweep)
- No code written yet — documentation only

**What is NOT done yet (next steps to start P1):**
1. Write ESP32 echo firmware: `firmware/spike_timing/main.c` — see Section 3.1 of the doc
2. Update `tools/spike_probe.py` with `--host` argument for laptop operation
3. Run NS3 PDR sweep script: `ns3-sim/scratch/aoi-scheduler/pdr_rssi_sweep.cc`
4. Run hardware timing campaign (laptop ↔ ESP32, ≥5,000 samples)
5. Fill `notebooks/01_timing.ipynb` with analysis and logistic fit
6. Export `config/measured_params.yaml` to unblock P2

**Blocked on:** Nothing — can start immediately with ESP32 boards and laptop.
**Pi-dependent tasks deferred to:** P9 (T9.x gateway runtime tasks).
