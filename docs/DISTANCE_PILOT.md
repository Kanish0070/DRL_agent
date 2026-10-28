# Distance pilot: are the gains larger when nodes are far away (training-like geometry)?

Written **before any scheduler was run** on these scenarios. Results are appended below only after the runs.

## Why
The main campaign puts nodes at 5, 8, 12 and 18 m and creates weak links by lowering transmit power. The DQN was trained in the Python simulator with nodes at 30, 36, 42 and 50 m.
So the test geometry differs from the training geometry, and "weak links" in the main campaign are an artefact of low power, not of distance.

## Design (separate from the main campaign and from the stress pilot)
- Results root: `results/ns3_distance_pilot/`. Main results and seeds untouched.
- Schedulers and metrics: unchanged (DQN, CAG, Fixed Priority, Round Robin; the same per-run metrics). DQN: all 5 training seeds, pooled and the deployed seed (1).
- Eval seeds 200-204, the same for every scheduler. 300 s, 0.1 s slots, TX power 20 dBm (the nominal S0 value), default loss model, default traffic.
- Only the node distances change, through `--distanceScale` (S0 distances 5/8/12/18 m multiplied by the scale).

## Choosing the distances (no scheduler results involved)
Run Round Robin only, seed 200, 120 s, for scales 3 to 7. Pick:
- **D1 (moderate):** the scale whose Round Robin wasted-slot rate is closest to 15%,
- **D2 (training-like):** the scale closest to 25% (the loss level the DQN was trained at),
provided all four nodes still deliver (none disassociated). If a candidate drops a node, take the next one down. DQN, CAG and Fixed Priority results are not used for this.

### Calibration outcome (Round Robin only, seed 200, 120 s)
| scale | node distances (m) | wasted slots | note |
|---|---|---|---|
| 3 | 15 / 24 / 36 / 54 | 6.8% | |
| 4 | 20 / 32 / 48 / 72 | 9.4% | |
| 5 | 25 / 40 / 60 / 90 | 12.2% | |
| 6 | 30 / 48 / 72 / 108 | 15.5% | **D1** |
| 7 | 35 / 56 / 84 / 126 | 17.9% | |
| 8 | 40 / 64 / 96 / 144 | 20.5% | |
| 9 | 45 / 72 / 108 / 162 | 20.2% | STA-4 never delivers (dropped), excluded |
| 10 | 50 / 80 / 120 / 180 | 26.7% | **D2**, all four nodes deliver |
| 12 | 60 / 96 / 144 / 216 | 24.9% | STA-4 never delivers (dropped), excluded |

Amendment made before any scheduler was run: the original range (3-7) tops out at 17.9% wasted slots, so no scale reached the 25% target. The probe was extended to 8-12 using Round Robin only.
D1 = scale 6 and D2 = scale 10 (26.7%; the closest to 25% among scales where every node delivers). The distances are beyond realistic Wi-Fi range because of the simulator's path-loss constants at 20 dBm; what matters is the resulting signal level and loss.
Scale 9 dropping a node while scale 10 does not shows association is somewhat unstable at these ranges, so any run in which a node never delivers will be reported.

## What we will report (n = 5 seeds, so trends only)
Per scenario, DQN (pooled and deployed seed) against CAG, Fixed Priority and Round Robin: mean weighted AoI and urgent / important / routine time past deadline,
with the absolute difference, relative %, and seeds won out of 5. Every scenario is reported whether DQN wins or loses.

## Rule for scaling up
Same as the stress pilot: expand a scenario to 20 seeds only if DQN beats CAG by at least 5% on mean weighted AoI, or by at least 10% on a deadline metric,
and wins at least 4 of 5 seeds for both the pooled and the deployed-seed DQN. If no scenario meets it, the conclusion is that distance alone does not reveal an advantage.

## Results
Run 2026-10-28: 80 runs (2 scenarios x 8 policies x 5 seeds), none failed. Raw logs are git-ignored; summaries are in `results/ns3_distance_pilot/summary/`.

**S11 (scale 10) is not interpretable.** In 24 of its 40 runs (60%, similar for every scheduler: CAG 3/5, Fixed Priority 3/5, Round Robin 3/5, DQN 15/25) at least one node never delivers a single update,
so mean weighted AoI is dominated by a node that has dropped off the network (medians about 6.4 s for all schedulers). This regime is association failure, not weak links, and the pre-registered caveat applies.
Its numbers are kept in the CSVs but not used for conclusions.

**S10 (scale 6; nodes at 30 / 48 / 72 / 108 m; Round Robin wastes 15.5% of slots; no dropped nodes).** Means over seeds 200-204 (DQN pooled over its 5 training seeds):

| Metric | DQN | CAG | RR | FPQ |
|---|---|---|---|---|
| Weighted AoI (s) | 0.173 | 0.175 | 0.197 | 0.857 |
| Urgent past 200 ms | 38.5% | 32.6% | 53.8% | 12.0% |
| Important past 500 ms | 18.8% | 26.1% | 12.9% | 91.8% |
| Routine past 1000 ms | 39.1% | 46.5% | 4.8% | 95.0% |

DQN vs CAG (positive = DQN better; wins out of 5 seeds; pooled | deployed seed 1):
- weighted AoI: +1.6% (4/5) | +4.7% (5/5), a tie in practice at this sample size
- urgent past deadline: 18% worse (0/5) | 20% worse (0/5)
- important past deadline: +28% (5/5) | +1.4% (3/5), so not robust to the training seed
- routine past deadline: +16% (5/5) | +60% (5/5)

- **Scale-up rule:** met by exactly one result, the routine-node deadline in S10. No other metric in either scenario meets it.
- **Pattern:** the same as in S1 and S5. DQN trades urgent-deadline time for better important and routine freshness, and ties CAG on mean weighted AoI. At this distance the mean-AoI edge is small (2-5%) and n = 5.
- vs Round Robin: DQN is 12% better on weighted AoI and 28% better on urgent deadline, but much worse on important and routine deadlines. vs Fixed Priority: DQN is about 80% better on weighted AoI, but Fixed Priority keeps urgent nodes past 200 ms 12% of the time against DQN's 38.5%.
- **Caveats:** n = 5, so trends only. The distances (up to 108 m) are beyond realistic Wi-Fi range because of the simulator's path-loss constants; what matters is the resulting signal level and loss.
