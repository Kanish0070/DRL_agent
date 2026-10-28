# Stress pilot: conditions where a learned scheduler could help

Written **before any scheduler was run** on these scenarios. Results are appended below only after the runs.

## Why
The main campaign (S0-S5) favours greedy index rules: every node always has a fresh sample, and the ns-3 loss model
(R50 = -82 dBm, slope 4 dB) is exactly the formula Channel-Aware Greedy (CAG) hard-codes. A tie there does not test the cases where learning should help.

## Design (separate from the main campaign)
- Results root: `results/ns3_stress_pilot/` (main results and seeds are untouched).
- Schedulers and metrics: unchanged. DQN, CAG, Fixed Priority, Round Robin; the same per-run metrics from `tools/ns3_summarize.py`.
- Eval seeds: **200-204** (5 seeds, the same for every scheduler; the main campaign uses 100-119). DQN: all 5 training seeds, pooled and the deployed seed (1).
- Duration 300 s, 0.1 s slots, as in the main campaign.
- Simulator change: new flag `--sampleInterval` (default 0.1 s = previous behaviour). Checked: rebuilt binary reproduces main-campaign logs byte for byte (S1 RR seed 100, S3 DQN seed 1 seed 118).

| ID | What it tests | Flags (on top of 300 s, 0.1 s slots) |
|---|---|---|
| S6 | CAG's channel formula is wrong: links fail 8 dB earlier than it assumes | `--txPower=-5 --r50=-74` |
| S7 | Bursty loss: long deep fades (memory of past losses matters) | `--txPower=-5 --geGB=0.10 --geBG=0.10 --geMult=0.1` |
| S8 | Variable load: sensors produce a sample every 0.5 s, so a grant to a node with nothing new is wasted | `--txPower=20 --sampleInterval=0.5` |
| S9 | Both: weak links plus sparse sampling | `--txPower=-5 --sampleInterval=0.5` |

TX powers are the S0/S1 values. The flags above were fixed first. One Round Robin probe run per scenario is allowed only to check that all four nodes stay associated;
flags change only if a node drops out entirely, and never based on DQN, CAG or Fixed Priority results.

## What we will report (pilot, n = 5 seeds, so trends only, no significance claims)
Per scenario, DQN (pooled over training seeds, and the deployed seed) against CAG, Fixed Priority and Round Robin:
mean weighted AoI, urgent / important / routine time past deadline: absolute difference, relative %, and seeds won out of 5.
Every scenario is reported whether DQN wins or loses.

## Rule for scaling up
Expand a scenario to the full 20 seeds only if DQN beats CAG by at least 5% on mean weighted AoI, or by at least 10% on a deadline metric, and wins at least 4 of 5 seeds
for both the pooled and the deployed-seed DQN. If no scenario meets this, the pilot's conclusion is that these stresses do not reveal an advantage for the current DQN,
and the scenarios are not re-tuned to look for one.

## Results
Run 2026-10-28: 160 runs (4 scenarios x 8 policies x 5 seeds), none failed. Raw logs are git-ignored; summaries are in `results/ns3_stress_pilot/summary/`.
Mean weighted AoI (s), mean over seeds 200-204 (DQN pooled over its 5 training seeds); wins = seeds where DQN beats the baseline, out of 5:

| Scenario | DQN | CAG | RR | FPQ | DQN vs CAG | seeds won |
|---|---|---|---|---|---|---|
| S6 early cliff | 0.369 | 0.358 | 0.476 | 0.965 | 3.1% worse | 0/5 |
| S7 bursty | 0.880 | 0.808 | 0.809 | 1.392 | 8.9% worse | 0/5 |
| S8 sparse sampling | 0.406 | 0.381 | 0.375 | 1.064 | 6.4% worse | 0/5 |
| S9 sparse + weak | 0.532 | 0.503 | 0.444 | 1.156 | 5.7% worse | 0/5 |

- **Scale-up rule: no scenario meets it.** DQN is behind CAG on mean weighted AoI in all four, with the deployed seed agreeing. The best deadline result is S8 routine node, 9.1% better than CAG
  (below the 10% bar; the important node there is 24% worse). So the scenarios are not expanded and not re-tuned.
- **vs Round Robin:** DQN is 22% better in S6 but 8-20% worse in S7, S8 and S9. DQN keeps urgent nodes past 200 ms 4-15% less often than RR in every scenario, but loses the important and routine deadlines.
- **vs Fixed Priority:** DQN is 37-62% better on weighted AoI in all four, at the cost of urgent-node deadlines in S6 and S7.
- **What the pilot did show:** under sparse sampling (S8, S9) Round Robin beats both CAG and DQN on mean weighted AoI. Age-based rules keep granting nodes that have nothing new (CAG wastes 40% of slots in S8, RR 23%),
  so the problem the stress was meant to expose is real for greedy rules. The current DQN does not solve it (44% wasted in S8): it was trained with always-ready nodes, and in ns-3 its queue input is
  always "ready", so it cannot see which node has a new sample.
- **Caveats:** n = 5 seeds, so these are trends and not tests. The DQN was not retrained for any of these conditions.
