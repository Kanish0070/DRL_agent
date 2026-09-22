# Parameter Provenance: `config/measured_params.yaml`

This document tracks exactly where every value in `config/measured_params.yaml`
comes from, and what has to happen before it can be cited as anything other
than a pre-hardware placeholder. It exists because `task.md`'s P1 (Hardware
Timing Characterisation, T1.1-T1.7) is `🔴 BLOCKED` on hardware that has not
arrived yet, and everything from P2 onward needs *some* value for the
channel/timing parameters to run at all.

Every run produced against this file is stamped with
`provenance.source` (currently `ns3_derived_placeholder`) via
`common.provenance.get_params_source()`, so every downstream artifact
(training run, eval sweep, figure) is traceable back to which parameter set
produced it. This is what makes the eventual D11.1 sim-to-real gap analysis
a filter over existing runs, not a rerun.

## What's in the file today

| Parameter | Value | Status |
|---|---|---|
| `r50_dbm` | -82.0 | **Reused, not fabricated.** Taken verbatim from `ns3-sim/aoi-scheduler-sim.cc`'s `R50_DBM` constant, which is already frozen and exercised by the review simulation (T2.8, done). |
| `beta_db` | 4.0 | Same as above — reused from `ns3-sim`'s `BETA_LOG`. |
| `node_mean_rssi_dbm` | `[-65, -72, -80, -88]` | **Placeholder, not derived.** Chosen to span strong/marginal/poor link quality around `r50_dbm` so the channel model has meaningful signal for a scheduler to learn from. `ns3-sim`'s own radial-placement RSSI (5m/8m/12m/18m with an assumed TX power) was deliberately *not* copied here — at those short demo distances the LogDistance path-loss model gives RSSI well above `r50_dbm` for every node, which would make every delivery ~100% and give the DRL agent nothing to learn about channel-aware scheduling. Rather than invent an uncited transmit-power assumption to back-derive "realistic" distances, these four levels are stated directly as illustrative values. |
| `fading_std_db` | 4.0 | Placeholder magnitude, loosely consistent with commonly-cited indoor Wi-Fi shadow-fading standard deviations (order of a few dB), not fitted to any trace. |
| `t_slot_s` | 0.1 | Inherited unchanged from `ns3-sim`'s default slot duration. The real rule (D1.1: `T_slot` = P99 delay + 10ms, ≤1% late-arrival budget) needs a real or simulated per-hop delay *distribution*, which doesn't exist yet. |
| `sample_interval_s` | 0.1 | Matches D8.1 (10 Hz sensor sampling) and `ns3-sim`'s `IoTSensorApp` sample interval. |

## What would replace it, in order of rigor

1. **`tools/derive_params_from_sim.py` (planned, not yet built).** Batch-run
   `ns3-sim/` across the RSSI/distance range already coded in
   `aoi-scheduler-sim.cc` (the 5/8/12/18 m radial placement, and additional
   distances/attenuation to cover the full delivery-probability curve),
   parse the per-slot CSV logs, and fit `r50_dbm`/`beta_db` plus a real
   delay-distribution-derived `t_slot_s` the same way `T1.5`'s notebook was
   meant to from hardware data. This needs the ns-3 toolchain to actually
   run the sweep — not yet executed in this environment.
2. **Literature-cited values** for the components ns-3's PHY/MAC model
   doesn't cover at all: ESP32 sensor/heartbeat task wake latency, the
   lwIP/UDP stack overhead on a Pi Zero 2W, and Wi-Fi association/retry
   timing. None are cited yet — add them here with sources when filled in.
3. **The real P1 hardware campaign** (`task.md` T1.1-T1.7) once hardware
   arrives — the authoritative source, and the point of comparison for
   D11.1's sim-to-real gap statistics against whatever this file's
   `ns3_derived_placeholder` track produced in the meantime.

## Rule

Nothing that reads this file should assume its numbers are validated.
`common/config.py::load_measured_params()` enforces that every
`measured_params.yaml` declares `provenance.source`, specifically so that
downstream consumers (and anyone reading a results doc) can always tell
which track produced a given number.
