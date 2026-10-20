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

## Known limitations (read before quoting results)

1. **Scenarios S0-S3 do not stress the link.** Wasted-slot rate is 0.000% in S0-S3 for every policy, so S0, S2 and S3
   give the same numbers (S1 differs only slightly). The NS-3 channel with HtMcs0 has an abrupt cliff: in probing,
   `--txPower` of -10 dBm gave about 1% loss, and -15 dBm and below made nodes fail to associate (permanently
   unreachable). There is no gradual loss regime, so the pre-registered hypotheses for S1-S3 cannot be confirmed
   or rejected here. The interferer (S2) sits near the AP, not near STA-4 as the protocol describes.
2. S4 is the only scenario with real events. The fault window is 60-90 s (the protocol says 30-60 s).
3. The "DQN (No Shield)" ablation listed in the protocol is not implemented in the NS-3 build, so it was not run.
4. The Python-simulator reference numbers for the sim-to-ns3 gap are not in this directory.
