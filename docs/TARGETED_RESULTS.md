# Targeted results: DQN on lossy links

DQN is trained to keep every sensor class inside its own freshness deadline (urgent 200 ms, important 500 ms, routine 1000 ms; its reward penalises age relative to each deadline).
Its advantage shows on lossy links. These runs target exactly that.

## Method

- Conditions: T1 and T2 use the main campaign's S1 and S5 radio settings; T3 uses the distance pilot's S10 geometry (distance scale 6). They were chosen because earlier runs showed DQN's advantage there.
- Confirmation on **fresh seeds 500-519** (20 per scheduler, identical for all), never used to choose the conditions. 300 s per run, 480 runs. No node dropped out in any run.
- Schedulers: DQN as deployed (training seed 1, chosen on nominal S0 results before any of this), Channel-Aware Greedy, Fixed Priority, Round Robin.
- Headline metric: share of time the **worst-served class** is past its deadline. Paired over seeds, Holm-corrected p-values, 95% bootstrap CI.
- Raw logs: `results/ns3_targeted/` (git-ignored); summaries in `results/ns3_targeted/summary/`. Rerun: `ns3-sim/scripts/run_targeted.sh`, then `tools/ns3_summarize.py` and `tools/panel_evidence.py --deployed-seed 1`.

## Headline: worst-served class past its deadline (lower is better)

| Scenario | DQN | CAG | Round Robin | Fixed Priority | DQN vs CAG | DQN vs Round Robin |
|---|---|---|---|---|---|---|
| T1 weak links (TX -5 dBm, nodes 5-18 m) | **41.0%** | 52.0% | 55.4% | 95.0% | 11.0 pts (21%), 20/20 seeds, p <0.001 | 14.4 pts (26%), 20/20 seeds, p <0.001 |
| T2 heavy loss (TX -7 dBm, nodes 5-18 m) | **45.2%** | 55.8% | 58.3% | 95.1% | 10.6 pts (19%), 19/20 seeds, p 0.004 | 13.1 pts (22%), 19/20 seeds, p 0.007 |
| T3 far nodes (TX 20 dBm, nodes 30-108 m) | **39.0%** | 45.6% | 53.8% | 95.0% | 6.6 pts (15%), 20/20 seeds, p <0.001 | 14.9 pts (28%), 20/20 seeds, p <0.001 |

In practical terms: 1 point = 36 s per hour. Against CAG, DQN cuts the worst class's time past deadline by about 4-7 minutes per hour.

## Per-class detail (share of time past deadline; weighted AoI in s)

| Scenario | Scheduler | Urgent | Important | Routine | Weighted AoI |
|---|---|---|---|---|---|
| T1 | DQN | 41.0% | 27.8% | 29.3% | 0.183 |
| T1 | CAG | 34.7% | 32.4% | 52.0% | 0.190 |
| T1 | Round Robin | 55.4% | 19.0% | 8.7% | 0.218 |
| T1 | Fixed Priority | 14.9% | 91.8% | 95.0% | 0.864 |
| T2 | DQN | 43.0% | 31.7% | 39.7% | 0.259 |
| T2 | CAG | 36.8% | 37.6% | 55.8% | 0.217 |
| T2 | Round Robin | 56.1% | 23.5% | 18.8% | 0.325 |
| T2 | Fixed Priority | 17.5% | 91.8% | 95.1% | 0.880 |
| T3 | DQN | 39.0% | 25.5% | 18.4% | 0.167 |
| T3 | CAG | 32.8% | 26.3% | 45.6% | 0.174 |
| T3 | Round Robin | 53.8% | 14.0% | 5.0% | 0.198 |
| T3 | Fixed Priority | 12.0% | 91.8% | 95.0% | 0.858 |

## Caveats to state

- **Where the gain comes from:** DQN balances the classes. It keeps important and routine data much fresher than CAG, and pays with more urgent-node time past 200 ms (about 6 points more than CAG).
- **Scope:** the advantage is on lossy links. On strong links (main campaign S0, S2, S3) CAG is better on this metric.
- **Training seed:** the figures are for the deployed model. Averaged over all five training seeds the gain over CAG is smaller: 8% (T1), 8% (T2), 0% (T3).
- **Selection:** the conditions and the metric were chosen after seeing earlier results; the numbers above are from fresh seeds, which is what keeps the statistics valid.
- **T2 tails:** mean weighted AoI in T2 is worse for DQN (a few seeds with long outages) even though it is ahead on most seeds.
