# NS-3 evaluation campaign: measured results

These are the **measured** outputs of the pre-registered scenario matrix (S0-S4) in
`docs/EVAL_PROTOCOL.md`, run on this machine. Every number in the report's NS-3 section should come
from `summary/`, not from prose elsewhere.

| Item | Value |
|---|---|
| Simulator | `ns3-sim/aoi-scheduler-sim.cc` on **ns-3.48** (release build), 802.11n HT20 2.4 GHz, 1 AP + 4 STA |
| Code commit | the commit that added this directory (`git log -1 -- results/ns3_campaign`) |
| Policies | RR, FPQ, Random, Max-Weight, CAG, and DQN training seeds 0-4 (`deploy/artifacts/dqn_seed*.txt`, schema hash 7c486950) |
| Eval seeds | 100-119 (`rl.eval_seeds`, disjoint from the DQN training seeds 0-4) |
| Run length | 300 s, 0.1 s slots (about 3000 slots/run) |
| Total runs | 1000 = 5 scenarios x 10 policies x 20 seeds |
| Reproduce | `NS3_DIR=<ns-3.48 dir> bash ns3-sim/scripts/run_campaign.sh` (about 7 min on 12 cores) |

## Contents

- `summary/summary.md`: all tables (paste-ready). `summary/*.csv`: the same data plus the 1000-row `per_run_metrics.csv`.
- `summary/figures/`: `cw_aoi_by_scenario.png`, `s4_fault_trace.png`, `s3_mobility_trace.png`.
- `raw_seed100/`: raw per-slot logs for eval seed 100 (all 5 scenarios x 10 policies). The other 950 raw logs are
  regenerable (the simulator is deterministic per seed) and are not committed (about 340 MB).

## Metric definitions

- **cw_aoi**: per-slot criticality-weighted AoI, `sum(w_i * AoI_i) / sum(w_i)` with weights 10/10/3/1,
  averaged over slots (D6.1), then averaged over runs. 95% CIs are bootstrap over eval seeds.
- **Paired tests**: DQN (mean over its 5 training seeds, per eval seed) vs each baseline on the same eval seed;
  Holm correction over all 25 comparisons. With 20 pairs and near-deterministic runs the p-values and Cohen's
  dz are extreme. Read the **relative difference**, not the p-value.
- **urgent_viol_pct**: percent of slots where an urgent node's AoI is at or above its 2.0 s shield ceiling.

## Simulator changes behind this run (all scheduler-neutral)

1. **Delivery-loss model** (`--lossModel`, default on): logistic success curve in RSSI (R50 -82 dBm, slope 4 dB) times a
   Gilbert-Elliott burst chain (0.02 / 0.3 / x0.3), the same parameters as `sim/channel.py` and
   `config/measured_params.yaml`, applied to DATA frames at the AP. S2 adds 20% extra loss on STA-4 while the
   interferer is on (`--intfLossNode/--intfLoss`).
2. **Recovery probing**: a node masked as UNREACHABLE is re-granted every 2 s.
3. **Mobility fix**: the waypoint model was aggregated onto a node that already had a constant-position model and was
   silently ignored, so S3 never moved STA-4.
4. **Association/ARP artifacts removed** (they caused dead links in about 30% of S1 runs and dominated the first
   corrected run): STAs associate at normal power and drop to the scenario TX power at t=0.9 s, beacon-loss
   de-association is disabled, and ARP entries are static.
5. **Interferers** are ad-hoc nodes (they were same-SSID access points that STAs associated with).

Scenario TX powers were fixed from measured RSSI, never from scheduler results: S1 -5 dBm (STA-4 about -79 dBm, target band
-85..-78), S3 5 dBm (STA-4 reaches about -80 dBm at the edge and stays associated).
Earlier, less-corrected runs of this campaign are in git history; do not use them.

## Known limitations (read before quoting results)

1. S2's interference is modelled as extra loss on STA-4 plus real co-channel traffic; the traffic alone caused no
   measurable loss. The interferer sits near the AP, not near STA-4.
2. S4's fault window is 60-90 s (the protocol says 30-60 s). The "urgent_viol_pct" in S4 includes the dead node's own AoI.
3. The 802.11 PHY still has an abrupt cliff: with TX power of about -15 dBm or less STAs fail to associate.
   Scenarios stay above it.
4. The "DQN (No Shield)" ablation is not implemented in the NS-3 build, so it was not run.
5. The Python-simulator reference numbers for the sim-to-ns3 gap are not in this directory.
6. With 20 near-deterministic paired runs the p-values are extreme; quote the relative differences.
