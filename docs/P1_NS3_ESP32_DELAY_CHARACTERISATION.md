# P1 — Hardware Timing Characterisation: NS3 + ESP32 Hybrid Approach

**Status:** Approved Alternative (Raspberry Pi unavailable)
**Date:** 2026-09-22
**Author:** Kanish Kannan (23BEC1192)
**Replaces:** Original P1 plan requiring Raspberry Pi Zero 2W as probe host

---

## 1. Context and Motivation

Phase 1 (P1) of the project requires measuring real wireless delay characteristics
before the NS3 simulator (P2) can be parameterised. Per blueprint finding **F1.1**,
training against invented physics is the single largest source of sim-to-real gap.

The original plan used:
- **Raspberry Pi Zero 2W** as the grant-issuing probe host (`tools/spike_probe.py`)
- **ESP32 boards** as the nodes under test

Since the Raspberry Pi is not currently available, this document defines the
approved **NS3 + ESP32 hybrid** methodology that satisfies all P1 acceptance
criteria without the Pi.

> **Blueprint reference:** `AoI_DRL_Scheduler_Engineering_Blueprint.md` — Phase 1
> (lines covering T1.1–T1.7, D1.1, D1.2, F1.1–F1.9)

---

## 2. Role Remapping

| Original Role | Original Hardware | Replacement |
|---|---|---|
| Grant probe / packet timestamper | Raspberry Pi Zero 2W | **Laptop** (runs `tools/spike_probe.py` over Wi-Fi) |
| UDP echo node | ESP32 (×2–4) | ESP32 (unchanged) |
| AP / router | Dedicated 2.4 GHz router | ESP32 #1 as **SoftAP** OR laptop hotspot |
| PDR-vs-RSSI sweep | Physical distance moves | **NS3** (parametric RSSI sweep) |
| Interference A/B condition | Co-channel laptop iperf3 | **NS3** background UDP flow |
| Analysis and fit | Pi → laptop notebook | Laptop notebook (unchanged) |

---

## 3. What Each Tool Provides

### 3.1 ESP32 Boards (Real Hardware Timing)

Used to obtain the **real `T_grant→data` delay distribution** — the quantity
that actually determines slot duration (D1.1). Simulated delays cannot substitute
here because ESP32's Wi-Fi stack behaviour (AMPDU, rate adaptation, beacon
alignment) is not perfectly modelled by NS3.

**Topology:**

```
Laptop (spike_probe.py)
   │  Wi-Fi (laptop hotspot or dedicated router)
   ├─── ESP32 #1  (echo node, STA mode)
   ├─── ESP32 #2  (echo node, STA mode)
   ├─── ESP32 #3  (echo node, STA mode)
   └─── ESP32 #4  (echo node, STA mode)
```

**What is measured:**
- `T_grant→data`: time from laptop sending a grant packet to receiving the data reply
- Per-packet RSSI (node-reported via `esp_wifi_sta_get_ap_info`)
- Packet delivery / loss events

**Critical firmware requirement (F1.3 / D1.3):**
```c
// MUST be called before wifi_start(); omitting this adds 100ms+ jitter
esp_wifi_set_ps(WIFI_PS_NONE);
```

**Sample sizes (F1.7):**
- ≥ 5,000 samples per node per condition
- At ≥ 8 minutes continuous capture at 10 Hz

**Statistics to report:**
```
n, mean, P50, P90, P99, max  — for each node and condition
```

### 3.2 NS3 Simulation (Parametric Sweep)

Used for the **PDR-vs-RSSI sweep** and **interference A/B** conditions.
NS3 provides unlimited repeatability, exact RSSI control, and no physical
movement required — making it ideal for the characterisation sweep that
the blueprint requires at ≥6 positions / ≥25 dB range.

**NS3 configuration to match real ESP32 hardware:**

```
Wi-Fi standard : 802.11n (2.4 GHz, channel 6)
Tx power       : 20 dBm  (ESP32 default)
Data rate      : HtMcs7  (ESP32 typical)
Packet size    : match frozen P0 protocol packet size
Queue model    : LCFS-1  (per D2.3)
Power save     : disabled (WIFI_PS_NONE equivalent)
Topology       : 1 AP + 4 STAs
```

**Sweep parameters:**

| Sweep Variable | Values | Purpose |
|---|---|---|
| Distance (→ RSSI) | 2m, 5m, 10m, 15m, 20m, wall×1, wall×2 | PDR-vs-RSSI logistic fit |
| Background load | 0 Mbps, 5 Mbps UDP | Interference A/B |
| Run duration | ≥ 5,000 packets per point | Statistical validity |

**Output:** Per-packet logs → fit `p_s(RSSI) = 1 / (1 + exp(-(RSSI - R50) / β))`

---

## 4. Task-by-Task Remapping (T1.1 – T1.7)

### T1.1 — Timing Firmware (`firmware/spike_timing/`)

**Original:** ESP32 echo sketch triggered by Pi.
**Updated:** ESP32 echo firmware with SoftAP capability on node #1.

Key firmware responsibilities:
- Connect to laptop hotspot or act as SoftAP
- `esp_wifi_set_ps(WIFI_PS_NONE)` mandatory
- On receipt of a grant packet: read sensor (simulate 1 ms), send reply immediately
- Embed `esp_timer_get_time()` (µs) in reply payload for one-way delay calculation
- Heartbeat every 2 s with RSSI reading (per F3.2 / D3.2 blueprint)

```c
// Packet reply payload (matches P0 frozen contract)
typedef struct {
    uint8_t  magic[2];       // 0xA0, 0x1 (AoI header)
    uint8_t  version;
    uint8_t  node_id;
    uint64_t age_at_tx_us;   // esp_timer_get_time() at send
    int8_t   rssi_dbm;       // esp_wifi_sta_get_ap_info().rssi
    uint16_t seq;
    uint16_t crc16;
} spike_reply_t;
```

### T1.2 — Probe Harness (`tools/spike_probe.py`)

**Original:** Runs on Raspberry Pi.
**Updated:** Runs on **laptop** over Wi-Fi. No code changes needed — only the
execution environment changes.

Add a `--host` argument to direct the probe at the laptop's Wi-Fi IP:
```bash
python tools/spike_probe.py --host 192.168.x.x --nodes 4 --samples 6000
```

The script must record:
- Send timestamp (laptop clock, `time.perf_counter_ns()`)
- Receive timestamp (same clock)
- `age_at_tx_us` from node payload
- RSSI from payload
- Sequence number (to detect drops)

### T1.3 — Delay Campaign (`data/raw/timing/`)

**Original:** Pi → ESP32 → Pi round-trips.
**Updated:** Laptop → ESP32 → Laptop. Same measurements, same output format.

Campaign protocol:
1. Start with all 4 nodes at fixed position (close range, LOS)
2. Run ≥ 5,000 grants per node (clean channel)
3. Repeat with laptop running `iperf3` on same channel (interference condition)
4. Record: timestamp, node_id, T_one_way_us, rssi_dbm, seq, drop flag

**Output file:** `data/raw/timing/timing_YYYYMMDD_HHMMSS.csv`

```csv
timestamp_ns,node_id,T_grant_to_data_us,rssi_dbm,seq,dropped
1748000000000,1,42300,-58,0,0
1748000100000,1,45100,-59,1,0
...
```

### T1.4 — PDR-vs-RSSI Sweep (`data/raw/pdr/`)

**Original:** Physical movement of ESP32 nodes to varied distances.
**Updated:** **NS3 parametric sweep** (see Section 3.2).

NS3 sweep script: `ns3-sim/scratch/aoi-scheduler/pdr_rssi_sweep.cc`

Produces: `data/raw/pdr/pdr_rssi_ns3_YYYYMMDD.csv`

```csv
rssi_dbm,packets_sent,packets_received,pdr,condition
-40,5000,4998,0.9996,clean
-55,5000,4930,0.9860,clean
-70,5000,3750,0.7500,clean
-80,5000,800,0.1600,clean
...
```

> **Note for report:** Clearly state that PDR-vs-RSSI characterisation was
> obtained via NS3 simulation calibrated to ESP32 802.11n parameters, and that
> real-hardware delay distribution was measured on actual ESP32 boards from
> the laptop probe. This is an honest and defensible methodology.

### T1.5 — Analysis + Fit (`notebooks/01_timing.ipynb`)

Unchanged. Notebook loads both real-hardware CSV (timing) and NS3 CSV (PDR)
and produces:

1. Delay distribution plots (CDF, P50/P90/P99 table)
2. Logistic fit: `p_s(RSSI)` with `R50` and `β` parameters
3. Recommended `T_slot` via D1.1 rule:
   ```
   T_slot = ceil_to_10ms( P99(T_grant→data, clean) ) + 10 ms
   ```
4. Exports `config/measured_params.yaml`

### T1.6 — Slot Duration Decision (`docs/SLOT_DURATION.md`)

Unchanged. Documents the chosen `T_slot` value with justification from
measured P99 and the D1.1 rule.

### T1.7 — Environment Record (`docs/TESTBED.md`)

**Updated fields** to reflect actual testbed:

```markdown
## Testbed Configuration (P1 Hybrid)

- Gateway/probe host : Laptop (Windows 11, Python 3.11)
- AP               : Laptop Wi-Fi hotspot OR dedicated router
                     (record which; record channel, SSID)
- Nodes            : 4× ESP32-WROOM-32 DevKit v1
- Firmware SHA     : <git SHA at time of campaign>
- Wi-Fi channel    : 6 (record actual)
- Power save       : WIFI_PS_NONE (verified)
- PDR sweep source : NS3 v3.40, 802.11n model
- Time of day      : <record>
- Background scan  : <record — number of visible APs on ch6>
- Raspberry Pi     : NOT USED in P1 (unavailable; Pi role deferred to P9)
```

---

## 5. Acceptance Criteria Mapping

All original P1 acceptance criteria remain achievable:

| Criterion | Original Method | Hybrid Method | Met? |
|---|---|---|---|
| ≥5,000 samples per condition | Pi probe campaign | Laptop probe campaign (same script) | ✅ Achievable |
| RSSI sweep spans ≥25 dB | Physical distance moves | NS3 parametric sweep (-40 to -85 dBm) | ✅ Achievable |
| `config/measured_params.yaml` validates | From Pi campaign | From merged laptop + NS3 data | ✅ Achievable |
| `T_slot` chosen by D1.1 rule | P99 from Pi data | P99 from laptop hardware data | ✅ Achievable |
| Confirmation campaign late-arrival ≤1% | Pi confirmation run | NS3 confirmation run at chosen `T_slot` | ✅ Achievable |

---

## 6. What Is Deferred (Not Lost)

The following P1-adjacent work requires the Pi and is deferred to P9:

| Deferred Item | Deferred To | Reason |
|---|---|---|
| Pi inference latency benchmark (T7.4) | P7/P9 | Needs Pi hardware |
| Pi gateway slot-loop jitter (P9 criteria: P99 < 5 ms) | P9 | Needs Pi hardware |
| Pi CPU / RSS profiling | P9 | Needs Pi hardware |

These are on the **non-critical path** for P2 parameterisation. P1's only
output that P2 strictly needs is `measured_params.yaml`, which this hybrid
approach fully produces.

---

## 7. Risk Register (P1 Hybrid)

| Risk | Severity | Mitigation |
|---|---|---|
| Laptop hotspot adds extra latency vs dedicated router | MEDIUM | Use a dedicated router if available; document which was used |
| NS3 PDR curve differs from real ESP32 PDR | MEDIUM | Cross-check NS3 P99 delay against laptop-measured P99; flag discrepancy in notebook |
| ESP32 SoftAP degrades timing (shared radio) | MEDIUM | Prefer laptop hotspot as AP; document AP choice in T1.7 |
| Single-room measurements not representative of deployment | LOW | Report as a limitation; interference condition provides realistic variation |

---

## 8. Output Artefacts

| Artefact | Path | Consumed By |
|---|---|---|
| Raw timing CSV (hardware) | `data/raw/timing/` | `notebooks/01_timing.ipynb` |
| Raw PDR CSV (NS3) | `data/raw/pdr/` | `notebooks/01_timing.ipynb` |
| Fitted parameters | `config/measured_params.yaml` | P2 simulator, P8 firmware |
| Slot duration doc | `docs/SLOT_DURATION.md` | D1.1 sign-off |
| Testbed record | `docs/TESTBED.md` | P11 reproducibility |

### `config/measured_params.yaml` schema (expected output)

```yaml
# Auto-generated by notebooks/01_timing.ipynb — DO NOT EDIT MANUALLY
# Source: P1 NS3+ESP32 hybrid campaign, 2026-09-22

timing:
  T_grant_to_data_p50_us:  TO_BE_MEASURED
  T_grant_to_data_p90_us:  TO_BE_MEASURED
  T_grant_to_data_p99_us:  TO_BE_MEASURED
  T_grant_to_data_max_us:  TO_BE_MEASURED
  n_samples:               TO_BE_MEASURED
  condition: clean_channel

slot:
  T_slot_ms:               TO_BE_MEASURED   # ceil_to_10ms(P99) + 10
  late_arrival_budget_pct: 1.0
  sizing_rule: "P99 + 10ms (D1.1)"

channel:
  p_success_model: logistic
  R50_dbm:         TO_BE_MEASURED   # from NS3 PDR sweep
  beta:            TO_BE_MEASURED   # logistic steepness
  rssi_variance_db: TO_BE_MEASURED  # log-normal sigma

source:
  timing_method: esp32_laptop_probe
  pdr_method:    ns3_parametric_sweep
  firmware_sha:  TO_BE_FILLED
  campaign_date: 2026-09-22
```

---

*This document should be read alongside `AoI_DRL_Scheduler_Engineering_Blueprint.md`
Phase 1 for full decision records (D1.1, D1.2) and audit findings (F1.1–F1.9).*
