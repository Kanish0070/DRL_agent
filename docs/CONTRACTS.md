# Phase 0: Frozen Contracts Sign-off

This document certifies that the fundamental contracts and schemas for the AoI DRL Scheduler project have been implemented, reviewed, and frozen. No changes may be made to these contracts without team consensus and updating the underlying state schema hashes.

## Contracts Implemented

1. **AoI Contract (`common/contracts/aoi.py`)**
   - Establishes Generation-Time AoI as the single authoritative metric.
   - Includes the mathematical definitions for calculating AoI without clock synchronization.

2. **State Spec Contract (`common/contracts/state_spec.py`)**
   - Defines the 16-D normalized state vector (4 nodes × [AoI, Queue, RSSI, Weight]).
   - Exposes a schema hash to prevent training vs deployment mismatches.

3. **Packet Contract (`common/contracts/packets.py`)**
   - Defines the wire format for UDP communication between the ESP32s and the Raspberry Pi.
   - Includes the CRC16-CCITT implementation and the `alarm_ack` flag addition.

4. **Logging Contract (`common/contracts/log_schema.py`)**
   - Defines the exact columns for the per-slot CSV output to ensure independent reconstruction of all metrics.
   - Defines the JSONL event schemas.

5. **Configuration Schema (`config/system.yaml` & `common/config.py`)**
   - Single source of truth for the project parameters.
   - Includes strict schema validation on startup.

## Signatures

By signing below, we agree that these contracts define the boundaries of the system modules.

- **Team Member 1 (Kanish Kannan):** ___________________________
- **Team Member 2 (Indirajeet Sudharsan):** ___________________________
- **Team Member 3 (Rohith S):** ___________________________
- **Project Guide (Dr. Vydeki D.):** ___________________________

---
*Once signed, the repository should be tagged with `v0-contracts` via Git.*
