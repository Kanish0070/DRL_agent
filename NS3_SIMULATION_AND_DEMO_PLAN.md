# NS-3 Evaluation and Live Demo Plan

**Audience:** the team (and any teammate's coding agent) picking up the final phase.
**Scope:** everything left after DQN training: running the trained policy inside
ns-3, evaluating it against the baselines in realistic 802.11 conditions, and
building a demo that shows the scheduler working.
**Status of inputs:** P0, P2–P8 code done; DQN training reported done (models not
yet in this repo, see N0). P1/P9–P12 are hardware-blocked, and this plan uses
ns-3 in place of that hardware.

---

## 1. Framing: what we're claiming and why ns-3

The blueprint's decision D2.2 rejected ns-3 *for training*, because ns-3 is about
100× slower than the Python simulator. That decision still holds. We now use ns-3
for **evaluation**:

> Train in the fast Python simulator (`sim/`), then deploy the frozen policy into
> an independent, higher-fidelity simulator (ns-3: real 802.11n MAC/PHY, CSMA,
> fading, interference) that it never saw during training.

This gives the project three things the hardware phases would have given:

| Blocked hardware phase | ns-3 substitute in this plan |
|---|---|
| P9 Gateway runtime (policy manager + shield in the slot loop) | DQN policy runs inside `MasterSchedulerApp` on the ns-3 AP (N2) |
| P11 Main campaign / interferer / placement (T11.4–T11.6, T11.9 gap stats) | Scenario matrix S0–S3 + sim-to-ns3 gap statistics (N4) |
| P12 Fault injection and recovery (T12.1–T12.4) | Scenario S4: node failure and recovery (N2, N4) |
| P1 PDR-vs-RSSI sweep (T1.4) | ns-3 channel calibration run (N3); this was already approved in `docs/P1_NS3_ESP32_DELAY_CHARACTERISATION.md` |

**Honesty rule (unchanged from earlier plans):** every number is a simulation
result. Say "ns-3 evaluation" and never "hardware". Report DQN-vs-CAG and
DQN-vs-Max-Weight outcomes as they come out (D6.2), including ties and losses.

---

## 2. What exists today (verified in the code)

- `ns3-sim/aoi-scheduler-sim.cc`: 1 AP + 4 STA, 802.11n HT20 2.4 GHz, grant-reply
  protocol over UDP, 5 baselines (rr/fpq/maxweight/cag/random), safety shield,
  per-slot CSV in `SLOT_LOG_COLUMNS` format, FlowMonitor, NetAnim.
- `ns3-sim/analysis/*.py`: sawtooth plots, scheduler comparison, FlowMonitor plots,
  and `validate_against_contracts.py` (replays the AoI trace against
  `common/contracts/aoi.py`).
- `deploy/export.py` writes the SB3 Q-network to `.npz`. `deploy/infer.py` runs a NumPy
  forward pass with the schema-hash check.
- `eval/stats.py`, `eval/figures.py` expect `results_root/<policy_dir>/log.csv`.

**Gaps that block the goal:**

1. **No DQN scheduler in ns-3.** It only has the 5 heuristic baselines.
2. **Tx power doesn't match.** `sim/channel.py` uses `tx_power_dbm = 20.0`. ns-3's
   `YansWifiPhy` default is about 16 dBm. Every RSSI the DQN sees in ns-3 is therefore
   about 4 dB lower than in training, which shifts its inputs out of distribution.
3. **ns-3 has no failure detection.** If a node dies, its AoI rises, the shield fires,
   and the shield then force-grants the dead node every slot. That starves the other
   nodes. `config/system.yaml` already defines `n_degraded: 3` / `n_fail: 5`, but
   ns-3 never uses them.
4. **The nominal scenario can't separate schedulers.** At 5/8/12/18 m all nodes sit
   at about −40 to −60 dBm, far above the −82 dBm logistic midpoint. Delivery is
   near-perfect, so CAG ≈ Max-Weight ≈ DQN. This is already noted in `task.md`
   P2. We need stress scenarios to see any difference.
5. **Wrong seeds and output layout.** `run_all_schedulers.sh` uses seeds 0–4, which
   are the **training** seeds. Evaluation must use `rl.eval_seeds` (100–119). It also
   writes `<sched>_seed<N>.csv`, which isn't the `<policy_dir>/log.csv` layout
   `eval/stats.py` reads.
6. **No scenario controls.** There are no flags for interference, mobility, faults,
   distance or tx power.
7. **No demo front end.** `dashboard/static/` is empty. NetAnim alone works but is a
   weak demo.

---

## 3. Phases

Effort estimates are for one person. Tracks A, B and C can run in parallel once
N1 is done (see §5).

### N0 — Collect training outputs and set up the environment (0.5–1 day)

1. Get the trained artefacts into the repo. `models/` is gitignored, so they aren't
   here yet. Commit only the exported `.npz` and `.txt` policies (they are a few
   kB) under `deploy/artifacts/dqn_seed{0..4}.{npz,txt}`, and keep the SB3 `.zip`
   checkpoints in shared storage.
2. Run `pytest tests/test_parity.py -v` with a real model present (T7.3), and close
   the P5/P6/P7 rows in `task.md`.
3. Fill in the stubbed `docs/TRAINING.md` and `docs/RESULTS_SIM.md` with the real
   Python-sim numbers. They are the reference point for the sim-to-ns3 gap in N4.
4. **Choose the demo DQN seed now, using the Python validation score.** Don't pick it
   after looking at ns-3 results, because that's cherry-picking. All 5 seeds still
   appear in the statistics.
5. Set up the ns-3 environment (the user's machine is Windows 11):
   - **Recommended:** WSL2 Ubuntu 24.04. ns-3 builds and runs headless without
     problems, and WSLg runs NetAnim's Qt GUI. Clone the repo **inside the WSL
     filesystem** (`~/DRL_agent`), not under `/mnt/c/.../OneDrive`. OneDrive sync
     and the 9P filesystem make builds very slow and can corrupt build directories.
   - Optional: a `ns3-sim/Dockerfile` pinned to ns-3.41, so every teammate gets the
     same build.
   - Run `bash ns3-sim/scripts/ns3_setup.sh`, then run the existing simulation once
     and confirm `validate_against_contracts.py` passes. This closes the open P2
     acceptance checkbox.

**Done when:** exported policies are reachable from the repo, the parity test is green,
ns-3 builds, and the existing baseline run validates against the contracts.

### N1 — Run the DQN policy natively in ns-3 (2–3 days) — *critical path*

**Approach: a C++ forward pass, not ns3-ai or a Python bridge.** The network is a
16→64→64→4 MLP (`rl.net_arch: [64, 64]`), which is about 40 lines of C++. This
approach is deterministic, needs no extra dependencies, runs at full ns-3 speed, and
avoids version coupling between ns3-ai and ns-3. The policy only runs inference, so
there's no reason to bring Python into the simulation loop.

1. **`deploy/export_ns3.py`**: `.npz` → plain-text `dqn_seedN.txt`:
   ```
   AOIDQN 1
   schema_hash <get_state_schema_hash()>
   n_layers 3
   layer 0 64 16      # out, in; then 64*16 weights row-major, then 64 biases
   ...
   ```
   Keep it to one definition, reuse `deploy/export.py`'s layer extraction, and
   write floats with `repr` precision (`%.9g`).
2. **`ns3-sim/dqn-policy.h`**: header-only with **no ns-3 includes**. It contains
   `DqnPolicy::Load(path)`, `Forward(const float obs[16]) -> std::array<float,4>`
   and `Act(obs) -> int`. `Act` uses first-max tie-breaking, the same as `np.argmax`.
   `Load` rejects a file whose `schema_hash` doesn't equal the compiled-in
   `STATE_SCHEMA_HASH` constant. This mirrors T7.5's negative test.
3. **`tests/test_ns3_policy_parity.py`**: compiles a ~30-line `ns3-sim/tests/parity_main.cc`
   with `g++`, and skips if no compiler is installed. This works without ns-3, so it
   also runs on Windows and in CI. Feed it about 5,000 observations:
   - 1,000 uniform random vectors in [0,1]^16
   - 4,000 real observations from Python-sim rollouts of the DQN

   Compare against `deploy/infer.py`. **Gate:** max |ΔQ| < 1e-4 (float32 vs
   float64 accumulation) and 100% argmax agreement.
4. **Contract hygiene test:** check that `STATE_SCHEMA_HASH` and the normalization
   constants in the `.cc`/`.h` (`DELTA_MAX=10`, `W_MAX=10`, `RSSI_MIN=-100`,
   `RSSI_RANGE=70`) match `common/contracts/state_spec.py`. The test parses the C++
   source, the same way `tests/test_contract_hygiene.py` checks the Python side.

**Done when:** the parity gate is green for all 5 seeds and a mismatched-hash file is
rejected.

### N2 — Upgrade the ns-3 simulation (3–4 days) — Track A

All changes are in `ns3-sim/aoi-scheduler-sim.cc` unless noted.

1. **`SCHED_DQN`**: add `--scheduler=dqn --policyFile=<path> --policyId=dqn_seed2`.
   `policy_id` in the CSV gets the real ID so runs from different seeds stay separate.
   The shield still wraps the DQN, as in training (`rl/env.py`).
2. **Observation builder** (`BuildObservation()` → `float[16]`), matching
   `NodeState.to_normalized_vector()` exactly:
   - `aoi_norm = min(m_aoi[i] / 10, 1)`
   - `rssi_norm = clip((m_rssi[i] + 100) / 70, 0, 1)`, where `m_rssi` comes from the
     existing sniffer callback (data and heartbeats). This is the same refresh rule
     as `sim/network.py::_refresh_rssi`.
   - `weight_norm = w_i / 10`
   - `queue_norm`: the gateway can't observe the queue directly. In training,
     `SimConfig(arrival_prob=1.0)` with 10 Hz sampling means the queue is almost
     always 1 at decision time. Estimate it as 1 if a sample has been generated
     since the node's last delivery (the gateway knows the 10 Hz period), and 0
     otherwise. Write this assumption down in the code comment and in the results
     doc.
3. **Match tx power to training:** add `--txPower` (default **20.0 dBm**, from
   `sim/channel.py`) and set `TxPowerStart/TxPowerEnd` on the PHY. Also add
   `--pathLossExp` (default 2.8) and `--distanceScale` (default 1.0) for scenarios.
4. **Liveness tracking** (uses `n_degraded`/`n_fail` from `system.yaml`, emits the
   `log_schema.py` event constants):
   - Count consecutive empty grants and missed heartbeats per node, and mark the
     node `DEGRADED` (3) or `UNREACHABLE` (5).
   - Leave unreachable nodes out of shield candidates and mask them out of every
     scheduler's argmax (DQN included: argmax over reachable nodes only).
   - Probe an unreachable node with one grant every N slots, and restore it on
     reply or heartbeat (`NODE_RECOVERED`).
   - Write events to a sidecar `events.jsonl` next to `log.csv`.

   Without this, S4 shows the shield starving the whole network, which looks like a
   bug in our design rather than a stress result.
5. **Scenario controls** (all off by default, so S0 matches the current behaviour):
   - `--interferer=none|cochannel|hidden` with `--intfStart/--intfStop/--intfRateMbps`:
     an extra STA+AP pair on channel 1 running `OnOffApplication` UDP bursts.
     `hidden` places it out of carrier-sense range of the AP but near STA-4.
   - `--mobileNode=3 --mobileSpeed=1.0`: a `WaypointMobilityModel` that walks the
     routine node from 18 m out to the coverage edge and back.
   - `--failNode=1 --failAt=60 --recoverAt=90`: stops and restarts that node's
     `IoTSensorApp` (or sets its PHY to sleep), for fault injection.
   - `--scenarioFile=demo.json` (optional): a timeline of the above events for the
     demo run.
6. **Seeds and output layout:** use `RngSeedManager::SetSeed(1); SetRun(seed)`, which
   is the ns-3-recommended way to get independent replications. Write to
   `ns3-sim/results/<scenario>/<policy_id>/seed<N>/log.csv` (+ `events.jsonl`,
   `flowmon-results.xml`, `run_meta.json` via `common/provenance.py`), so
   `eval/stats.py` reads it as-is with only a recursive glob.
7. **Live telemetry hook (used by N6):** `--liveUdpPort=9999` sends each CSV row
   also as one JSON datagram to 127.0.0.1. Add `--realtime` to switch to
   `RealtimeSimulatorImpl`, so 1 simulated second = 1 wall-clock second.
8. Update `run_all_schedulers.sh` → `run_campaign.sh`: scenario × policy ×
   eval-seed, running in parallel (`xargs -P $(nproc)`), with **eval_seeds read
   from `config/system.yaml`** rather than hard-coded.

**Done when:** all 6 policies (5 baselines + DQN) run in every scenario,
`validate_against_contracts.py` passes on DQN runs too, and S0 with the DQN is
deterministic per seed (identical CSV hash on re-run).

### N3 — Calibrate the ns-3 channel against the training simulator (1–2 days) — Track C

The DQN only means something in ns-3 if its inputs look like what it trained on.

1. **PDR-vs-RSSI sweep in ns-3:** move a single node from 1 to 150 m (or sweep
   `--txPower`), with ≥5,000 grants per point. Fit the logistic `p_s(RSSI)`
   (R50, slope) the same way T1.5 would.
   **What to expect:** ns-3's default `ThresholdPreambleDetectionModel` drops frames
   below about −82 dBm, so the curve will be a step near −82 smeared by fading,
   not a smooth logistic. Measure it; don't assume it.
2. **Compare observation distributions:** under S0, compare the per-feature
   histograms of the 16-D observation in Python-sim vs ns-3 (2-sample KS test per
   feature). Put the overlay plot in the results doc.
3. **Decide (owner decision, record it as D-N3 in `task.md`):**
   - **(a) Keep the policy frozen** and report the measured mismatch as part of the
     transfer gap. This is the default: it's honest, and the user said training is
     done.
   - **(b) Treat the ns-3 fit as the "measured" P1 parameters:** write them to
     `config/measured_params.yaml` (source = `ns3_calibration`), retrain all 5 seeds
     in Python, and re-evaluate in ns-3. This is stronger science but costs a
     retraining cycle. Only do it if the gap from (a) is large (for example, the DQN
     loses to Max-Weight in S0).
4. **Calibrate the stress scenarios:** pick `distanceScale`/`txPower` for S1 so the
   **far node's mean RSSI sits around −85 to −78 dBm** (the sensitive region). That's
   where channel awareness should matter. Pick an interferer rate for S2 that gives
   about 10–20% loss on the affected link.

**Done when:** the calibration figure, KS table and recorded D-N3 decision are in
`docs/RESULTS_NS3.md`, and S1/S2 parameters are fixed in `ns3-sim/scenarios/*.json`.

### N4 — Evaluation campaign and statistics (2–3 days) — Track C

**Scenario matrix** (fixed before running, then frozen. Add it to
`docs/EVAL_PROTOCOL.md` as a "ns-3 addendum" **before** looking at DQN ns-3
results, as T3.8 did for the Python sim):

| ID | Scenario | Substitutes | Hypothesis |
|---|---|---|---|
| S0 | Nominal (5/8/12/18 m, 20 dBm) | T11.4 | AoI-aware schedulers (MW/CAG/DQN) roughly tie; all beat RR/FPQ/Random. |
| S1 | Weak links (far nodes in −85 to −78 dBm) | T11.6 | Channel awareness matters: CAG and DQN beat MW. |
| S2 | Co-channel and hidden-terminal interferer, bursty | T11.5 | Burst loss: shield and DQN keep urgent-class AoI bounded. |
| S3 | Mobility: routine node walks to the edge and back | (new) | Policy adapts to time-varying RSSI. |
| S4 | Fault: urgent node 2 down 30 s, then recovers | T12.2 | Liveness masking avoids starvation, and recovery time is bounded. |

- **Policies:** RR, FPQ, Random, Max-Weight, CAG, DQN (5 seeds, each run separately),
  plus the **DQN without shield** ablation (shows what the shield buys) and
  optionally the Python Oracle score as an upper reference.
- **Seeds:** `rl.eval_seeds` (20) × 300 s (3,000 slots). That's about 5 × 11 × 20 =
  1,100 runs. At roughly 5–20 s each, this takes about 1–3 h on 8 cores.
- **Metrics:**
  - Primary: criticality-weighted mean AoI (D6.1).
  - Secondary: per-class mean, P95 and P99 AoI; fraction of time above the soft
    threshold (200/500/1000 ms); shield activation rate (target < 5% at S0);
    wasted-slot rate; PDR; FlowMonitor delay and jitter; S4 recovery time.
- **Statistics:** paired by seed (same seed = same channel realisation), bootstrap 95%
  CIs, paired t or Wilcoxon, Holm correction across comparisons, and the
  shuffled-label control. All of this reuses `eval/stats.py`.
- **Sim-to-ns3 gap (D11.1's three statistics, ns-3 instead of hardware):**
  - metric gap: |cw-AoI_python − cw-AoI_ns3| per policy
  - ranking gap: Kendall τ between the leaderboards
  - transfer gap: whether DQN's advantage over the best baseline survives the move
- **Figures** (extend `eval/figures.py`, one command regenerates everything):
  - leaderboard bars with CIs per scenario
  - AoI sawtooth DQN vs CAG vs RR
  - per-class P99 AoI
  - shield rate per scenario
  - S4 recovery timeline
  - Python-vs-ns3 gap plot
  - the calibration curve from N3

**Done when:** `docs/RESULTS_NS3.md` holds every table and figure with CIs, the
shuffled-label control is non-significant, and `make report` (or one script)
regenerates everything from the raw CSVs.

### N5 — Demo dashboard, replay mode (3–4 days) — Track B

**Design principle:** the demo is driven by recorded data by default, so it can't fail
on stage. The live mode (N6) uses the same front end.

- **Backend `tools/demo_server.py`:** a small FastAPI or `websockets` server.
  - **Replay source:** reads one or more `log.csv` + `events.jsonl` runs and streams
    rows at 1×, 2×, 5× or 10× speed, with pause and seek.
  - **Live source (N6):** reads ns-3's UDP JSON datagrams.
  - Both produce the same message schema (`SLOT_LOG_COLUMNS` + events).
- **Frontend `dashboard/static/index.html`:** single page, plain JS + Chart.js, no
  build step. It shows:
  - **Topology view:** the AP and 4 STAs at their real positions, coloured by class.
    An animated grant arrow shows each slot's choice, and a red flash marks a shield
    override. Nodes are greyed out when `UNREACHABLE`, and an interferer icon appears
    while it's active.
  - **Live AoI bars:** per node, with that class's soft-threshold and shield-ceiling
    lines.
  - **Rolling AoI sawtooth** (last 30 s) per node.
  - **Running KPIs:** cw-mean AoI, shield count and %, PDR, wasted slots.
  - **Side-by-side mode:** 2–3 policies on the **same seed and scenario**, synced
    slot-by-slot (e.g. RR | CAG | DQN). This is the core visual argument.
  - **Results tab:** static N4 figures and the leaderboard table.
- **Demo scenario `ns3-sim/scenarios/demo.json`:** one 120 s timeline that covers
  every behaviour:

  | t (s) | Event |
  |---|---|
  | 0–20 | Nominal |
  | 20 | Co-channel interferer ON near STA-4 |
  | 45 | Interferer OFF; STA-4 starts walking to the edge |
  | 70 | Urgent STA-2 fails |
  | 100 | STA-2 recovers |
  | 120 | End |

  Pre-record this for RR, Max-Weight, CAG and DQN (plus DQN-no-shield) on a fixed
  eval seed.

**Done when:** `python -m tools.demo_server --replay ns3-sim/results/demo/` opens
the dashboard, plays the 120 s scenario side by side, and works offline.

### N6 — Live mode (2 days, optional) — Track B, after N2.7

- `tools/run_live_demo.sh`: starts ns-3 with `--realtime --liveUdpPort=9999
  --scenarioFile=demo.json --scheduler=dqn`, and starts `demo_server --live`.
- The dashboard has a "LIVE" badge and shows the ns-3 process's simulated time.
  This proves the run is happening now and isn't a recording.
- Stretch goal: dashboard buttons that send a control datagram to ns-3 to trigger
  "kill STA-2" or "interferer ON" on demand. ns-3 schedules the event at the next
  slot. This is impressive but optional. Only add it if N5 is solid.
- Fallback order on demo day: live → replay → recorded screen video (capture one
  in N7).

### N7 — Documentation, viva prep, rehearsal (2 days)

- `docs/RESULTS_NS3.md`: setup, the calibration decision, scenario matrix, results,
  gap statistics, threats to validity (placeholder parameters, queue estimate,
  single-AP topology, simulated interference model).
- Update `ns3-sim/README.md` (DQN flags, scenarios, output layout) and `README.md`
  (a "Run the demo" section).
- Update `task.md` with the N-phase rows, close P2's ns-3 checkbox, and mark the
  P9/P11/P12 rows as "substituted by ns-3 evaluation (N2/N4)" instead of leaving
  them BLOCKED.
- **Prepared panel answers:**
  - "Why ns-3 now if D2.2 rejected it?" → D2.2 rejected it for training. Evaluating
    in a separate, more realistic simulator is a stricter test.
  - "Why doesn't DQN beat CAG at nominal?" → S0 doesn't stress the channel (point to
    the RSSI histogram), then show S1/S2.
  - "Isn't this just Max-Weight?" → the ablation table and S1 results.
  - "What happens if a node dies?" → S4 and liveness masking.
- Record a 5-minute screen capture of the demo as a backup.
- Do two full rehearsals on the demo laptop, offline.

---

## 4. Demo storyboard (target: 8–10 minutes)

1. **Problem (1 min):** mixed-criticality IoT, why AoI and not throughput, and the
   three classes and their deadlines.
2. **System (1 min):** a single diagram: Python sim → DQN training → export →
   C++ policy in the ns-3 gateway → dashboard. Mention the frozen contracts and the
   parity gate (the "same math everywhere" story).
3. **Live run (3 min):** start the demo scenario in side-by-side mode, RR | CAG | DQN.
   Narrate each event as it happens: the interferer, the node walking away, the
   urgent node failing and recovering. Point at the urgent nodes' AoI bars staying
   under their ceilings, and at the shield-override flashes.
4. **Results (2 min):** the leaderboard with CIs per scenario, P99 AoI per class,
   and the shield activation rate. State the honest outcome against CAG.
5. **Credibility (1 min):** the Python→ns-3 gap statistics, the parity test output,
   and a 10 s NetAnim clip showing packets on the real 802.11 stack.
6. **Deployability (30 s):** the ESP32 firmware tree and the NumPy-only inference
   path, i.e. what the hardware deployment would run.

---

## 5. Sequencing and parallel tracks

```
N0 ──► N1 ──┬──► Track A: N2 (ns-3 upgrades) ──► N3 calibration ──► N4 campaign ──┐
            │                                                                       ├──► N7
            └──► Track B: N5 dashboard (on existing baseline CSVs) ──► N6 live ────┘
                 Track C: write the ns-3 eval-protocol addendum before N4 results
```

- Track B can start on day 1 of N2, using CSVs from the current baseline sim, because
  the schema is already frozen. It doesn't have to wait for the DQN.
- Critical path: N0 → N1 → N2 → N3 → N4. That's about 9–13 working days for one
  person, and about 2 weeks end-to-end with 2–3 people working the tracks in parallel.

## 6. Proposed `task.md` rows

| Task ID | Objective | Key Files | Depends on |
|---|---|---|---|
| N0.1 | Publish exported policies, parity green, fill training/sim results docs | `deploy/artifacts/`, `docs/TRAINING.md`, `docs/RESULTS_SIM.md` | — |
| N0.2 | WSL2/Docker ns-3 env, baseline sim validates | `ns3-sim/scripts/`, `ns3-sim/Dockerfile` | — |
| N1.1 | Text export for C++ | `deploy/export_ns3.py` | N0.1 |
| N1.2 | Header-only C++ MLP policy | `ns3-sim/dqn-policy.h` | N1.1 |
| N1.3 | C++/NumPy parity gate + constant hygiene | `tests/test_ns3_policy_parity.py`, `ns3-sim/tests/parity_main.cc` | N1.2 |
| N2.1 | DQN scheduler + observation builder | `ns3-sim/aoi-scheduler-sim.cc` | N1.3 |
| N2.2 | Tx-power/path-loss/distance flags (default 20 dBm) | same | — |
| N2.3 | Liveness tracking + events.jsonl | same | — |
| N2.4 | Interferer / mobility / fault / scenario-file flags | same, `ns3-sim/scenarios/` | — |
| N2.5 | SetRun seeding, results layout, provenance | same, `ns3-sim/scripts/run_campaign.sh` | — |
| N2.6 | Live UDP telemetry + realtime mode | same | — |
| N3.1 | PDR-vs-RSSI calibration + obs-distribution KS | `ns3-sim/analysis/calibrate_channel.py` | N2.2 |
| N3.2 | Owner decision D-N3 (frozen policy vs recalibrate+retrain) | `task.md` | N3.1 |
| N4.1 | Freeze ns-3 eval-protocol addendum | `docs/EVAL_PROTOCOL.md` | N3.2 |
| N4.2 | Run campaign S0–S4 | `ns3-sim/results/` | N2.*, N4.1 |
| N4.3 | Stats, gap statistics, figures | `eval/stats.py`, `eval/figures.py` | N4.2 |
| N5.1 | Demo server (replay) | `tools/demo_server.py` | — |
| N5.2 | Dashboard front end | `dashboard/static/` | N5.1 |
| N5.3 | Demo scenario recordings | `ns3-sim/scenarios/demo.json` | N2.4 |
| N6.1 | Live mode + launcher | `tools/run_live_demo.sh` | N2.6, N5.2 |
| N7.1 | Results doc, README, task.md, viva answers, backup video, rehearsal | `docs/RESULTS_NS3.md` | all |

## 7. Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| DQN ties or loses to CAG/Max-Weight in ns-3 | High at S0 | Expected and pre-registered (D6.2). Make the case with S1/S2/S4, the shield and the deployability story, not a nominal-scenario win. |
| Out-of-distribution observations (RSSI offset, queue estimate) | Medium | Match tx power to 20 dBm, run the N3 KS check, and fall back to D-N3 option (b). |
| ns-3 build pain on Windows | Medium | WSL2 inside the Linux filesystem plus a pinned Dockerfile. Do this in N0, not demo week. |
| Interferer model too strong or too weak to show anything | Medium | Calibrate the loss target (10–20%) in N3 before the campaign. |
| Live demo crashes on stage | Low–Med | Replay mode by default, a recorded video, and offline rehearsals. |
| Selecting the demo seed after seeing ns-3 results | — | Choose it in N0 from the Python validation score, and report all 5 seeds. |
| C++/Python drift (constants, tie-breaking) | Low | N1.3 parity gate and constant-hygiene test run in CI. |
