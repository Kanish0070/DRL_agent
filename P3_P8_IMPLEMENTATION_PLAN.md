# P3-P8 Implementation Plan

**Audience:** a teammate's coding agent picking up this repo cold. This document is
self-contained — it names exact files, exact interfaces to match, exact formulas
(taken from the already-validated `ns3-sim/` reference implementation), and exact
acceptance criteria. Read this whole document before writing any code; the phases
depend on each other in the order given.

**Scope:** P3 (baseline schedulers + eval harness) through P8 (ESP32 firmware code).
This picks up immediately after P0 (frozen contracts) and P2 (Python simulation core),
both already done. **Do not implement P1, P9, P10, P11, P12** — those are out of scope
for this document (P1 is hardware-blocked; P9-P12 depend on hardware bring-up or on
work not covered here).

---

## 0. Orientation: what already exists, and what you must reuse

Do not reimplement any of the following. Import them.

| Module | What it owns | Why it matters here |
|---|---|---|
| `common/contracts/aoi.py` | `update_aoi_for_slot`, `compute_delivered_age` — the **one** authoritative AoI update rule | `tests/test_contract_hygiene.py` fails the build if this logic is redefined anywhere else in `common/`, `sim/`, `schedulers/`, `rl/`, `eval/`, `gateway/`, `tools/`, or `tests/`. Never inline AoI math. |
| `common/contracts/state_spec.py` | `NodeState`, `NetworkState`, `get_state_schema_hash()` — the frozen 16-D state layout (4 nodes × [aoi_norm, queue_norm, rssi_norm, weight_norm]) | P4's Gym env observation and P7's export/parity gate both key off `get_state_schema_hash()` to detect train/deploy mismatches. |
| `common/contracts/packets.py` | Wire format, CRC16-CCITT, `PacketHeader`, `GrantPacket` | Has an unfinished `# TODO: Add DATA, HEARTBEAT, HELLO, CONTROL models similarly`. **You must finish this** before P8's network task can serialize real packets — see P8 §7.0 below. This is filling a documented gap, not reopening the frozen P0 contract review. |
| `common/contracts/log_schema.py` | `SLOT_LOG_COLUMNS`, `validate_slot_row`, JSONL event type constants | P3's eval harness (`eval/run.py`) must emit rows matching this schema exactly. |
| `common/config.py` | `load_system_config()`, `load_measured_params()` | Single source of truth for every parameter. Never hardcode a value that's already in `config/system.yaml` or `config/measured_params.yaml`. |
| `common/metrics.py` | `compute_dui`, `calculate_reward`, `criticality_weighted_aoi` | The one authoritative urgency/reward metric (Dynamic Urgency Index, see `criticality_metric_plan.md`). P4's reward function must call this, not reimplement it. |
| `common/provenance.py` | `generate_run_meta`, `write_run_meta`, `get_params_source` | Every run this plan produces (eval sweeps, training runs) must call `write_run_meta()` so results are traceable to which `params_source` (currently `ns3_derived_placeholder`) produced them. See `docs/PARAM_PROVENANCE.md`. |
| `sim/channel.py` | `ChannelModel`, `delivery_probability` — logistic p_s(RSSI) | P3's Channel-Aware-Greedy and Oracle schedulers use this directly. |
| `sim/queue.py` | `LcfsAlarmQueue` — LCFS-1 buffer with sticky alarm latch | Internal to `sim/network.py`; you shouldn't need to touch this. |
| `sim/network.py` | `NetworkSimulator`, `SlotResult` — the fast (>=1e4 slots/sec) slot simulator | **This is what every scheduler and the RL env run against.** See its docstring; `step(action: int) -> SlotResult` is the entire interface. Needs one extension for P3's Oracle — see P3 §3.5. |
| `ns3-sim/aoi-scheduler-sim.cc` | The already-validated C++ reference implementation of RR/FPQ/Max-Weight/CAG/Random + the shield | **Copy the exact formulas from here for P3's schedulers** (line numbers cited per-scheduler below) so the Python and NS-3 implementations can never silently diverge in behavior, only in language. |
| `config/system.yaml` | All frozen hyperparameters: weights, thresholds, shield ceilings, DUI params, RL hyperparameters (`rl:` section), seeds | Read this before inventing any parameter. In particular `rl.lambda_energy` and `rl.lambda_waste` (currently `0.0`) are already-provisioned reward-shaping knobs — see P4 §4.2. |
| `config/measured_params.yaml` + `docs/PARAM_PROVENANCE.md` | Provisional (non-hardware) channel/timing parameters | Every result this plan produces is a *simulation* result on provisional parameters, not a hardware-validated one. Say so in every doc you write (see §9, "Honesty rule"). |

### Conventions (match the existing codebase exactly)

- No `__init__.py` files anywhere (the repo uses implicit namespace packages). Don't add them.
- No docstrings beyond a short one-liner unless a constraint is genuinely non-obvious. No inline comments explaining *what* code does — only *why*, and only when it would surprise a reader (see existing files for the calibration).
- Tests are plain `pytest` functions (no test classes), one behavior per test, named `test_<behavior>`. Put new test files directly in `tests/`.
- Every new "authoritative" function (one that computes something contract-like: a reward, a schema, a wire format) gets exactly one definition. If `tests/test_contract_hygiene.py`'s `SEARCH_DIRS` list doesn't yet cover a new top-level directory you add (it currently covers `common`, `sim`, `schedulers`, `rl`, `eval`, `gateway`, `tools`, plus `tests`), you don't need to touch it — `schedulers/`, `rl/`, `eval/` are already listed.
- Determinism: any stochastic component takes an explicit `np.random.Generator` (via `np.random.default_rng(seed)`), never touches `np.random`'s global state. `sim/channel.py` and `sim/network.py` already do this — follow the same pattern in `rl/reference_dqn.py`'s replay buffer sampling, etc.
- After finishing each phase, update `task.md`: flip the task's status to `✅ DONE`, and update its Acceptance Criteria checkboxes. Follow the exact style already used for P0/P2's entries (including provisional caveats where relevant, e.g. "✅ DONE (params provisional, see P1′)").
- Run `python -m pytest tests/ -q` after every phase and keep it green before moving to the next phase.

---

## 1. Phase P3 — Baseline Schedulers and Evaluation Harness

Implements `task.md` T3.1-T3.8.

### 3.1 Scheduler interface — `schedulers/base.py` (T3.1)

Every scheduler is a stateless-per-call decision function over the current network
state, plus whatever internal counters it needs (e.g. RR's slot counter). Define:

```python
from abc import ABC, abstractmethod
import numpy as np

class BaseScheduler(ABC):
    """A scheduler observes per-node AoI/RSSI/queue-occupancy/criticality-weight
    and returns the node index to grant this slot. It never sees delivery
    outcomes (those don't exist yet at decision time) and never mutates the
    simulator -- sim.network.NetworkSimulator.step() owns the shield override,
    so a scheduler's returned action can be legally overridden."""

    @abstractmethod
    def select(self, aoi: np.ndarray, rssi: np.ndarray, queue: np.ndarray,
               weights: np.ndarray) -> int:
        ...
```

Every concrete scheduler below implements `select()`. Construct each with whatever
static config it needs (weights/thresholds come from `config/system.yaml` via
`load_system_config()`, not hardcoded).

### 3.2 RR, FPQ, Random — `schedulers/round_robin.py`, `schedulers/fixed_priority.py`, `schedulers/random_scheduler.py` (T3.2)

Mirror `ns3-sim/aoi-scheduler-sim.cc`'s `RunScheduler()` exactly (lines 472-524):

- **RoundRobin**: internal `self._slot = 0` counter; `select()` returns `self._slot % n_nodes`, then increments. (`SCHED_RR` branch, line 477.)
- **FixedPriority**: class priority is Urgent=2, Important=1, Routine=0 (`ClassPriority`, lines 128-141 — derive this from `system.node_classes`, don't hardcode node indices). Among the highest-priority class, tie-break by highest current AoI (line 483-489).
- **RandomScheduler**: takes its own seeded `np.random.Generator` (constructor arg, never global RNG); `select()` draws a uniform node index (`SCHED_RANDOM`, line 520-521).

### 3.3 Max-Weight — `schedulers/max_weight.py` (T3.3)

`select()` returns `argmax(weights * aoi)` (lines 492-502).

### 3.4 Channel-Aware Greedy — `schedulers/channel_aware_greedy.py` (T3.4)

`select()` returns `argmax(weights * aoi * p_s(rssi))`, where `p_s` is
`sim.channel.delivery_probability(rssi, r50_dbm, beta_db)` — **reuse this function**,
don't recompute the logistic inline (lines 504-518). `r50_dbm`/`beta_db` come from
`load_measured_params()["channel"]`.

### 3.5 Oracle reference — `schedulers/oracle.py` (T3.5)

The Oracle is an **evaluation-only, non-deployable** upper-bound baseline with
perfect foreknowledge of this slot's delivery outcome for every node (real
schedulers only ever see the last-sampled RSSI, not whether a transmission would
actually succeed). This requires one small, carefully-scoped extension to
`sim/network.py`:

1. Add `NetworkSimulator.peek_slot_outcomes() -> np.ndarray` (dtype bool, shape
   `(n_nodes,)`). It must sample this slot's RSSI (`self.channel.sample_rssi()`)
   and then draw **one** Bernoulli outcome per node (reusing
   `sim.channel.delivery_probability` + `self.rng`/`self.channel.rng`), caching the
   result on `self` (e.g. `self._cached_outcomes`, `self._cached_outcomes_slot_id`).
2. Modify `step(action)` so that if `peek_slot_outcomes()` was already called for
   the *current* slot, it reuses the cached RSSI/outcomes instead of re-sampling
   (this is required for determinism — calling `peek` then `step` must not double-draw
   from the RNG, or the Oracle's decision and the actual applied outcome would be
   inconsistent, and reruns with the same seed would no longer be bitwise identical).
   If `peek_slot_outcomes()` was *not* called this slot, `step()` behaves exactly as
   it does today (samples once, uses immediately).
3. **Only `schedulers/oracle.py` may call `peek_slot_outcomes()`.** No other
   scheduler, and — critically — **`rl/env.py` (P4) must never call it**. Leaking
   ground-truth outcome data into the DRL agent's observations would invalidate
   every P5/P6 result. Add a test in `tests/test_network_simulator.py` asserting
   `NetworkSimulator`'s public step-facing state never exposes cached outcomes
   through anything the Gym env touches (e.g. assert `rl/env.py`'s observation
   builder path doesn't import or call `peek_slot_outcomes`).

`OracleScheduler.select()`: among nodes whose peeked outcome is `True`, return
`argmax(weights * aoi)`; if no node would succeed this slot, fall back to
`argmax(weights * aoi * p_s(rssi))` (same formula as Channel-Aware-Greedy) so the
Oracle still makes a sane choice on an all-fail slot.

### 3.6 Evaluation harness — `eval/run.py` (T3.6)

A CLI/library entry point that:
1. Loads `config/system.yaml` and `config/measured_params.yaml`.
2. Constructs a `sim.network.NetworkSimulator(config, measured_params, seed)`.
3. Constructs the requested scheduler (by name: `rr`, `fpq`, `maxweight`, `cag`,
   `random`, `oracle`).
4. Runs `config["scheduler"]["run_duration_s"] / measured_params["channel"]["t_slot_s"]`
   slots (or an explicit `--n-slots` override), calling `sim.step(scheduler.select(...))`
   each slot and appending a row matching `common.contracts.log_schema.SLOT_LOG_COLUMNS`
   exactly (use `validate_slot_row()` in a test to enforce this).
5. Writes the CSV to a per-run directory and calls
   `common.provenance.write_run_meta(run_dir, policy_id=<scheduler name>, seed=seed)`.
6. Supports running `config["scheduler"]["runs_per_condition"]` seeds per scheduler
   (config already lists `runs_per_condition: 10`; P5/P6 will reuse the seed lists
   under `config["rl"]["train_seeds"]`/`["eval_seeds"]` instead where specified).

### 3.7 Statistics + figures — `eval/stats.py` (T3.7)

- `criticality_weighted_mean_aoi_per_run(csv_path) -> float`: loads a run's CSV,
  computes `common.metrics.criticality_weighted_aoi` per row, averages over rows.
  (D6.1: this is the **primary** reporting statistic — always compute and report it,
  not just raw mean AoI.)
- A leaderboard table across schedulers with 95% confidence intervals (bootstrap
  over `runs_per_condition` seeds is fine — don't assume normality with only 10
  runs).
- Shield activation rate per scheduler (`shield_fired` column mean).

### 3.8 Pre-registration — `docs/EVAL_PROTOCOL.md` (T3.8)

Write this **before** any DQN numbers exist (P5). State, and freeze:
- The primary statistic (criticality-weighted mean AoI, D6.1) and the secondary
  ones you'll also report.
- The statistical test used to claim DQN beats a baseline (task.md requires
  `p < 0.05`; specify paired vs unpaired, and cite D6.2 — negative results
  (DQN vs CAG) get reported exactly as honestly as positive ones).
- Seeds: `train_seeds` for training, `eval_seeds` for evaluation — **never
  overlapping**, both already fixed in `config/system.yaml`.
- Note explicitly that all P3/P6 results in this document are on
  `params_source: ns3_derived_placeholder` (see `docs/PARAM_PROVENANCE.md`) until
  P1 lands.

### Definition of done (P3)

- [ ] All 6 schedulers (`rr`, `fpq`, `maxweight`, `cag`, `random`, `oracle`)
      conformance-tested against the exact `ns3-sim` formulas cited above.
- [ ] `eval/run.py` produces schema-valid CSVs + `run_meta.json` for every scheduler.
- [ ] `docs/EVAL_PROTOCOL.md` written and frozen.
- [ ] A baseline leaderboard exists (even if just an `eval/stats.py`-generated table
      in a scratch output — P6 formalizes the final figure pack).
- [ ] `tests/test_schedulers.py` (new) covers each scheduler's decision formula with
      hand-computed expected outputs, plus a determinism test per scheduler.

---

## 2. Phase P4 — RL Environment Interface and Shielding Layer

Implements `task.md` T4.1-T4.5. Depends on P3 only for `rl/wrappers.py` (§2.5).

### 4.0 First: extract the shield into its own authoritative module

`sim/network.py` currently implements the safety-shield override as a private
method, `NetworkSimulator._apply_shield()`. Before writing `rl/shield.py`, **move
that logic** into a new, single authoritative function:

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

Then change `sim/network.py`'s `step()` to import and call `rl.shield.apply_safety_shield`
instead of its own `_apply_shield` method (delete the method). This avoids the same
"two definitions of the same safety-critical logic" problem `common/contracts/aoi.py`
was designed to prevent — `sim/network.py` (P2, already built) and `rl/env.py` (P4,
this phase) must never be able to silently disagree about when the shield fires.
Add a test to `tests/test_contract_hygiene.py`'s pattern (or a new dedicated test)
asserting `apply_safety_shield` / the shield-override logic is defined exactly once.

### 4.1 Gym environment — `rl/env.py` (T4.1)

```python
import gymnasium as gym
import numpy as np
from gymnasium import spaces

class AoiSchedulerEnv(gym.Env):
    """Gymnasium wrapper around sim.network.NetworkSimulator. Action = which
    node to grant this slot (the shield may override it); Observation = the
    frozen 16-D state vector (common.contracts.state_spec)."""

    def __init__(self, config: dict, measured_params: dict, seed: int | None = None):
        self.action_space = spaces.Discrete(config["system"]["n_nodes"])
        self.observation_space = spaces.Box(low=0.0, high=1.0, shape=(16,), dtype=np.float32)
        ...

    def reset(self, *, seed=None, options=None):
        ...  # construct/reset sim.network.NetworkSimulator with the given seed

    def step(self, action):
        result = self._sim.step(action)
        obs = build_observation(result, self._sim.weights)   # rl/obs.py, §4.4
        reward = shaped_reward(result, self._config)          # rl/reward.py, §4.2
        terminated = False
        truncated = self._elapsed_steps >= self._config["rl"]["episode_length"]
        info = {"shield_fired": result.shield_fired, "dui": result.dui}
        return obs, reward, terminated, truncated, info
```

Key correctness requirements:
- `observation_space` bounds are `[0, 1]` because `state_spec.py`'s
  `to_normalized_vector()` already clips/normalizes every feature into that range
  — don't re-derive bounds.
  - Episodes never `terminate` (this is a continuing control problem); they only
  `truncate` at `config["rl"]["episode_length"]` steps (`1000`, from
  `config/system.yaml`).
- `reset(seed=...)` must produce a **fresh, independently-seeded**
  `NetworkSimulator` — never reuse RNG state across episodes/resets.
- Run `gymnasium.utils.env_checker.check_env(AoiSchedulerEnv(...))` as an actual
  test (`tests/test_rl_env.py`) — this is a literal P4 acceptance criterion.

### 4.2 Reward — `rl/reward.py` (T4.2)

Thin wrapper over `common.metrics.calculate_reward`, extended with the two
already-provisioned (currently zeroed) shaping terms from `config["rl"]`:

```python
def shaped_reward(result: SlotResult, config: dict) -> float:
    base = calculate_reward(result.dui)                     # common.metrics
    lambda_energy = config["rl"]["lambda_energy"]            # currently 0.0
    lambda_waste = config["rl"]["lambda_waste"]               # currently 0.0
    waste_penalty = 0.0 if result.uplink_received else 1.0    # granted slot, no delivery
    return base - lambda_energy * result.energy_proxy_cost - lambda_waste * waste_penalty
```

With both lambdas at `0.0` (their current config value) this is exactly
`calculate_reward(result.dui)` — verify that with a test. These knobs exist for
P6's sensitivity sweep (T6.4); don't change their default values here.

### 4.3 Shield — `rl/shield.py` (T4.3)

Covered in §4.0 above — this file's only export is `apply_safety_shield`.

### 4.4 Observation builder — `rl/obs.py` (T4.4)

```python
from common.contracts.state_spec import NodeState, NetworkState

def build_observation(result: SlotResult, weights: np.ndarray) -> np.ndarray:
    nodes = [NodeState(aoi=result.aoi[i], queue=int(result.queue_status[i]),
                        rssi=float(result.rssi[i]), weight=float(weights[i]))
             for i in range(len(weights))]
    return NetworkState(nodes=nodes).to_vector()
```

Never build the 16-D vector by hand elsewhere — always go through
`NetworkState.to_vector()` so `get_state_schema_hash()` (used by P7's parity gate)
stays authoritative.

### 4.5 Baseline-parity wrapper — `rl/wrappers.py` (T4.5)

A thin adapter so a P3 `BaseScheduler` can be evaluated through the *same*
`AoiSchedulerEnv` + logging path as the trained DQN, guaranteeing apples-to-apples
comparison (same env RNG handling, same episode length, same log schema):

```python
class SchedulerPolicyWrapper:
    """Adapts a schedulers.base.BaseScheduler to look like an SB3-style policy
    (.predict(obs) -> (action, state)) so eval/run.py and P6's sweeps can drive
    baselines and the trained DQN through identical code paths."""
    def __init__(self, scheduler: "BaseScheduler"):
        self._scheduler = scheduler

    def predict(self, obs, deterministic=True):
        aoi, queue, rssi, weights = decode_observation(obs)  # inverse of rl/obs.py's normalization
        return self._scheduler.select(aoi, rssi, queue, weights), None
```

Note this requires an inverse-normalization helper (`decode_observation`) since
`BaseScheduler.select()` operates on raw AoI/RSSI/queue/weights, not the normalized
16-D vector. Put `decode_observation` in `rl/obs.py` next to `build_observation`
(it's the literal inverse using `state_spec.py`'s `DELTA_MAX`/`W_MAX`/`RSSI_MIN`/
`RSSI_RANGE` constants) — don't duplicate those constants.

### Definition of done (P4)

- [ ] `apply_safety_shield` has exactly one definition, used by both
      `sim/network.py` and `rl/env.py`'s info dict.
- [ ] `gymnasium.utils.env_checker.check_env` passes.
- [ ] Observation is verifiably 16-D and matches `get_state_schema_hash()`.
- [ ] Shield activation rate `<5%` at nominal load (measured over a smoke run with
      a reasonable baseline policy, e.g. CAG — write this as a test with a generous
      threshold, not a strict benchmark).
- [ ] `rl/wrappers.py` lets every P3 scheduler run through `AoiSchedulerEnv` and
      produce identical `SlotResult` sequences to running that scheduler directly
      against `NetworkSimulator` (write this as a parity test — same seed, same
      scheduler, both paths, assert equal).

---

## 3. Phase P5 — DQN Implementation and Training

Implements `task.md` T5.1-T5.8. Requires `pip install -e .[train,dev]` (installs
`torch`, `stable-baselines3`, `gymnasium` per `pyproject.toml`).

### 5.1 Training script — `rl/train.py` (T5.1)

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

### 5.2 Divergence monitor — `rl/monitors.py` (T5.2)

An SB3 `BaseCallback` that watches the training loss / mean Q-value each
`target_update_interval` and flags (log a warning, optionally stop early) on NaN/Inf
loss or a Q-value magnitude blowing up past a sane bound (e.g. `> 10x` the
theoretical max reward magnitude, computable from `config["scheduler"]` weights/
thresholds — don't pick an arbitrary constant, derive the bound from the DUI
formula's max plausible value).

### 5.3 Periodic evaluation callback — `rl/callbacks.py` (T5.3)

An SB3 `BaseCallback` that, every N training steps, runs the current policy
(wrapped via `rl/wrappers.py`-style `.predict()`, or directly since it's already an
SB3 model) against `config["rl"]["eval_seeds"]` (the 20 seeds `100-119` — **disjoint
from `train_seeds`**, this is a literal T5.1 acceptance criterion) and logs the
criticality-weighted mean AoI to TensorBoard.

### 5.4 Hyperparameter sweep — `rl/sweep.py` (T5.4)

A small grid/random search (a handful of runs, not an expensive campaign) over 2-3
of the most sensitive hyperparameters (e.g. `learning_rate`, `net_arch`,
`dui_lambda`/`dui_beta` from the reward formula). Log results to compare; this
informs but doesn't have to replace the frozen `config/system.yaml` defaults for
the final runs unless you find a clearly better setting — if you do change a
default, note why in `docs/TRAINING.md`.

### 5.5 Final training runs (T5.5)

Actually execute `rl/train.py` for all 5 `train_seeds`. This is compute (not
hardware) — run it. Save all 5 models under `models/`.

### 5.6 Cross-check agent — `rl/reference_dqn.py` (T5.6)

An independent, from-scratch DQN (plain PyTorch, no SB3): experience replay
buffer, target network, epsilon-greedy schedule matching the same
`config["rl"]` hyperparameters, small 2-layer MLP (`net_arch`). Train it on the
same env/seeds. Compare its final criticality-weighted mean AoI against SB3's —
**must be within 15%** (T5.1 acceptance criterion). This exists to catch an SB3-
specific bug or config-parsing mistake that both implementations would otherwise
share silently.

### 5.7 Ablations — `rl/ablations.py` (T5.7)

Re-train (fewer seeds is fine, e.g. 2-3) with individual pieces removed/altered to
isolate their contribution:
- State without the criticality-weight feature (revert to the pre-F4.1 12-D state,
  see `AoI_DRL_Scheduler_Engineering_Blueprint.md` finding F4.1) — does performance
  degrade on the live-escalation scenario?
- Reward without the non-linear DUI penalty term (`dui_lambda=0`) — does the agent
  still avoid threshold violations?
- Shield disabled entirely (evaluation-only, never disable it during training) —
  how much does the shield actually change outcomes vs. a well-trained unshielded
  policy?

### 5.8 Training report — `docs/TRAINING.md` (T5.8)

Document: hyperparameters used, all 5 seeds' learning curves, the cross-check
agent's agreement with SB3, the ablation results, and — per D6.2 — **the DQN vs
CAG comparison reported exactly as it came out**, whether DQN wins, loses, or ties.
`F5.2` in the blueprint doc already flags that CAG (using the *true* `p_s(RSSI)`
model) may be a very strong baseline the DQN doesn't beat; that is a legitimate,
reportable outcome, not a bug to hide.

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

Implements `task.md` T6.1-T6.7. This is mostly "run the P3 harness at scale over
everything P5 produced, with proper statistics" — most of the machinery already
exists from P3.

### 6.1 Main sweep — extend `eval/run.py` (T6.1)

Run every P3 baseline + the 5 trained DQN models (via `rl/wrappers.py` for
baselines, direct `model.predict()` for DQN) across `runs_per_condition` (10) seeds
each, under the nominal load condition from `config/system.yaml`.

### 6.2 Generalisation battery — extend `eval/run.py` (T6.2)

Re-run the best DQN model(s) under conditions **not** seen during training: e.g.
perturbed `weights`/`thresholds`, different `node_mean_rssi_dbm` levels (still
reading from a `measured_params.yaml` variant, don't hand-edit the frozen one),
different `heartbeat_period_s`. This checks for overfitting to the exact training
config.

### 6.3 Ablation table — `eval/stats.py` (T6.3)

Format P5.7's ablation results into a comparison table (criticality-weighted mean
AoI, shield activation rate, per variant).

### 6.4 Weight sensitivity — `eval/stats.py` (T6.4)

Sweep `dui_alpha`, `dui_lambda`, `dui_beta` (and separately, the class weights
`urgent`/`important`/`routine`) across a small grid, re-evaluating a fixed trained
model (not retraining each time, unless you find the policy is highly sensitive —
note that explicitly if so) or a baseline scheduler, and plot how the primary
statistic moves.

### 6.5 Statistics module — `eval/stats.py` (T6.5)

- Bootstrap or t-test confidence intervals for every leaderboard entry (from P3.7,
  now applied at full scale).
- **Shuffled-label control**: re-run the significance test with scheduler labels
  randomly permuted across runs; this must come back non-significant (`p >= 0.05`)
  — it's a sanity check that your statistical test isn't spuriously significant by
  construction. This is a literal P6 acceptance criterion.

### 6.6 Figure pack — `eval/figures.py` (T6.6)

Matplotlib figures, each regenerable by one command (`python -m eval.figures` or
similar — a literal acceptance criterion, "every figure regenerable by 1 command"):
leaderboard bar chart with CIs, AoI-over-time traces per scheduler, shield
activation rate comparison, training curves (from TensorBoard logs), ablation
table as a figure, sensitivity sweep plots.

### 6.7 Results doc — `docs/RESULTS_SIM.md` (T6.7)

Full write-up tying together P3's leaderboard, P5's training report, and P6's
ablation/sensitivity/generalisation results. State prominently, at the top: these
are simulation results on `params_source: ns3_derived_placeholder` parameters (cite
`docs/PARAM_PROVENANCE.md`), pending the real P1 hardware campaign and the D11.1
sim-to-real comparison that will follow it.

### Definition of done (P6)

- [ ] All sweeps (main, generalisation, ablation, sensitivity) complete with CIs.
- [ ] Shuffled-label control is non-significant.
- [ ] Every figure in `docs/RESULTS_SIM.md` is regenerable by one documented
      command.

---

## 5. Phase P7 — Model Export and NumPy Inference Parity

Implements `task.md` T7.1-T7.5. This is pure software — no hardware needed except
for T7.4's final on-device number, which stays deferred (see below).

### 7.1 Export — `deploy/export.py` (T7.1)

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

### 7.2 NumPy inference — `deploy/infer.py` (T7.2)

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

### 7.3 Parity gate — `tests/test_parity.py` (T7.3)

Load a trained model both ways (`model.q_net(torch_obs)` vs
`deploy.infer.infer(np.load(exported_path), obs)`) on a batch of representative
observations (random valid 16-D vectors, plus edge cases: all-zero AoI, max AoI,
one node at its shield ceiling). Assert `max(abs(delta_q)) < 1e-5` and 100%
`argmax` agreement (the actual action selection, which is what matters
operationally, must match every time even if raw Q-values have tiny float
differences).

### 7.4 Pi benchmark — `tools/bench_infer.py` (T7.4)

Write the benchmark harness (times `deploy.infer.infer()` over many calls, reports
P50/P99 latency) and **run it on the laptop now** to get a software-only number.
**Do not claim the "<5ms on-Pi P99" acceptance criterion is met** — that specific
number requires a real Raspberry Pi Zero 2W and stays `🔴 BLOCKED`/unverified until
hardware arrives. Say so explicitly in the benchmark's output/report.

### 7.5 Negative test — `tests/test_parity.py` (T7.5)

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
tests**, ready to flash the moment hardware exists.

### ⚠️ Decision needed before starting: ESP-IDF vs Arduino

This choice isn't frozen anywhere in the repo (`AoI_DRL_Scheduler_Engineering_Blueprint.md`'s
context-signal list explicitly names "ESP32 SDK choice (Arduino vs ESP-IDF)" as
unresolved). Task.md's T8.2-T8.4 describe three **separate FreeRTOS tasks**
(network/sensor/heartbeat), which fits ESP-IDF's native task model most directly.
**Recommendation: ESP-IDF**, for that reason — but confirm with the project
owner/guide before committing to it, since it affects every file path below.

### 8.0 Prerequisite: finish the packet contract — `common/contracts/packets.py`

The file currently has `GrantPacket` fully implemented but a literal
`# TODO: Add DATA, HEARTBEAT, HELLO, CONTROL models similarly` for the rest. The
firmware's network task (§8.2) needs all of these on the wire. Fill them in,
mirroring `GrantPacket`'s exact pattern (header + payload `struct.pack`, CRC16
appended):
- `DataPacket`: node's reply to a GRANT — needs `age_at_tx_us` (D2.1) and the
  `alarm_ack`/`FLAG_ALARM_ACK` bit (already defined as `FLAG_ALARM_ACK` at the top
  of the file).
- `HeartbeatPacket`: unsolicited, per D3.2 (2s period + jitter) — minimal payload,
  just needs to carry `node_id` and flags (e.g. `FLAG_SENSOR_FAULT`,
  `FLAG_POST_REBOOT`) for the gateway to track liveness/health.
- `HelloPacket`: sent once on association/reboot, so the gateway can detect
  `FLAG_POST_REBOOT` per D-series decisions on reconnection handling.
- `ControlPacket`: gateway-to-node, for future out-of-band commands (define a
  minimal payload now — a command-code byte is enough; this doesn't need to be
  elaborate yet, nothing downstream depends on it except the alarm ack path).

Add `tests/test_packets.py` cases for each (pack/unpack round-trip, CRC validation)
matching the existing `GrantPacket` test pattern already in that file.

### 8.1 Skeleton + build — `firmware/node/` (T8.1)

A single firmware source tree that builds **one binary** configurable (via
`sdkconfig`/build-time define, e.g. `CONFIG_NODE_ID`) to become any of the 4 node
roles — this is a literal acceptance criterion ("4 images from 1 source"), not 4
separate codebases. Node class (`urgent`/`urgent`/`important`/`routine`) and
therefore its weight/threshold/shield-ceiling should be derivable from `node_id` +
the same `config/system.yaml` values already frozen in Python (mirror the constants,
don't invent new ones — match `NODE_CLASSES`/`WEIGHTS`/`SHIELD_CEILING` exactly as
`ns3-sim/aoi-scheduler-sim.cc` lines 50-56 already do in C++).

### 8.2 Network task — `firmware/node/` (T8.2)

FreeRTOS task implementing the exact grant-reply protocol already validated by
`ns3-sim`'s `IoTSensorApp` (lines 149-266): bind a UDP socket for GRANT packets
(port `udp_port_grant` from `config/system.yaml`'s `network:` section), on receipt
check the local LCFS-1 buffer (§8.3) and reply with a `DataPacket` over
`udp_port_uplink` if occupied. **0 foreign-grant replies in 10k slots** is a literal
acceptance criterion — validate the GRANT's target `node_id` before replying.

### 8.3 Sensor task — `firmware/node/` (T8.3)

10 Hz (`sample_interval_s`/D8.1) periodic task that overwrites the single-slot
LCFS-1 buffer — mirror `sim/queue.py`'s `LcfsAlarmQueue` semantics exactly (a fresh
sample always overwrites; the alarm latch, once set, survives being overwritten by
a later non-alarm sample and is cleared only by an explicit ack). The Python
version in `sim/queue.py` is the reference semantics to replicate in C, even though
it can't be imported directly.

### 8.4 Heartbeat task — `firmware/node/` (T8.4)

Periodic unsolicited `HeartbeatPacket` every `heartbeat_period_s` (2.0s, from
config) plus small random jitter, matching `ns3-sim`'s `SendHeartbeat` (lines
238-248, ±0.2s jitter) — this is what keeps the gateway's RSSI estimate warm for a
starved node (F3.2 in the blueprint).

### 8.5 Diagnostics — `firmware/node/` (T8.5)

Sensor-fault detection (set `FLAG_SENSOR_FAULT` on read failure/out-of-range
value), TX failure counters, exposed via the heartbeat's flags byte.

### 8.6 Reconnection state — `firmware/node/` (T8.6)

WiFi disconnect/reconnect handling: on reassociation after a drop, send a
`HelloPacket` with `FLAG_POST_REBOOT` set so the gateway knows to treat this node's
prior AoI/RSSI state as stale rather than trusting a silently-resumed stream.

### 8.7 Firmware unit tests — `firmware/tests/` (T8.7)

Host-side unit tests (ESP-IDF's native/host test target, or an equivalent
Unity-based host build) for the logic that doesn't need real hardware: packet
pack/unpack + CRC round-trips (mirroring `tests/test_packets.py`), LCFS-1
overwrite + alarm-latch-survives-overwrite behavior (mirroring
`tests/test_queue.py`'s exact test names/semantics), node-role-from-`node_id`
derivation. **No hardware needed for any of this** — it's pure logic testable on
the host.

### 8.8 Bring-up — **out of scope, stays blocked**

Do not attempt T8.8. Document in `task.md` that firmware is built/tested and ready;
bring-up requires physical ESP32 boards.

### Definition of done (P8)

- [ ] `common/contracts/packets.py`'s TODO is resolved: `DataPacket`,
      `HeartbeatPacket`, `HelloPacket`, `ControlPacket` implemented and tested.
- [ ] One firmware source tree builds 4 distinct node images via a build-time
      config value, all sharing one codebase.
- [ ] Host-side unit tests pass for packet framing and LCFS-1/alarm-latch logic.
- [ ] `task.md` T8.1-T8.7 marked done; T8.8 explicitly left `🔴 BLOCKED` pending
      hardware.

---

## 7. Cross-cutting rules for the whole plan

1. **Honesty rule.** Every doc this plan produces (`docs/EVAL_PROTOCOL.md`,
   `docs/TRAINING.md`, `docs/RESULTS_SIM.md`) must state at the top that its
   numbers come from `params_source: ns3_derived_placeholder` (or whatever
   `common.provenance.get_params_source()` reports at the time), not real hardware.
   Never let a results doc read as if it's hardware-validated.
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
