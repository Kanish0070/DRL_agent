# Training Phase Plan — AoI DRL Scheduler

# Synthetic Data Assessment & Parameter Fitting → DRL Training

> **Handoff note:** This document was generated after a full assessment of the `synthetic data/`
> folder. Any agent or developer picking this up cold should read this file, then `partial_work.md`,
> then `task.md` before doing anything else.

---

## 1. Dataset Inventory & Assessment

The `synthetic data/` folder contains **four datasets** across two sub-purposes:
**Parameter Fitting** and **Reference only**. None of the raw datasets are fed directly
into DRL training — they inform `config/measured_params_fitted.yaml`, which `NetworkSim`
then uses to simulate the channel.

---

### 1.1 UM-DSI Wi-Fi Fingerprint Database ✅ PRIMARY — Parameter Fitting

📂 `synthetic data/UM_DSI_DB_v1.1.0_full/`  
**License:** CC BY 4.0 — Zenodo DOI 10.5281/zenodo.6928554

| Sub-corpus                                     | Date span                       | Locations                         | Row count     |
| ---------------------------------------------- | ------------------------------- | --------------------------------- | ------------- |
| `data/site_surveys/`                           | 2019-02 → 2021-04 (12 sessions) | 97 named reference points         | ~10,580       |
| `data/mon_devices/` (7× Raspberry Pi monitors) | 2019-02 → 2021-03 (26 months)   | Fixed positions in `mds_info.csv` | **7,435,398** |

**Data format per row:**

- `timestamps.csv` — `YYYYMMDDHHMMSSfff` format
- `coordinates.csv` — `x, y` (or `x, y, z`) in metres on building floor plan
- `rssis.csv` — `AP_id:RSSI_dBm, AP_id:RSSI_dBm, ...` (20–80 APs visible per scan)
- `channels.csv` — `AP_id:channel, ...`

**Why it's the primary fitting source:**

- Site surveys give **distance-stratified RSSI** → fits log-distance path loss curve and logistic PDR sigmoid.
- 26-month monitoring time series gives **RSSI temporal autocorrelation** → fits AR(1) shadowing parameter `rho`.
- AP disappearance events in monitoring data proxy **Gilbert-Elliott burst losses**.

---

### 1.2 RSSI Fingerprint Dataset ⚠️ SECONDARY — Cross-validation only

📂 `synthetic data/Parameter Fitting/RSSI-Dataset-for-Indoor-Localization-Fingerprinting/`  
**Source:** Sadowski, Spachos, Plataniotis — IEEE IoT Journal

Three scenarios: 6×5.5 m clean room, 5.8×5.3 m noisy room, 10.8×7.3 m computer lab.  
Three technologies: **Zigbee, BLE, Wi-Fi (802.11n 2.4 GHz)**.

- **Use:** Wi-Fi subset only → cross-validate the logistic PDR sigmoid from step 1.1.
- **Do NOT use:** Zigbee (wrong frequency band) or BLE (different PHY).
- **Size:** Small (49 + 16 + 40 fingerprint points) — supplementary only.

---

### 1.3 RT-IoT 2022 ⚠️ LOW PRIORITY — Timing params only (if accessible)

📂 `synthetic data/Parameter Fitting/RT_IOT2022.csv`

**Current status: file permissions are DENIED** — run first:

```powershell
icacls "d:\dev_env\Final_year\DRL_agent\synthetic data\Parameter Fitting\RT_IOT2022.csv" /grant Users:R
```

This is an IoT network traffic + intrusion detection dataset (MQTT/CoAP/HTTP flows).

- **Use:** "Normal" traffic rows only → estimate `uplink_delay_median_s` and
  `late_arrival_probability` for `measured_params.yaml`'s `timing:` section.
- **Do NOT use** for channel/RSSI parameter fitting.
- If permissions can't be fixed, the existing `timing:` placeholders are within design
  budget and can stay.

---

### 1.4 LTE-Wi-Fi Coexistence Archive ℹ️ REFERENCE only

📂 `synthetic data/Parameter Fitting/archive/LTE-Wifi-Coexisetnce/Coexistence-Algorithms/`

Throughput/collision traces from LTE-Wi-Fi spectrum-sharing simulations.

- **Use:** Validate that the Gilbert-Elliott priors in `measured_params.yaml`
  (`ge_prob_good_to_bad: 0.02`, `ge_prob_bad_to_good: 0.30`) are in a realistic range
  for the coexistence-driven burst loss model. They are.
- **Do NOT use** as primary fitting data — it is simulation output, not real RSSI.

---

## 2. Parameter Fitting Plan

### 2.1 Parameters to Replace and Their Sources

| Parameter in `measured_params.yaml` | Current placeholder | Dataset                                 | Method                                                     |
| ----------------------------------- | ------------------- | --------------------------------------- | ---------------------------------------------------------- |
| `path_loss_exponent`                | `2.8`               | UM-DSI site surveys                     | OLS: `mean(RSSI) ~ -10·n·log10(d) + C`                     |
| `reference_loss_db`                 | `40.046`            | UM-DSI site surveys                     | OLS intercept at `d_0 = 1 m`                               |
| `shadowing_sigma_db`                | `4.0`               | UM-DSI site surveys                     | Std dev of RSSI residuals after path-loss mean removed     |
| `shadowing_correlation_rho`         | `0.9`               | UM-DSI mon_devices (26 months)          | AR(1): `rho = corr(RSSI[t], RSSI[t-1])` per device–AP pair |
| `logistic_r50_dbm`                  | `-82.0`             | UM-DSI surveys + RSSI fingerprint Wi-Fi | MLE sigmoid fit with AP-visibility as PDR proxy            |
| `logistic_slope_db`                 | `4.0`               | Same                                    | MLE slope                                                  |
| `ge_prob_good_to_bad`               | `0.02`              | UM-DSI mon_devices burst sequences      | Count good→bad transitions over AP disappearance runs      |
| `ge_prob_bad_to_good`               | `0.30`              | UM-DSI mon_devices burst sequences      | Count bad→good transitions                                 |
| `ge_bad_state_success_multiplier`   | `0.3`               | LTE-WiFi archive (reference)            | Keep — consistent with literature                          |
| `uplink_delay_median_s`             | `0.005`             | RT-IoT 2022 (if accessible)             | Median flow duration for Normal MQTT rows                  |
| `late_arrival_probability`          | `0.01`              | RT-IoT 2022 (if accessible)             | Fraction of packets with delay > `slot_duration_s`         |

### 2.2 Fitting Pipeline — `tools/fit_params.py` (TO BE CREATED)

```
Step 1 — Path Loss & Shadowing (UM-DSI site surveys)
  Input : data/site_surveys/*/rssis.csv + coordinates.csv + coords_info.csv
  Action: For each survey session, compute distance from monitoring device positions
          (mds_info.csv) to reference point positions (coords_info.csv).
          Group samples by distance band. Fit OLS on mean RSSI vs log10(d).
          Compute residual std dev → shadowing_sigma_db.
  Output: path_loss_exponent, reference_loss_db, shadowing_sigma_db

Step 2 — AR(1) Shadowing Autocorrelation (UM-DSI mon_devices)
  Input : data/mon_devices/YYYY-MM/rssis.csv (all 26 months, all 7 RPi devices)
  Action: For each (monitoring device, AP_id) pair with ≥100 consecutive samples,
          compute lag-1 Pearson correlation. Median across all pairs → rho.
  Note  : 7.4M rows — use pandas chunked read + subsample (1 in 10) for speed.
  Output: shadowing_correlation_rho

Step 3 — Logistic PDR Sigmoid
  Input : UM-DSI site survey RSSI + RSSI fingerprint dataset (Wi-Fi CSVs only)
  Action: Bin RSSI by 2 dBm intervals. Use AP-visibility as PDR proxy:
          AP seen in scan = "packet delivered", AP absent from expected set = "lost".
          Fit: p_s(rssi) = 1 / (1 + exp(-(rssi - r50) / slope)) via MLE.
          Cross-validate on RSSI fingerprint Wi-Fi data.
  Output: logistic_r50_dbm, logistic_slope_db

Step 4 — Gilbert-Elliott Burst Parameters (UM-DSI mon_devices)
  Input : data/mon_devices/YYYY-MM/rssis.csv time series
  Action: For each AP, detect "bad state" = RSSI drops >10 dB below 60-sample
          rolling mean OR AP absent from scan. Count transition events:
          good→bad (onset) and bad→good (recovery). Divide by time-in-state
          to get per-slot probabilities.
  Output: ge_prob_good_to_bad, ge_prob_bad_to_good

Step 5 — Timing (RT-IoT 2022, if accessible)
  Input : RT_IOT2022.csv, filter label == "Normal", protocol == "MQTT"
  Action: Compute median(flow_duration) → uplink_delay_median_s.
          Compute fraction(flow_duration > slot_duration_s) → late_arrival_probability.
  Output: uplink_delay_median_s, late_arrival_probability

Step 6 — Write output + validate
  Action: Write config/measured_params_fitted.yaml.
          Run: python -m sim.validate --params config/measured_params_fitted.yaml
          Assert: simulated PDR curve within ±5% of fitted logistic at 5/8/12/18 m.
```

### 2.3 Distance Mapping Caveat

Neither UM-DSI nor the fingerprint dataset uses distances `[5, 8, 12, 18]` m directly.
Strategy:

1. Fit path-loss model on whatever distances exist in the data.
2. Evaluate the fitted model at exactly 5, 8, 12, 18 m to get the RSSI operating points.
3. Document this extrapolation in `docs/FITTING_REPORT.md`.

### 2.4 Output Files to Create

| File                                 | Purpose                                                                    |
| ------------------------------------ | -------------------------------------------------------------------------- |
| `tools/fit_params.py`                | Fitting pipeline (Steps 1–6)                                               |
| `config/measured_params_fitted.yaml` | Fitted parameters replacing placeholders                                   |
| `docs/FITTING_REPORT.md`             | Documents each fit: data used, method, result, residuals, cross-validation |

---

## 3. DRL Training Plan (Phase P5)

### 3.1 Architecture of Data Flow

```
UM-DSI mon_devices (7.4M rows)  ──→  AR(1) fit ──→ shadowing_correlation_rho ─┐
UM-DSI site surveys (10.6K rows) ──→  OLS fit  ──→ path_loss_*, shadowing_*    ├─→ measured_params_fitted.yaml
                                 ──→  Sigmoid   ──→ logistic_r50, slope         │
RSSI fingerprint (Wi-Fi subset) ──→  Cross-val  ──→ (validates sigmoid)         ┘
LTE-WiFi archive ──→ GE prior check (reference, not primary fitting)

measured_params_fitted.yaml + config/system.yaml
    → sim/channel.py (ChannelModel)
        → sim/network.py (NetworkSim)
            → rl/env.py (AoiSchedulerEnv + shield)
                → rl/train.py (DQN via SB3, 5 seeds)
                    → models/dqn_seedN.zip
                        → eval/run.py (P6 sweeps)
```

**DRL training does NOT consume raw datasets directly.**  
The datasets' only role is to replace placeholders in `measured_params_fitted.yaml`.

### 3.2 Pre-Training Checklist

Before running `python -m rl.train --all-seeds`:

- [ ] `tools/fit_params.py` executed → `config/measured_params_fitted.yaml` written
- [ ] `python -m sim.validate` passes with fitted params (PDR within ±5%)
- [ ] All 15 Owner Decisions in `task.md` are ✅ DONE
- [ ] P3 complete (all 6 schedulers + eval harness) — ✅ DONE per task.md
- [ ] P4 complete (RL env + shield, `check_env` passes) — ✅ DONE per task.md
- [ ] `docs/EVAL_PROTOCOL.md` written and frozen (pre-registration before any DQN numbers)
- [ ] `config/system.yaml` `rl:` section locked — no hyperparameter changes post-training start

### 3.3 Training Commands

```bash
# Step 1: Fix RT-IoT permissions (optional, for timing params)
icacls "synthetic data\Parameter Fitting\RT_IOT2022.csv" /grant Users:R

# Step 2: Run parameter fitting
python -m tools.fit_params \
  --survey-dir "synthetic data/UM_DSI_DB_v1.1.0_full/data" \
  --fingerprint-dir "synthetic data/Parameter Fitting/RSSI-Dataset-for-Indoor-Localization-Fingerprinting" \
  --rt-iot "synthetic data/Parameter Fitting/RT_IOT2022.csv" \
  --out config/measured_params_fitted.yaml

# Step 3: Validate fitted channel model
python -m sim.validate --params config/measured_params_fitted.yaml

# Step 4: Train all 5 seeds (T5.5 — currently IN PROGRESS per partial_work.md)
python -m rl.train --all-seeds --params config/measured_params_fitted.yaml

# Step 5: Cross-check agent (T5.6)
python -m rl.reference_dqn --seed 0 --params config/measured_params_fitted.yaml

# Step 6: Ablations (T5.7)
python -m rl.ablations --params config/measured_params_fitted.yaml
```

### 3.4 Hyperparameter Policy

All training hyperparameters come from `config/system.yaml`'s `rl:` section.
**Do not hardcode any values.** Key locked values:

| Key           | Value                                             |
| ------------- | ------------------------------------------------- |
| `train_seeds` | `[0, 1, 2, 3, 4]`                                 |
| `eval_seeds`  | `[100..119]` — strictly disjoint from train_seeds |
| All others    | Read via `load_system_config()["rl"]`             |

---

## 4. Phased Execution Order

```
1. [NOW]     Fix RT-IoT file permissions
2. [NOW]     Implement tools/fit_params.py (Steps 1–6 above)
3. [NEXT]    Run fitting → write measured_params_fitted.yaml
4. [NEXT]    Run sim.validate → confirm PDR curve
5. [AFTER]   Write docs/FITTING_REPORT.md
6. [AFTER]   Execute rl.train --all-seeds  (T5.5 — unblocked once models exist)
7. [AFTER]   rl.reference_dqn cross-check (T5.6)
8. [AFTER]   rl.ablations (T5.7)
9. [AFTER]   P6: eval/run.py full sweeps, figures, RESULTS_SIM.md
```

---

## 5. Risk Register

| Risk                                                                     | Impact                                                  | Mitigation                                                                                                     |
| ------------------------------------------------------------------------ | ------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| AP TX positions not known in UM-DSI → can't compute exact TX-RX distance | Path loss fit less precise                              | Use monitoring device (known fixed position) as TX reference. Document in FITTING_REPORT.md.                   |
| RT-IoT permissions denied                                                | `timing:` stays as placeholder                          | Run `icacls` fix. If still blocked, existing placeholders are within design budget.                            |
| UM-DSI is 802.11 infrastructure Wi-Fi; nodes use ESP32 Wi-Fi             | PHY differences affect r50/slope                        | Flag in docs. Logistic shape is robust; slope may shift ±2 dBm.                                                |
| 7.4M row mon_devices corpus is slow to process                           | Fit script takes hours                                  | Subsample to 1-in-10 rows for AR(1) (temporal structure preserved). Use pandas chunked read.                   |
| Fitted RSSI operating point sits above logistic sensitive region         | CAG ≈ MaxWeight; channel-awareness provides little lift | Document as pre-registered caveat in EVAL_PROTOCOL.md. Try T2.7 distance calibration to shift operating point. |

---

_Related files: `partial_work.md` · `task.md` · `P3_P8_IMPLEMENTATION_PLAN.md` · `config/measured_params.yaml` · `config/system.yaml` · `sim/channel.py` · `sim/validate.py`_
