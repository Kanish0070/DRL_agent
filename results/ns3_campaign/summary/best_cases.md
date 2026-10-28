# Where the DQN does best (measured ns-3 campaign)

## Headline: large, consistent wins over the non-AoI-aware baselines (S0-S3, mean of 20 paired eval seeds)

| scenario | vs Round Robin | vs Random | vs Fixed Priority |
|---|---|---|---|
| S0 | -9.1% | -50.7% | -81.6% |
| S1 | -12.9% | -47.0% | -78.0% |
| S2 | -7.7% | -50.1% | -81.2% |
| S3 | -8.0% | -49.4% | -80.7% |
| S5 | -25.4% | -57.4% | -69.9% |

(negative = DQN has lower criticality-weighted AoI)

## Honest comparison with the strongest heuristics (Max-Weight, CAG)

Across 600 single-seed DQN runs, DQN beats the better of Max-Weight/CAG in 171 (31 by more than 3%); mean difference +10.0%. On average it is worse than the better heuristic (pooled mean above); only DQN seed 1 is near parity, and seeds 0 and 4 are about 10% worse. It does reduce worst-case urgent AoI in S1 and S3 (tail table below), though Round Robin is lowest there.

| DQN training seed | mean vs best heuristic | wins |
|---|---|---|
| 0 | +13.4% | 7/120 |
| 1 | +5.8% | 58/120 |
| 2 | +8.5% | 57/120 |
| 3 | +11.1% | 46/120 |
| 4 | +11.1% | 3/120 |

## Best 5 single runs vs the better of Max-Weight/CAG (selected cases, not averages)

| case | DQN cw-AoI | heuristic | heuristic cw-AoI | difference |
|---|---|---|---|---|
| S5_dqn2_seed108 | 0.1923 | cag | 0.2107 | -8.7% |
| S3_dqn1_seed118 | 0.1478 | maxweight | 0.1594 | -7.3% |
| S3_dqn1_seed102 | 0.1551 | maxweight | 0.1673 | -7.3% |
| S3_dqn3_seed102 | 0.1554 | maxweight | 0.1673 | -7.1% |
| S5_dqn3_seed118 | 0.1831 | maxweight | 0.1961 | -6.7% |

## Tail safety (mean over 20 eval seeds of the worst urgent-node AoI, seconds)

| scenario | DQN | Max-Weight | CAG | Round Robin |
|---|---|---|---|---|
| S0 | 1.77 | 1.67 | 1.66 | 1.57 |
| S1 | 2.03 | 2.17 | 2.08 | 1.79 |
| S2 | 1.97 | 1.92 | 1.92 | 1.55 |
| S3 | 1.86 | 2.11 | 2.12 | 1.58 |
| S4 | 30.70 | 30.64 | 30.64 | 30.09 |
| S5 | 2.12 | 2.05 | 1.99 | 2.00 |
