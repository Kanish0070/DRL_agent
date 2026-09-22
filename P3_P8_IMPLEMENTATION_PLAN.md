# P3-P8 Implementation Plan

**Audience:** a teammate's coding agent picking up this repo cold. This document is
self-contained — it names exact files, exact interfaces to match, exact formulas
(taken from the already-validated `ns3-sim/` reference implementation), and exact
acceptance criteria. Read this whole document before writing any code; the phases
depend on each other in the order given.

**Scope:** P3 (baseline schedulers + eval harness) through P8 (ESP32 firmware code).
This picks up immediately after P0 (frozen contracts) and P2 (Python simulation core),
both already done. **Do not implement P1, P9, P10, P11, P12** — those are out of scope
for this document (P1 is hardware-blocked, see `docs/P1_NS3_ESP32_DELAY_CHARACTERISATION.md`
for the approved substitute methodology; P9-P12 depend on hardware bring-up or on
work not covered here).

> **Note on API accuracy:** this document was revised after P2 was merged from a
> parallel branch with a more complete design than an earlier draft assumed (Gauss-
> Markov shadowing + Gilbert-Elliott burst loss in the channel model, arrival-
> probability-driven queues, `sim/replay.py` and `sim/validate.py` already done). Every
> interface named below matches what is actually on disk — verify by reading the
> cited files yourself before writing code, don't trust memory of an earlier version.

---

## 0. Orientation: what already exists, and what you must reuse

Do not reimplement any of the following. Import them.

| Module | What it owns | Why it matters here |
|---|---|---|
| `common/contracts/aoi.py` | `update_aoi_for_slot`, `compute_delivered_age` — the **one** authoritative AoI update rule | `tests/test_contract_hygiene.py` fails the build if this logic is redefined anywhere else in `common/`, `sim/`, `schedulers/`, `rl/`, `eval/`, `gateway/`, `tools/`, or `tests/`. Never inline AoI math. `sim/metrics.py::MetricsTracker` is the one place that already applies it per slot. |
| `common/contracts/state_spec.py` | `NodeState`, `NetworkState`, `get_state_schema_hash()` — the frozen 16-D state layout (4 nodes × [aoi_norm, queue_norm, rssi_norm, weight_norm]) | `sim/network.py::NetworkSim._build_observation()` already builds this every step — **you do not need to build the 16-D vector yourself**, `NetworkSim.step()`/`reset()` return it directly. P7's export/parity gate keys off `get_state_schema_hash()` to detect train/deploy mismatches. |
| `common/contracts/packets.py` | Wire format, CRC16-CCITT, `PacketHeader`, `GrantPacket` | Has an unfinished `# TODO: Add DATA, HEARTBEAT, HELLO, CONTROL models similarly`. **You must finish this** before P8's network task can serialize real packets — see P8 §7.0 below. This is filling a documented gap, not reopening the frozen P0 contract review. |
| `common/contracts/log_schema.py` | `SLOT_LOG_COLUMNS`, `validate_slot_row`, JSONL event type constants | P3's eval harness (`eval/run.py`) must emit rows matching this schema exactly (the same one `sim/replay.py` already reads and `ns3-sim` already emits). |
| `common/config.py` | `load_system_config()`, `load_measured_params()` | Single source of truth for every parameter. Never hardcode a value that's already in `config/system.yaml` or `config/measured_params.yaml`. `load_measured_params()` validates the `channel`/`timing` sections match what `sim/channel.py::ChannelParams.from_measured_params()` and `sim/network.py::SimConfig.from_configs()` actually read. |
| `common/metrics.py` | `compute_dui`, `calculate_reward`, `criticality_weighted_aoi` | The one authoritative urgency/reward/reporting metric (Dynamic Urgency Index, see `criticality_metric_plan.md`). P4's reward function must call `compute_dui`/`calculate_reward`, not reimplement them. Distinct from `sim/metrics.py` (below) — that one owns AoI/energy bookkeeping, this one owns the DUI reward formula. |
| `sim/metrics.py` | `MetricsTracker` — per-slot AoI/energy/wasted-slot bookkeeping, wraps `common/contracts/aoi.py` | `NetworkSim` owns one `MetricsTracker` instance (`sim.metrics`); read `sim.metrics.aoi`, `.total_energy`, `.wasted_slots`, `.delivered_count` rather than recomputing any of this. |
| `common/provenance.py` | `generate_run_meta`, `write_run_meta`, `get_params_source` | Every run this plan produces (eval sweeps, training runs) must call `write_run_meta()` so results are traceable. `get_params_source()` currently reports `"placeholder_pending_p1"` — say so in every doc you write (see §7, "Honesty rule"). |
| `sim/channel.py` | `ChannelParams`, `ChannelModel`, `path_loss_db`, `success_probability_from_rssi` | Log-distance path loss + AR(1)-correlated shadowing + a Gilbert-Elliott burst-loss overlay (see the file's own docstring for the audit findings this addresses — F2.4/F2.5). `ChannelModel.step(rng)` advances one slot; `.rssi(i)` / `.success_probability(i)` / `.draw_success(i, rng)` read the *current* (already-advanced) state. P3's Channel-Aware-Greedy and Oracle schedulers use `success_probability_from_rssi` / `ChannelModel.success_probability` directly. |
| `sim/queue.py` | `NodeQueue` (LCFS default, FIFO ablation option), `.has_data()`, `.push(is_alarm)`, `.pop_for_delivery()`, `.age_all(t_slot)`, `.alarm_latched`, `.clear_alarm()` | One `NodeQueue` per node, owned by `NetworkSim.queues`. |
| `sim/network.py` | `SimConfig`, `NetworkSim` — the discrete-slot simulator core | **This is what every scheduler and the RL env run against.** `SimConfig.from_configs(system_config, measured_params, episode_length, arrival_prob=1.0)` builds the config; `NetworkSim(sim_config).reset(seed) -> obs` starts an episode; `.step(action) -> (obs, info)` advances one slot. **It does not apply a safety shield** — that's explicitly deferred to P3/P4 (see its own docstring). Needs a small, carefully-scoped extension for P3's Oracle — see P3 §1.5. |
| `sim/replay.py` | `replay_log(csv_path, t_slot, n_nodes=4) -> dict` (T2.5, done) | Replays a hardware or simulated per-slot CSV log through `MetricsTracker` so hardware and simulated runs are scored identically. You likely won't need to touch this in P3-P8, but `eval/run.py`'s CSV output format must stay compatible with it. |
| `sim/validate.py` | `validate_channel_success_curve(...)` (T2.6, done) | Self-consistency check of `ChannelModel`'s empirical delivery rate against its own configured analytic curve. Re-run this (`python -m sim.validate`) any time you touch `config/measured_params.yaml`'s `channel` section. |
| `tools/demo_sim_run.py` | A runnable demo driver for `NetworkSim` | Read this first — it's the clearest worked example of constructing `SimConfig`/`NetworkSim` and driving `step()` in a loop. |
| `ns3-sim/aoi-scheduler-sim.cc` | The already-validated C++ reference implementation of RR/FPQ/Max-Weight/CAG/Random + the shield | **Copy the exact scheduler formulas from here** (line numbers cited per-scheduler below) so the Python and NS-3 implementations can never silently diverge in behavior, only in language. Its shield/channel model are simpler (single logistic curve, no burst overlay) than `sim/channel.py`'s — that's expected, `ns3-sim` is the frozen review-demo reference for scheduler *decision logic*, not the channel physics. |
| `config/system.yaml` | All frozen hyperparameters: weights, thresholds, shield ceilings, DUI params, RL hyperparameters (`rl:` section), seeds | Read this before inventing any parameter. In particular `rl.lambda_energy` and `rl.lambda_waste` (currently `0.0`) are already-provisioned reward-shaping knobs — see P4 §2.2. |
| `config/measured_params.yaml` | PLACEHOLDER (non-hardware) channel/timing parameters, `channel:` + `timing:` sections | Every result this plan produces is a *simulation* result on placeholder parameters, not a hardware-validated one. The file's own header says so; say so again in every doc you write (see §7, "Honesty rule"). See `docs/P1_NS3_ESP32_DELAY_CHARACTERISATION.md` for how a real fit will eventually replace it. |

### Conventions (match the existing codebase exactly)

- No `__init__.py` files anywhere (the repo uses implicit namespace packages). Don't add them.
- No docstrings beyond a short one-liner unless a constraint is genuinely non-obvious. No inline comments explaining *what* code does — only *why*, and only when it would surprise a reader (see existing files, e.g. `sim/queue.py`, for the calibration).
- Tests are plain `pytest` functions (no test classes), one behavior per test, named `test_<behavior>`. Existing simulation-core tests use the `tests/test_sim_*.py` naming (`test_sim_channel.py`, `test_sim_queue.py`, `test_sim_network.py`, `test_sim_metrics.py`, `test_sim_replay.py`, `test_sim_validate.py`) — follow that pattern for new test files (e.g. `tests/test_schedulers.py`, `tests/test_rl_env.py`).
- Every new "authoritative" function (one that computes something contract-like: a reward, a schema, a wire format) gets exactly one definition. `tests/test_contract_hygiene.py`'s `SEARCH_DIRS` already covers `common`, `sim`, `schedulers`, `rl`, `eval`, `gateway`, `tools`, plus `tests`.
- Determinism: any stochastic component takes an explicit `np.random.Generator`, never touches `np.random`'s global state. `NetworkSim.reset(seed)` constructs its own `np.random.Generator(np.random.PCG64(seed))` — follow the same pattern in `rl/reference_dqn.py`'s replay buffer sampling, etc.
- After finishing each phase, update `task.md`: flip the task's status to `✅ DONE`, and update its Acceptance Criteria checkboxes. Follow the exact style already used for P0/P2's entries.
- Run `python -m pytest tests/ -q` after every phase and keep it green before moving to the next phase.

---

## 1. Phase P3 — Baseline Schedulers and Evaluation Harness

Implements `task.md` T3.1-T3.8.

### 1.1 Scheduler interface — `schedulers/base.py` (T3.1)

Every scheduler is a decision function over the current, *observable* network
state, plus whatever internal counters it needs (e.g. RR's slot counter). It never
sees delivery outcomes (those don't exist yet at decision time) and never applies
the safety shield itself — see §1.5's note on where the shield actually lives.

```python
from abc import ABC, abstractmethod
import numpy as np

class BaseScheduler(ABC):
    """A scheduler observes per-node AoI/RSSI/queue-occupancy/criticality-weight
    and returns the node index to grant this slot."""

    @abstractmethod
    def select(self, aoi: np.ndarray, rssi: np.ndarray, queue: np.ndarray,
               weights: np.ndarray) -> int:
        ...
```

`eval/run.py` (§1.6) is responsible for pulling these four arrays off a live
`NetworkSim` instance each slot: `sim.metrics.aoi`, `sim.rssi_observed`,
`np.array([q.has_data() for q in sim.queues])`, `sim.weights` — all are plain
public attributes, no new accessor needed. Construct each scheduler with whatever
static config it needs (weights/thresholds come from `config/system.yaml` via
`load_system_config()`, not hardcoded).

### 1.2 RR, FPQ, Random — `schedulers/round_robin.py`, `schedulers/fixed_priority.py`, `schedulers/random_scheduler.py` (T3.2)

Mirror `ns3-sim/aoi-scheduler-sim.cc`'s `RunScheduler()` exactly (lines 472-524):

- **RoundRobin**: internal `self._slot = 0` counter; `select()` returns `self._slot % n_nodes`, then increments. (`SCHED_RR` branch, line 477.)
- **FixedPriority**: class priority is Urgent=2, Important=1, Routine=0 (`ClassPriority`, lines 128-141 — derive this from `system.node_classes`, don't hardcode node indices). Among the highest-priority class, tie-break by highest current AoI (line 483-489).
- **RandomScheduler**: takes its own seeded `np.random.Generator` (constructor arg, never global RNG); `select()` draws a uniform node index (`SCHED_RANDOM`, line 520-521).

### 1.3 Max-Weight — `schedulers/max_weight.py` (T3.3)

`select()` returns `argmax(weights * aoi)` (lines 492-502).

### 1.4 Channel-Aware Greedy — `schedulers/channel_aware_greedy.py` (T3.4)

`select()` returns `argmax(weights * aoi * p_s(rssi))`, where `p_s` is
`sim.channel.success_probability_from_rssi(rssi, params)` — **reuse this function**,
don't recompute the logistic inline (mirrors `ns3-sim` lines 504-518, but note
`sim/channel.py`'s curve additionally sits under a Gilbert-Elliott burst overlay
that CAG, using only the *observed* RSSI, cannot see — that gap is deliberate, see
§1.5). Build a `ChannelParams` via `ChannelParams.from_measured_params(measured_params)`
once at construction time; don't re-parse the yaml per slot.

### 1.5 Oracle reference — `schedulers/oracle.py` (T3.5)

The Oracle is an **evaluation-only, non-deployable** upper-bound baseline that
knows the network's true, instantaneous channel quality — not the possibly-stale
`rssi` a real scheduler observes (RSSI is only refreshed on delivery or heartbeat,
per `NetworkSim._refresh_rssi`/D3.2/F2.5). Concretely:
`Oracle = argmax(weights * aoi * ChannelModel.success_probability(i))` using the
**true** channel state, vs. CAG's `argmax(weights * aoi * success_probability_from_rssi(observed_rssi))`
using the **staleness-limited** observed state. The gap between Oracle and CAG is
therefore a direct, reportable measurement of what RSSI staleness costs.

This requires one small, carefully-scoped refactor of `NetworkSim.step()`, which
currently does "advance channel/queue physics for the slot" and "resolve the
granted action's outcome" in one inseparable method body:

1. Split `step(action)`'s current body into two methods:
   - `advance_slot() -> None`: everything currently at the top of `step()` that
     doesn't depend on `action` — `self.channel.step(self.rng)`, the arrivals/aging
     loop, and (move this part from the bottom) the heartbeat RSSI-refresh loop.
   - `resolve(action) -> tuple[np.ndarray, dict]`: everything that *does* depend on
     `action` — the late-delivery/`draw_success`/queue-pop/`metrics.step`/
     `slot_idx` increment/observation-building logic.
   - `step(action)` becomes exactly `self.advance_slot(); return self.resolve(action)`
     — **behavior-preserving**: every existing test in `tests/test_sim_network.py`
     must keep passing unmodified after this refactor. Run them before and after to
     confirm.
2. Add `NetworkSim.true_success_probabilities() -> np.ndarray`: returns
   `np.array([self.channel.success_probability(i) for i in range(self.cfg.n_nodes)])`.
   Only valid to call after `advance_slot()` has run for the current slot and before
   the next call to `advance_slot()` — document this precondition in the docstring.
3. **Only an Oracle-driving code path may call `advance_slot()`/`resolve()`
   separately and read `true_success_probabilities()`.** Every other scheduler, and
   — critically — **`rl/env.py` (P4) must never call `true_success_probabilities()`**.
   Leaking ground-truth channel state into the DRL agent's observations would
   invalidate every P5/P6 result. Add a test asserting `rl/env.py` never imports or
   calls it.

`OracleScheduler` does **not** implement `BaseScheduler.select()`'s signature (it
needs `true_success_probabilities`, which no other scheduler gets — this is a
deliberate, documented exception given its eval-only role). Give it its own method,
e.g. `select_with_oracle(aoi, queue, weights, true_success_probs) -> int`:
`argmax(weights * aoi * true_success_probs)` among nodes with `queue[i] == 1`; if no
node has data buffered this slot, fall back to `argmax(weights * aoi)`. `eval/run.py`
(§1.6) special-cases the Oracle policy to call `sim.advance_slot()`, read
`sim.true_success_probabilities()`, call `select_with_oracle`, then
`sim.resolve(action)` — every other scheduler just calls `sim.step(action)`.

### 1.6 Evaluation harness — `eval/run.py` (T3.6)

A CLI/library entry point that:
1. Loads `config/system.yaml` and `config/measured_params.yaml`.
2. Builds `SimConfig.from_configs(system_config, measured_params, episode_length=config["rl"]["episode_length"])`
   and constructs `NetworkSim(sim_config)`, then `sim.reset(seed)`.
3. Constructs the requested scheduler (by name: `rr`, `fpq`, `maxweight`, `cag`,
   `random`, `oracle`).
4. Runs one episode's worth of slots (`sim_config.episode_length`, or an explicit
   `--n-slots` override), driving `sim.step(scheduler.select(...))` each slot for
   every non-Oracle scheduler (the Oracle path is special-cased per §1.5), and
   appending a row matching `common.contracts.log_schema.SLOT_LOG_COLUMNS` exactly
   (use `validate_slot_row()` in a test to enforce this — pull the row's fields from
   `info` plus the scheduler's chosen action, matching the same columns `ns3-sim`
   emits and `sim/replay.py` reads).
5. Writes the CSV to a per-run directory and calls
   `common.provenance.write_run_meta(run_dir, policy_id=<scheduler name>, seed=seed)`.
6. Supports running `config["scheduler"]["runs_per_condition"]` seeds per scheduler
   (config already lists `runs_per_condition: 10`; P5/P6 will reuse the seed lists
   under `config["rl"]["train_seeds"]`/`["eval_seeds"]` instead where specified).

### 1.7 Statistics + figures — `eval/stats.py` (T3.7)

- `criticality_weighted_mean_aoi_per_run(csv_path) -> float`: loads a run's CSV,
  computes `common.metrics.criticality_weighted_aoi` per row, averages over rows.
  (D6.1: this is the **primary** reporting statistic — always compute and report it,
  not just raw mean AoI.)
- A leaderboard table across schedulers with 95% confidence intervals (bootstrap
  over `runs_per_condition` seeds is fine — don't assume normality with only 10
  runs).

### 1.8 Pre-registration — `docs/EVAL_PROTOCOL.md` (T3.8)

Write this **before** any DQN numbers exist (P5). State, and freeze:
- The primary statistic (criticality-weighted mean AoI, D6.1) and the secondary
  ones you'll also report (wasted-slot rate, `total_energy` from `MetricsTracker`).
- The statistical test used to claim DQN beats a baseline (task.md requires
  `p < 0.05`; specify paired vs unpaired, and cite D6.2 — negative results
  (DQN vs CAG) get reported exactly as honestly as positive ones).
- Seeds: `train_seeds` for training, `eval_seeds` for evaluation — **never
  overlapping**, both already fixed in `config/system.yaml`.
- Note explicitly that all P3/P6 results in this document are on PLACEHOLDER
  `config/measured_params.yaml` (`common.provenance.get_params_source()` currently
  reports `"placeholder_pending_p1"`), pending the real P1 hardware campaign
  described in `docs/P1_NS3_ESP32_DELAY_CHARACTERISATION.md`.
- Note the existing flag in `task.md`'s P2 section: at the current placeholder
  `distances_m` (5/8/12/18m), every node's RSSI sits well above the logistic
  curve's sensitive region, so simulated PDR is ~95-96% everywhere with little
  channel-quality differentiation. This will flatten CAG's/Oracle's advantage over
  Max-Weight until `T2.7`'s load calibration or real P1 data changes the operating
  point — say so plainly in the leaderboard writeup rather than let a reader assume
  channel-awareness doesn't matter.

### Definition of done (P3)

- [ ] All 6 schedulers (`rr`, `fpq`, `maxweight`, `cag`, `random`, `oracle`)
      conformance-tested against the exact `ns3-sim` formulas cited above.
- [ ] `NetworkSim.step()` refactored into `advance_slot()`/`resolve()` with all of
      `tests/test_sim_network.py` still passing unmodified.
- [ ] `eval/run.py` produces schema-valid CSVs + `run_meta.json` for every scheduler.
- [ ] `docs/EVAL_PROTOCOL.md` written and frozen.
- [ ] A baseline leaderboard exists (even if just an `eval/stats.py`-generated table
      in a scratch output — P6 formalizes the final figure pack).
- [ ] `tests/test_schedulers.py` (new) covers each scheduler's decision formula with
      hand-computed expected outputs, plus a determinism test per scheduler.

---

## 2. Phase P4 — RL Environment Interface and Shielding Layer

Implements `task.md` T4.1-T4.5. Depends on P3 only for `rl/wrappers.py` (§2.5).

### 2.1 Shield — `rl/shield.py` (T4.3)

`NetworkSim` deliberately does not implement a safety shield (see its own
docstring: "It deliberately does NOT know about schedulers, rewards, or the safety
shield -- those are P3/P4 concerns layered on top"). This is the first thing P4
adds, as a standalone, single authoritative function — write it **before**
`rl/env.py` so the env can import it:

```python
# rl/shield.py
import numpy as np

def apply_safety_shield(proposed_action: int, aoi: np.ndarray,
                         weights: np.ndarray, shield_ceilings_s: np.ndarray) -> tuple[int, bool]:
    """Force-grants the highest-urgency ceiling violator, if any. Mirrors
    ns3-sim/aoi-scheduler-sim.cc's SlotTick shield block (lines 432-448)."""
    violations = aoi >= shield_ceilings_s
    if not np.any(violations):
        return proposed_action, False
    urgency = weights * aoi
    urgency_masked = np.where(violations, urgency, -np.inf)
    return int(np.argmax(urgency_masked)), True
```

Both `rl/env.py` (§2.2) and `eval/run.py` (P3 §1.6, for baseline evaluation runs
that should also be shielded — add this as a follow-up to P3 once `rl/shield.py`
exists) must call this same function before passing an action to
`NetworkSim.step()`. There must be exactly one definition of the shield decision.

### 2.2 Gym environment — `rl/env.py` (T4.1)

```python
import gymnasium as gym
import numpy as np
from gymnasium import spaces

from rl.shield import apply_safety_shield
from sim.network import NetworkSim, SimConfig

class AoiSchedulerEnv(gym.Env):
    """Gymnasium wrapper around sim.network.NetworkSim. Action = which node
    to grant this slot (the shield may override it); Observation = the
    frozen 16-D state vector NetworkSim already builds internally."""

    def __init__(self, system_config: dict, measured_params: dict, seed: int | None = None):
        n_nodes = system_config["system"]["n_nodes"]
        self.action_space = spaces.Discrete(n_nodes)
        self.observation_space = spaces.Box(low=0.0, high=1.0, shape=(16,), dtype=np.float32)

        self._sim_config = SimConfig.from_configs(
            system_config, measured_params, episode_length=system_config["rl"]["episode_length"])
        self._sim = NetworkSim(self._sim_config)
        self._shield_ceilings_s = np.array(
            [system_config["scheduler"]["shield_ceilings_s"][c]
             for c in system_config["system"]["node_classes"]])
        self._config = system_config

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        obs = self._sim.reset(seed if seed is not None else np.random.SeedSequence().entropy)
        return obs.astype(np.float32), {}

    def step(self, action):
        shielded_action, shield_fired = apply_safety_shield(
            action, self._sim.metrics.aoi, self._sim.weights, self._shield_ceilings_s)
        obs, info = self._sim.step(shielded_action)
        reward = shaped_reward(info, self._sim.weights, self._sim.thresholds_s, self._config)  # rl/reward.py, §2.3
        info["shield_fired"] = shield_fired
        info["action_before_shield"] = action
        return obs.astype(np.float32), reward, False, info.pop("truncated"), info
```

Key correctness requirements:
- `observation_space` bounds are `[0, 1]` because `NetworkSim._build_observation()`
  already goes through `NodeState.to_normalized_vector()`, which clips/normalizes
  every feature into that range — don't re-derive bounds.
- Episodes never `terminate` (`info["terminated"]` from `NetworkSim.step()` is
  always `False` — this is a continuing control problem, F2.7); they only
  `truncate` at `sim_config.episode_length` steps.
- `reset(seed=...)` delegates directly to `NetworkSim.reset(seed)`, which builds a
  fresh `np.random.Generator` — never reuse RNG state across episodes/resets.
- Run `gymnasium.utils.env_checker.check_env(AoiSchedulerEnv(...))` as an actual
  test (`tests/test_rl_env.py`) — this is a literal P4 acceptance criterion.

### 2.3 Reward — `rl/reward.py` (T4.2)

`NetworkSim.step()`'s `info` dict carries `aoi` (post-update, per-node array) but
not a queue-occupancy array or the DUI directly — build both here:

```python
from common.metrics import compute_dui, calculate_reward

def shaped_reward(info: dict, weights: np.ndarray, thresholds_s: np.ndarray, config: dict) -> float:
    aoi = info["aoi"]
    # queue occupancy isn't in `info`; the caller (rl/env.py) has `self._sim.queues`
    # available -- pass it in, or add `queue_status` to NetworkSim's info dict as a
    # small, additive extension (either is fine; prefer extending `info` so
    # eval/run.py's logging gets it too, matching log_schema's `queue_status` column).
    queue = info["queue_status"]  # see note above -- add this to NetworkSim.step()'s info dict
    sched = config["scheduler"]
    dui = compute_dui(aoi, queue, weights, thresholds_s,
                       alpha=sched["dui_alpha"], lambd=sched["dui_lambda"], beta=sched["dui_beta"])
    base = calculate_reward(dui)

    lambda_energy = config["rl"]["lambda_energy"]   # currently 0.0
    lambda_waste = config["rl"]["lambda_waste"]      # currently 0.0
    waste_penalty = 0.0 if info["packet_arrived"] else 1.0
    return base - lambda_energy * info.get("total_energy", 0.0) - lambda_waste * waste_penalty
```

With both lambdas at `0.0` (their current config value) this reduces to
`calculate_reward(compute_dui(...))` — verify that with a test. These knobs exist
for P6's sensitivity sweep (T6.4); don't change their default values here. Note the
small, additive `NetworkSim.step()` extension this needs (adding
`"queue_status": np.array([q.has_data() for q in self.queues])` to the `info` dict
in `resolve()`) — make this change once, in `sim/network.py`, not by duplicating
queue-status logic in `rl/reward.py`.

### 2.4 Observation decoding — `rl/obs.py` (T4.4)

`NetworkSim` already builds the 16-D observation; what P4 still needs is the
**inverse** — a way to recover raw `(aoi, rssi, queue, weights)` from a normalized
observation vector, for `rl/wrappers.py` (§2.5) to hand P3 schedulers their expected
inputs when evaluated through the Gym env instead of directly against `NetworkSim`:

```python
from common.contracts.state_spec import DELTA_MAX, W_MAX, RSSI_MIN, RSSI_RANGE

def decode_observation(obs: np.ndarray, n_nodes: int = 4) -> tuple[np.ndarray, ...]:
    """Inverse of NodeState.to_normalized_vector(), applied to all n_nodes
    at once. Must use the same constants as common.contracts.state_spec --
    import them, don't restate the numbers."""
    obs = obs.reshape(n_nodes, 4)
    aoi = obs[:, 0] * DELTA_MAX
    queue = obs[:, 1]
    rssi = obs[:, 2] * RSSI_RANGE + RSSI_MIN
    weights = obs[:, 3] * W_MAX
    return aoi, rssi, queue, weights
```

### 2.5 Baseline-parity wrapper — `rl/wrappers.py` (T4.5)

A thin adapter so a P3 `BaseScheduler` can be evaluated through the *same*
`AoiSchedulerEnv` + logging path as the trained DQN, guaranteeing apples-to-apples
comparison (same env RNG handling, same episode length, same shield, same log
schema):

```python
from rl.obs import decode_observation

class SchedulerPolicyWrapper:
    """Adapts a schedulers.base.BaseScheduler to look like an SB3-style policy
    (.predict(obs) -> (action, state)) so eval/run.py and P6's sweeps can drive
    baselines and the trained DQN through identical code paths."""
    def __init__(self, scheduler: "BaseScheduler"):
        self._scheduler = scheduler

    def predict(self, obs, deterministic=True):
        aoi, rssi, queue, weights = decode_observation(obs)
        return self._scheduler.select(aoi, rssi, queue, weights), None
```

### Definition of done (P4)

- [ ] `apply_safety_shield` has exactly one definition, used by both `rl/env.py`
      and (as a follow-up patch to P3) `eval/run.py`'s baseline runs.
- [ ] `gymnasium.utils.env_checker.check_env` passes.
- [ ] Observation is verifiably 16-D and matches `get_state_schema_hash()`.
- [ ] Shield activation rate `<5%` at nominal load (measured over a smoke run with
      a reasonable baseline policy, e.g. CAG — write this as a test with a generous
      threshold, not a strict benchmark).
- [ ] `rl/wrappers.py` lets every P3 scheduler run through `AoiSchedulerEnv`; write
      a parity test comparing its trajectory against driving the same scheduler
      directly against `NetworkSim` with the same seed (small numerical
      differences from the normalize/decode round-trip are expected — assert they
      stay within a tight tolerance, not bit-exact).
- [ ] `tests/test_rl_env.py` asserts `rl/env.py` never imports or calls
      `NetworkSim.true_success_probabilities()` (P3 §1.5's leakage guard).

---

## 3. Phase P5 — DQN Implementation and Training

Implements `task.md` T5.1-T5.8. Requires `pip install -e .[train,dev]` (installs
`torch`, `stable-baselines3`, `gymnasium` per `pyproject.toml`).

### 3.1 Training script — `rl/train.py` (T5.1)

Use Stable-Baselines3's `DQN` with `MlpPolicy`, reading every hyperparameter from
`config["rl"]` — do not hardcode any of these, they're already frozen in
`config/system.yaml`:

```python
from stable_baselines3 import DQN

model = DQN(
    "MlpPolicy", env,
    gamma=rl_cfg["gamma"], learning_rate=rl_cfg["learning_rate"],
    buffer_size=rl_cfg["buffer_size"], batch_size=rl_cfg["batch_size"],
    target_update_interval=rl_cfg["target_update_interval"],
    exploration_initial_eps=rl_cfg["eps_start"], exploration_final_eps=rl_cfg["eps_end"],
    exploration_fraction=rl_cfg["eps_fraction"],
    policy_kwargs={"net_arch": rl_cfg["net_arch"]},
    tensorboard_log="runs/",
    seed=seed,
)
model.learn(total_timesteps=rl_cfg["total_timesteps"], callback=[...])  # P5.3's callback
model.save(f"models/dqn_seed{seed}")
```

CLI should accept `--seed` (loop over `config["rl"]["train_seeds"]` = `[0,1,2,3,4]`
for the final runs, T5.5) and write `run_meta.json` per run via
`common.provenance.write_run_meta`.

### 3.2 Divergence monitor — `rl/monitors.py` (T5.2)

An SB3 `BaseCallback` that watches the training loss / mean Q-value each
`target_update_interval` and flags (log a warning, optionally stop early) on NaN/Inf
loss or a Q-value magnitude blowing up past a sane bound (derive the bound from the
DUI formula's max plausible value given `config["scheduler"]`'s weights/thresholds,
don't pick an arbitrary constant).

### 3.3 Periodic evaluation callback — `rl/callbacks.py` (T5.3)

An SB3 `BaseCallback` that, every N training steps, runs the current policy against
`config["rl"]["eval_seeds"]` (the 20 seeds `100-119` — **disjoint from
`train_seeds`**, this is a literal T5.1 acceptance criterion) via `AoiSchedulerEnv`,
and logs the criticality-weighted mean AoI to TensorBoard.

### 3.4 Hyperparameter sweep — `rl/sweep.py` (T5.4)

A small grid/random search (a handful of runs, not an expensive campaign) over 2-3
of the most sensitive hyperparameters (e.g. `learning_rate`, `net_arch`,
`dui_lambda`/`dui_beta`). Log results to compare; this informs but doesn't have to
replace the frozen `config/system.yaml` defaults for the final runs unless you find
a clearly better setting — if you do change a default, note why in `docs/TRAINING.md`.

### 3.5 Final training runs (T5.5)

Actually execute `rl/train.py` for all 5 `train_seeds`. This is compute (not
hardware) — run it. Save all 5 models under `models/`.

### 3.6 Cross-check agent — `rl/reference_dqn.py` (T5.6)

An independent, from-scratch DQN (plain PyTorch, no SB3): experience replay
buffer, target network, epsilon-greedy schedule matching the same
`config["rl"]` hyperparameters, small 2-layer MLP (`net_arch`). Train it on the
same env/seeds. Compare its final criticality-weighted mean AoI against SB3's —
**must be within 15%** (T5.1 acceptance criterion). This exists to catch an SB3-
specific bug or config-parsing mistake that both implementations would otherwise
share silently.

### 3.7 Ablations — `rl/ablations.py` (T5.7)

Re-train (fewer seeds is fine, e.g. 2-3) with individual pieces removed/altered to
isolate their contribution:
- State without the criticality-weight feature (revert to a pre-F4.1-style 12-D
  state) — does performance degrade on a live-escalation scenario?
- Reward without the non-linear DUI penalty term (`dui_lambda=0`) — does the agent
  still avoid threshold violations?
- Shield disabled entirely (evaluation-only, never disable it during training) —
  how much does the shield actually change outcomes vs. a well-trained unshielded
  policy?

### 3.8 Training report — `docs/TRAINING.md` (T5.8)

Document: hyperparameters used, all 5 seeds' learning curves, the cross-check
agent's agreement with SB3, the ablation results, and — per D6.2 — **the DQN vs
CAG comparison reported exactly as it came out**, whether DQN wins, loses, or ties.
`F5.2` in `AoI_DRL_Scheduler_Engineering_Blueprint.md` already flags that CAG (using
the *true* `p_s(RSSI)` model) may be a very strong baseline the DQN doesn't beat;
that is a legitimate, reportable outcome, not a bug to hide.

### Definition of done (P5)

- [ ] 5 seeds trained, all runs traceable via `run_meta.json`.
- [ ] Eval seeds strictly disjoint from train seeds (assert this in a test, not just
      by inspection — compare `set(config["rl"]["train_seeds"])` and
      `set(config["rl"]["eval_seeds"])`).
- [ ] Cross-check agent's result within 15% of SB3's.
- [ ] Statistical test (from `docs/EVAL_PROTOCOL.md`, P3) run comparing DQN against
      RR and FPQ, `p < 0.05` claimed only if actually true.
- [ ] DQN vs CAG result written up honestly in `docs/TRAINING.md`, win or lose.

---

## 4. Phase P6 — Evaluation, Ablation, and Sensitivity (Simulation)

Implements `task.md` T6.1-T6.7. Mostly "run the P3 harness at scale over
everything P5 produced, with proper statistics" — most of the machinery already
exists from P3.

### 4.1 Main sweep — extend `eval/run.py` (T6.1)

Run every P3 baseline + the 5 trained DQN models (via `rl/wrappers.py` for
baselines, direct `model.predict()` for DQN, both through `AoiSchedulerEnv` so the
shield applies uniformly) across `runs_per_condition` (10) seeds each, under the
nominal load condition from `config/system.yaml`.

### 4.2 Generalisation battery — extend `eval/run.py` (T6.2)

Re-run the best DQN model(s) under conditions **not** seen during training: e.g.
perturbed `weights`/`thresholds`, a different `distances_m` set passed to
`NetworkSim(sim_config, distances_m=...)` (rather than the default radial
placement), different `heartbeat_period_s`. This checks for overfitting to the
exact training config.

### 4.3 Ablation table — `eval/stats.py` (T6.3)

Format P5.7's ablation results into a comparison table (criticality-weighted mean
AoI, shield activation rate, wasted-slot rate, per variant).

### 4.4 Weight sensitivity — `eval/stats.py` (T6.4)

Sweep `dui_alpha`, `dui_lambda`, `dui_beta` (and separately, the class weights
`urgent`/`important`/`routine`) across a small grid, re-evaluating a fixed trained
model or a baseline scheduler, and plot how the primary statistic moves. Also worth
sweeping here (per the P2 note in `task.md`): the placeholder `distances_m`, to
show how CAG's/Oracle's advantage over Max-Weight changes once nodes aren't all
sitting in the logistic curve's saturated region.

### 4.5 Statistics module — `eval/stats.py` (T6.5)

- Bootstrap or t-test confidence intervals for every leaderboard entry (from P3.7,
  now applied at full scale).
- **Shuffled-label control**: re-run the significance test with scheduler labels
  randomly permuted across runs; this must come back non-significant (`p >= 0.05`)
  — it's a sanity check that your statistical test isn't spuriously significant by
  construction. This is a literal P6 acceptance criterion.

### 4.6 Figure pack — `eval/figures.py` (T6.6)

Matplotlib figures, each regenerable by one command (a literal acceptance
criterion): leaderboard bar chart with CIs, AoI-over-time traces per scheduler,
shield activation rate comparison, training curves (from TensorBoard logs),
ablation table as a figure, sensitivity sweep plots.

### 4.7 Results doc — `docs/RESULTS_SIM.md` (T6.7)

Full write-up tying together P3's leaderboard, P5's training report, and P6's
ablation/sensitivity/generalisation results. State prominently, at the top: these
are simulation results on PLACEHOLDER `config/measured_params.yaml` parameters
(cite this file's header and `docs/P1_NS3_ESP32_DELAY_CHARACTERISATION.md`),
pending the real P1 hardware campaign and the D11.1 sim-to-real comparison that
will follow it.

### Definition of done (P6)

- [ ] All sweeps (main, generalisation, ablation, sensitivity) complete with CIs.
- [ ] Shuffled-label control is non-significant.
- [ ] Every figure in `docs/RESULTS_SIM.md` is regenerable by one documented
      command.

---

## 5. Phase P7 — Model Export and NumPy Inference Parity

Implements `task.md` T7.1-T7.5. This is pure software — no hardware needed except
for T7.4's final on-device number, which stays deferred (see below).

### 5.1 Export — `deploy/export.py` (T7.1)

Extract a trained SB3 `DQN` model's Q-network into a plain `.npz`: weight/bias
arrays per layer, `net_arch`, activation name, and — critically —
`get_state_schema_hash()` (from `common.contracts.state_spec`) embedded as metadata,
so a mismatched artifact can be detected at load time rather than silently producing
wrong Q-values (this is exactly what T7.5's negative test checks).

```python
def export_model(model: "DQN", output_path: str):
    q_net = model.q_net  # SB3's QNetwork
    layers = [(l.weight.detach().numpy(), l.bias.detach().numpy())
              for l in q_net.q_net if hasattr(l, "weight")]
    np.savez(output_path,
             **{f"w{i}": w for i, (w, b) in enumerate(layers)},
             **{f"b{i}": b for i, (w, b) in enumerate(layers)},
             n_layers=len(layers),
             state_schema_hash=get_state_schema_hash())
```

### 5.2 NumPy inference — `deploy/infer.py` (T7.2)

A pure-NumPy forward pass matching SB3's default `QNetwork` architecture exactly:
linear layers with ReLU activations between them, no activation on the final
(Q-value) output layer.

```python
def infer(params: dict, obs: np.ndarray) -> np.ndarray:
    x = obs
    n_layers = int(params["n_layers"])
    for i in range(n_layers):
        x = x @ params[f"w{i}"].T + params[f"b{i}"]
        if i < n_layers - 1:
            x = np.maximum(x, 0.0)  # ReLU
    return x  # Q-values per action
```

### 5.3 Parity gate — `tests/test_parity.py` (T7.3)

Load a trained model both ways (`model.q_net(torch_obs)` vs
`deploy.infer.infer(np.load(exported_path), obs)`) on a batch of representative
observations (random valid 16-D vectors, plus edge cases: all-zero AoI, max AoI,
one node at its shield ceiling). Assert `max(abs(delta_q)) < 1e-5` and 100%
`argmax` agreement (the actual action selection, which is what matters
operationally, must match every time even if raw Q-values have tiny float
differences).

### 5.4 Pi benchmark — `tools/bench_infer.py` (T7.4)

Write the benchmark harness (times `deploy.infer.infer()` over many calls, reports
P50/P99 latency) and **run it on the laptop now** to get a software-only number.
**Do not claim the "<5ms on-Pi P99" acceptance criterion is met** — that specific
number requires a real Raspberry Pi Zero 2W and stays unverified until hardware
arrives. Say so explicitly in the benchmark's output/report.

### 5.5 Negative test — `tests/test_parity.py` (T7.5)

Corrupt an exported artifact's `state_schema_hash` (or omit it) and assert
`deploy/infer.py`'s loader raises a clear, specific error rather than silently
producing (wrong) Q-values.

### Definition of done (P7)

- [ ] Parity gate green: `max|ΔQ| < 1e-5`, 100% action agreement, across a
      representative + edge-case observation batch.
- [ ] Laptop-measured inference latency reported (Pi-specific `<5ms` claim
      explicitly deferred, not fabricated).
- [ ] Mismatched/corrupted artifacts are rejected with a clear error.

---

## 6. Phase P8 — ESP32 Node Firmware

Implements `task.md` T8.1-T8.7 (**not** T8.8 bring-up — that needs real hardware
and stays `🔴 BLOCKED`). This phase produces firmware that **builds and passes unit
tests**, ready to flash. Note the team currently *does* have ESP32 boards (just not
a Raspberry Pi — see `docs/P1_NS3_ESP32_DELAY_CHARACTERISATION.md`), so bring-up may
in fact be unblockable sooner than P9/P11; that's still out of this document's scope.

### ⚠️ Decision already partially made by the P1 substitute doc

`docs/P1_NS3_ESP32_DELAY_CHARACTERISATION.md`'s T1.1 firmware section already
assumes ESP-IDF-style APIs (`esp_wifi_set_ps`, `esp_timer_get_time`,
`esp_wifi_sta_get_ap_info`) for the timing-spike firmware. **Use ESP-IDF for P8's
node firmware too**, for consistency with that already-written spike firmware and
because T8.2-T8.4 describe three separate FreeRTOS tasks (network/sensor/heartbeat),
which fits ESP-IDF's native task model directly.

### 6.0 Prerequisite: finish the packet contract — `common/contracts/packets.py`

The file currently has `GrantPacket` fully implemented but a literal
`# TODO: Add DATA, HEARTBEAT, HELLO, CONTROL models similarly`. The firmware's
network task (§6.2) needs all of these on the wire. Fill them in, mirroring
`GrantPacket`'s exact pattern (header + payload `struct.pack`, CRC16 appended):
- `DataPacket`: node's reply to a GRANT — needs `age_at_tx_us` (D2.1) and the
  `alarm_ack`/`FLAG_ALARM_ACK` bit (already defined at the top of the file).
- `HeartbeatPacket`: unsolicited, per D3.2 (2s period + jitter) — carries `node_id`
  and flags (e.g. `FLAG_SENSOR_FAULT`, `FLAG_POST_REBOOT`) plus an RSSI reading
  (the spike firmware's `spike_reply_t` in the P1 substitute doc already has a
  precedent field layout for this — reuse the same field order/types where they
  overlap, for firmware-code reuse between the timing spike and the real node).
- `HelloPacket`: sent once on association/reboot, so the gateway can detect
  `FLAG_POST_REBOOT`.
- `ControlPacket`: gateway-to-node, minimal payload (a command-code byte is enough
  for now — nothing downstream depends on it except the alarm ack path).

Add `tests/test_packets.py` cases for each (pack/unpack round-trip, CRC validation)
matching the existing `GrantPacket` test pattern already in that file.

### 6.1 Skeleton + build — `firmware/node/` (T8.1)

A single firmware source tree that builds **one binary** configurable (via
`sdkconfig`/build-time define, e.g. `CONFIG_NODE_ID`) to become any of the 4 node
roles — this is a literal acceptance criterion ("4 images from 1 source"), not 4
separate codebases. Node class (`urgent`/`urgent`/`important`/`routine`) and
therefore its weight/threshold/shield-ceiling should be derivable from `node_id` +
the same `config/system.yaml` values already frozen in Python (mirror the constants,
don't invent new ones — match `NODE_CLASSES`/`WEIGHTS`/`SHIELD_CEILING` exactly as
`ns3-sim/aoi-scheduler-sim.cc` lines 50-56 already do in C++).

### 6.2 Network task — `firmware/node/` (T8.2)

FreeRTOS task implementing the exact grant-reply protocol already validated by
`ns3-sim`'s `IoTSensorApp` (lines 149-266): bind a UDP socket for GRANT packets
(port `udp_port_grant` from `config/system.yaml`'s `network:` section), on receipt
check the local LCFS-1 buffer (§6.3) and reply with a `DataPacket` over
`udp_port_uplink` if occupied. **0 foreign-grant replies in 10k slots** is a literal
acceptance criterion — validate the GRANT's target `node_id` before replying. Also
mandatory: `esp_wifi_set_ps(WIFI_PS_NONE)` before `wifi_start()` (D1.3; the P1
substitute doc already flags this exact call as critical — F1.3).

### 6.3 Sensor task — `firmware/node/` (T8.3)

10 Hz periodic task that overwrites the single-slot LCFS buffer — mirror
`sim/queue.py`'s `NodeQueue` (LCFS mode) semantics exactly (a fresh sample always
overwrites; the alarm latch, once set, survives being overwritten by a later
non-alarm sample and is cleared only by an explicit ack via `clear_alarm()`). The
Python version in `sim/queue.py` is the reference semantics to replicate in C, even
though it can't be imported directly.

### 6.4 Heartbeat task — `firmware/node/` (T8.4)

Periodic unsolicited `HeartbeatPacket` every `heartbeat_period_s` (2.0s, from
config) plus small random jitter, matching `ns3-sim`'s `SendHeartbeat` (lines
238-248, ±0.2s jitter) — this is what keeps the gateway's RSSI estimate warm for a
starved node (F3.2 in the blueprint, and the same staleness `NetworkSim`'s
heartbeat-refresh logic already models in software).

### 6.5 Diagnostics — `firmware/node/` (T8.5)

Sensor-fault detection (set `FLAG_SENSOR_FAULT` on read failure/out-of-range
value), TX failure counters, exposed via the heartbeat's flags byte.

### 6.6 Reconnection state — `firmware/node/` (T8.6)

WiFi disconnect/reconnect handling: on reassociation after a drop, send a
`HelloPacket` with `FLAG_POST_REBOOT` set so the gateway knows to treat this node's
prior AoI/RSSI state as stale rather than trusting a silently-resumed stream.

### 6.7 Firmware unit tests — `firmware/tests/` (T8.7)

Host-side unit tests (ESP-IDF's native/host test target, or an equivalent
Unity-based host build) for the logic that doesn't need real hardware: packet
pack/unpack + CRC round-trips (mirroring `tests/test_packets.py`), LCFS overwrite +
alarm-latch-survives-overwrite behavior (mirroring `tests/test_sim_queue.py`'s
exact semantics), node-role-from-`node_id` derivation. **No hardware needed for any
of this** — it's pure logic testable on the host.

### 6.8 Bring-up — **out of scope, stays blocked in this document**

Do not attempt T8.8 here (even though the team's ESP32 hardware may make it
reachable sooner than P9/P11 — that's a separate, later task, not part of this
P3-P8 handoff). Document in `task.md` that firmware is built/tested and ready;
actual bring-up is tracked separately.

### Definition of done (P8)

- [ ] `common/contracts/packets.py`'s TODO is resolved: `DataPacket`,
      `HeartbeatPacket`, `HelloPacket`, `ControlPacket` implemented and tested.
- [ ] One firmware source tree builds 4 distinct node images via a build-time
      config value, all sharing one codebase.
- [ ] Host-side unit tests pass for packet framing and LCFS/alarm-latch logic.
- [ ] `task.md` T8.1-T8.7 marked done; T8.8 explicitly left `🔴 BLOCKED`.

---

## 7. Cross-cutting rules for the whole plan

1. **Honesty rule.** Every doc this plan produces (`docs/EVAL_PROTOCOL.md`,
   `docs/TRAINING.md`, `docs/RESULTS_SIM.md`) must state at the top that its
   numbers come from PLACEHOLDER `config/measured_params.yaml` parameters (check
   `common.provenance.get_params_source()` at the time of writing), not real
   hardware. Never let a results doc read as if it's hardware-validated.
2. **No duplicate authoritative logic.** Before writing any function that computes
   AoI, the DUI/reward, the state vector, the shield decision, or the wire format —
   check §0's table first. If it already exists, import it.
3. **Test as you go**, not at the end of each phase. `python -m pytest tests/ -q`
   should stay green throughout; don't accumulate a backlog of broken tests across
   phases.
4. **Update `task.md`** at the end of each phase (not each task) so status is easy
   to review in one diff per phase.
5. **This work is hardware-agnostic** — none of P3-P8 (except T8.8, explicitly
   excluded) needs physical ESP32/Pi hardware. If you find yourself blocked on
   "needs real hardware," you've likely wandered into P9/P11/P12 scope, which this
   document deliberately excludes — stop and flag it rather than approximating it.
