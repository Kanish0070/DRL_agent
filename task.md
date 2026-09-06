# AoI DRL Scheduler Project - Task Tracker

**Status Key:**
`⬜ TODO` | `🔵 IN PROGRESS` | `✅ DONE` | `🔴 BLOCKED` | `⚠️ DECISION REQUIRED`

## §21. Owner Decision Matrix
*All decisions must be resolved before coding begins.*

| ID | Decision | Status | Owner |
|---|---|---|---|
| D3.1 | Promote CAG to baseline, reframe contribution | ✅ DONE (Modified: using DUI from `criticality_metric_plan.md`) | Owner |
| D2.1 | Clock strategy: duration-based ages (`age_at_tx_us`) | ✅ DONE (Accepted) | Owner |
| D0.1 | Generation-time AoI as authoritative definition | ✅ DONE (Accepted) | Owner |
| D4.1 | 16-D state including criticality weight | ✅ DONE (Accepted) | Owner |
| D2.3 | LCFS-1 queue with sticky alarm latch | ✅ DONE (Accepted) | Owner |
| D1.1 | Slot duration = P99 + 10 ms, 1% late-arrival budget | ✅ DONE (Accepted) | Owner |
| D1.2 | Measured logistic `p_s(RSSI)` + burst overlay | ✅ DONE (Accepted) | Owner |
| D1.3 | `WIFI_PS_NONE`; energy relabelled TX-energy proxy | ✅ DONE (Accepted) | Owner |
| D4.3 | Shield ceilings 2/6/20s; <5% activation target | ✅ DONE (Accepted) | Owner |
| D6.1 | Criticality-weighted mean AoI as primary statistic | ✅ DONE (Accepted) | Owner |
| D6.2 | Commit to reporting negative results (DRL-vs-CAG) | ✅ DONE (Accepted) | Owner |
| D8.1 | Fast sensors at 10 Hz (sets AoI floor) | ✅ DONE (Accepted) | Owner |
| D11.1 | Three sim-to-real gap statistics | ✅ DONE (Accepted) | Owner |
| D11.2 | Campaign scope (~15-18 hours hardware time) | ✅ DONE (Accepted) | Owner |
| D12.2 | Conditional wording of the safety guarantee | ✅ DONE (Accepted) | Owner |

## P0: Foundation, Configuration, and Frozen Contracts
| Task ID | Objective | Key Files | Status | Assignee |
|---|---|---|---|---|
| T0.1 | Repo + env | `pyproject.toml`, `README.md` | ✅ DONE | - |
| T0.2 | Config schema | `config/system.yaml` | ✅ DONE | - |
| T0.3 | AoI contract | `common/contracts/aoi.py` | ✅ DONE | - |
| T0.4 | State contract | `common/contracts/state_spec.py` | ✅ DONE | - |
| T0.5 | Packet contract | `common/contracts/packets.py` | ✅ DONE | - |
| T0.6 | Logging contract | `common/contracts/log_schema.py` | ✅ DONE | - |
| T0.7 | Provenance | `common/provenance.py` | ✅ DONE | - |
| T0.8 | Contract freeze review | `docs/CONTRACTS.md` | ✅ DONE | Guide + Team |

### Acceptance Criteria
- [x] `pip install -e .` succeeds on laptop and Pi OS Lite 64-bit
- [x] Exactly ONE AoI implementation exists
- [x] `StateSpec` hash is emitted and stored
- [x] Golden-bytes packet fixture passes
- [x] `docs/CONTRACTS.md` signed; tagged `v0-contracts`

## P1: Hardware Timing Characterisation Spike
| Task ID | Objective | Key Files | Status | Assignee |
|---|---|---|---|---|
| T1.1 | Timing firmware | `firmware/spike_timing/` | 🔴 BLOCKED | - |
| T1.2 | Pi probe harness | `tools/spike_probe.py` | 🔴 BLOCKED | - |
| T1.3 | Delay campaign | `data/raw/timing/` | 🔴 BLOCKED | - |
| T1.4 | PDR-vs-RSSI sweep | `data/raw/pdr/` | 🔴 BLOCKED | - |
| T1.5 | Analysis + fit | `notebooks/01_timing.ipynb` | 🔴 BLOCKED | - |
| T1.6 | Slot-duration decision | `docs/SLOT_DURATION.md` | 🔴 BLOCKED | - |
| T1.7 | Environment record | `docs/TESTBED.md` | 🔴 BLOCKED | - |

### Acceptance Criteria
- [ ] ≥5,000 samples per condition
- [ ] RSSI sweep spans ≥25 dB
- [ ] `config/measured_params.yaml` validates
- [ ] `T_slot` chosen by D1.1 rule
- [ ] Confirmation campaign late-arrival rate ≤1%

## P2: Simulation Core
| Task ID | Objective | Key Files | Status | Assignee |
|---|---|---|---|---|
| T2.1 | Channel model | `sim/channel.py` | 🔴 BLOCKED | - |
| T2.2 | Queue model | `sim/queue.py` | 🔴 BLOCKED | - |
| T2.3 | AoI + energy accounting | `sim/metrics.py` | 🔴 BLOCKED | - |
| T2.4 | Simulator core | `sim/network.py` | 🔴 BLOCKED | - |
| T2.5 | Replay mode | `sim/replay.py` | 🔴 BLOCKED | - |
| T2.6 | Validation harness | `sim/validate.py` | 🔴 BLOCKED | - |
| T2.7 | Load calibration | `notebooks/02_load.ipynb` | 🔴 BLOCKED | - |

### Acceptance Criteria
- [ ] Deterministic bitwise per seed
- [ ] No global RNG
- [ ] PDR/delay stats match P1
- [ ] AoI resets to delivered-packet age
- [ ] ≥10⁴ simulated slots/sec

## P3: Baseline Schedulers and Evaluation Harness
| Task ID | Objective | Key Files | Status | Assignee |
|---|---|---|---|---|
| T3.1 | Scheduler interface | `schedulers/base.py` | 🔴 BLOCKED | - |
| T3.2 | RR, FPQ, Random | `schedulers/*.py` | 🔴 BLOCKED | - |
| T3.3 | Max-Weight | `schedulers/max_weight.py` | 🔴 BLOCKED | - |
| T3.4 | Channel-Aware Greedy | `schedulers/channel_aware_greedy.py` | 🔴 BLOCKED | - |
| T3.5 | Oracle reference | `schedulers/oracle.py` | 🔴 BLOCKED | - |
| T3.6 | Evaluation harness | `eval/run.py` | 🔴 BLOCKED | - |
| T3.7 | Statistics + figures | `eval/stats.py` | 🔴 BLOCKED | - |
| T3.8 | Pre-registration | `docs/EVAL_PROTOCOL.md` | 🔴 BLOCKED | - |

### Acceptance Criteria
- [ ] 5 baselines + oracle conformance-tested
- [ ] `docs/EVAL_PROTOCOL.md` frozen BEFORE DQN results
- [ ] Baseline leaderboard published internally

## P4: RL Environment Interface and Shielding Layer
| Task ID | Objective | Key Files | Status | Assignee |
|---|---|---|---|---|
| T4.1 | Gym env | `rl/env.py` | 🔴 BLOCKED | - |
| T4.2 | Reward | `rl/reward.py` | 🔴 BLOCKED | - |
| T4.3 | Shield | `rl/shield.py` | 🔴 BLOCKED | - |
| T4.4 | Observation builder | `rl/obs.py` | 🔴 BLOCKED | - |
| T4.5 | Baseline parity wrapper | `rl/wrappers.py` | 🔴 BLOCKED | - |

### Acceptance Criteria
- [ ] `env_checker` passes
- [ ] 16-D state vector
- [ ] Shield activation rate <5% at nominal load

## P5: DQN Implementation and Training
| Task ID | Objective | Key Files | Status | Assignee |
|---|---|---|---|---|
| T5.1 | Training script | `rl/train.py` | 🔴 BLOCKED | - |
| T5.2 | Divergence monitor | `rl/monitors.py` | 🔴 BLOCKED | - |
| T5.3 | Periodic evaluation | `rl/callbacks.py` | 🔴 BLOCKED | - |
| T5.4 | Hyperparameter sweep | `rl/sweep.py` | 🔴 BLOCKED | - |
| T5.5 | Final training runs | - | 🔴 BLOCKED | - |
| T5.6 | Cross-check agent | `rl/reference_dqn.py` | 🔴 BLOCKED | - |
| T5.7 | Ablations | `rl/ablations.py` | 🔴 BLOCKED | - |
| T5.8 | Training report | `docs/TRAINING.md` | 🔴 BLOCKED | - |

### Acceptance Criteria
- [ ] 5 seeds trained; disjoint eval seeds
- [ ] Cross-check agent within 15% of SB3
- [ ] DQN beats RR/FPQ (p<0.05)
- [ ] DQN vs CAG result recorded honestly

## P6: Evaluation, Ablation, and Sensitivity (Simulation)
| Task ID | Objective | Key Files | Status | Assignee |
|---|---|---|---|---|
| T6.1 | Main sweep | `eval/run.py` | 🔴 BLOCKED | - |
| T6.2 | Generalisation battery | `eval/run.py` | 🔴 BLOCKED | - |
| T6.3 | Ablation table | `eval/stats.py` | 🔴 BLOCKED | - |
| T6.4 | Weight sensitivity | `eval/stats.py` | 🔴 BLOCKED | - |
| T6.5 | Statistics module | `eval/stats.py` | 🔴 BLOCKED | - |
| T6.6 | Figure pack | `eval/figures.py` | 🔴 BLOCKED | - |
| T6.7 | Results docs | `docs/RESULTS_SIM.md` | 🔴 BLOCKED | - |

### Acceptance Criteria
- [ ] All sweeps complete with CIs
- [ ] Shuffled-label control non-significant
- [ ] Every figure regenerable by 1 command

## P7: Model Export and NumPy Inference Parity
| Task ID | Objective | Key Files | Status | Assignee |
|---|---|---|---|---|
| T7.1 | Export | `deploy/export.py` | 🔴 BLOCKED | - |
| T7.2 | Infer | `deploy/infer.py` | 🔴 BLOCKED | - |
| T7.3 | Parity gate | `tests/test_parity.py` | 🔴 BLOCKED | - |
| T7.4 | Pi benchmark | `tools/bench_infer.py` | 🔴 BLOCKED | - |
| T7.5 | Negative test | `tests/test_parity.py` | 🔴 BLOCKED | - |

### Acceptance Criteria
- [ ] Parity gate green (max \|ΔQ\| < 1e-5, 100% agreement)
- [ ] On-Pi P99 latency <5ms
- [ ] Mismatched artefacts rejected

## P8: ESP32 Node Firmware
| Task ID | Objective | Key Files | Status | Assignee |
|---|---|---|---|---|
| T8.1 | Skeleton + build | `firmware/node/` | 🔴 BLOCKED | - |
| T8.2 | Network task | `firmware/node/` | 🔴 BLOCKED | - |
| T8.3 | Sensor task | `firmware/node/` | 🔴 BLOCKED | - |
| T8.4 | Heartbeat task | `firmware/node/` | 🔴 BLOCKED | - |
| T8.5 | Diagnostics | `firmware/node/` | 🔴 BLOCKED | - |
| T8.6 | Reconnection state | `firmware/node/` | 🔴 BLOCKED | - |
| T8.7 | Firmware unit tests | `firmware/tests/` | 🔴 BLOCKED | - |
| T8.8 | Bring-up | - | 🔴 BLOCKED | - |

### Acceptance Criteria
- [ ] 4 images from 1 source
- [ ] 0 foreign-grant replies in 10k slots
- [ ] Alarm latch survives overwrite

## P9: Raspberry Pi Gateway Runtime
| Task ID | Objective | Key Files | Status | Assignee |
|---|---|---|---|---|
| T9.1 | Slot-loop skeleton | `gateway/main.py` | 🔴 BLOCKED | - |
| T9.2 | Socket layer | `gateway/sockets.py` | 🔴 BLOCKED | - |
| T9.3 | State tracker | `gateway/state_tracker.py`| 🔴 BLOCKED | - |
| T9.4 | Policy manager | `gateway/policy_manager.py`| 🔴 BLOCKED | - |
| T9.5 | Shield integration | `gateway/main.py` | 🔴 BLOCKED | - |
| T9.6 | Logging subsystem | `gateway/logger.py` | 🔴 BLOCKED | - |
| T9.7 | Dashboard publisher | `gateway/publisher.py` | 🔴 BLOCKED | - |
| T9.8 | Pre-flight checks | `gateway/preflight.py` | 🔴 BLOCKED | - |
| T9.9 | Bring-up | - | 🔴 BLOCKED | - |

### Acceptance Criteria
- [ ] 30-min run with jitter P99 < 5ms
- [ ] CPU < 40%, RSS < 150MB

## P10: Dashboard and Experiment Infrastructure
| Task ID | Objective | Key Files | Status | Assignee |
|---|---|---|---|---|
| T10.1 | SSE server | `dashboard/server.py` | 🔴 BLOCKED | - |
| T10.2 | Front end | `dashboard/static/` | 🔴 BLOCKED | - |
| T10.3 | Control endpoints | `dashboard/server.py` | 🔴 BLOCKED | - |
| T10.4 | Run manager | `experiments/run_experiment.py`| 🔴 BLOCKED | - |
| T10.5 | Offline CLI | `eval/run.py` | 🔴 BLOCKED | - |
| T10.6 | Make report | `Makefile` | 🔴 BLOCKED | - |
| T10.7 | Demo rehearsal | - | 🔴 BLOCKED | - |

### Acceptance Criteria
- [ ] Dashboard live updates ≥2 Hz
- [ ] Jitter unchanged with clients

## P11: Hardware Integration and Contention Experiments
| Task ID | Objective | Key Files | Status | Assignee |
|---|---|---|---|---|
| T11.1 | Testbed assembly | - | 🔴 BLOCKED | - |
| T11.2 | Pilot session | - | 🔴 BLOCKED | - |
| T11.3 | Contention verification| - | 🔴 BLOCKED | - |
| T11.4 | Main campaign | `experiments/` | 🔴 BLOCKED | - |
| T11.5 | Interferer condition | `experiments/` | 🔴 BLOCKED | - |
| T11.6 | Varied placement | `experiments/` | 🔴 BLOCKED | - |
| T11.7 | Matched-load sim | `sim/` | 🔴 BLOCKED | - |
| T11.8 | Validity checker | `tools/` | 🔴 BLOCKED | - |
| T11.9 | Gap analysis | `docs/RESULTS_HW.md`| 🔴 BLOCKED | - |
| T11.10| Alarm demo capture | - | 🔴 BLOCKED | - |

### Acceptance Criteria
- [ ] ≥10 valid runs per condition
- [ ] Metric, ranking, transfer gap stats computed

## P12: Failure Injection and Final Validation
| Task ID | Objective | Key Files | Status | Assignee |
|---|---|---|---|---|
| T12.1 | Fault-injection tools | `tools/inject_fault.py` | 🔴 BLOCKED | - |
| T12.2 | Execute fault matrix | - | 🔴 BLOCKED | - |
| T12.3 | Recovery-time analysis | - | 🔴 BLOCKED | - |
| T12.4 | Shielding figure | `eval/figures.py` | 🔴 BLOCKED | - |
| T12.5 | Final regression | `tests/` | 🔴 BLOCKED | - |
| T12.6 | Results docs | `docs/RESULTS_FAILURE.md`| 🔴 BLOCKED | - |

### Acceptance Criteria
- [ ] Every fault executed ≥3x
- [ ] `make report` regenerates everything from clean clone
