# NS-3 campaign summary

Runs: 1000 (5 scenarios x 10 policies x 20 eval seeds). DQN rows pool its 5 training seeds.

## S0: Nominal

| policy | cw_aoi | ci_lo | ci_hi | wasted_pct | shield_pct | urgent_viol_pct | max_urgent_aoi |
|---|---|---|---|---|---|---|---|
| Max-Weight | 0.129 | 0.129 | 0.129 | 0.000 | 0.000 | 0.000 | 0.220 |
| Channel-Aware Greedy | 0.129 | 0.129 | 0.129 | 0.000 | 0.000 | 0.000 | 0.219 |
| DQN (+shield) | 0.135 | 0.133 | 0.138 | 0.000 | 0.000 | 0.000 | 0.316 |
| Round Robin | 0.150 | 0.150 | 0.150 | 0.000 | 0.000 | 0.000 | 0.400 |
| Random | 0.294 | 0.291 | 0.297 | 0.000 | 0.164 | 0.107 | 2.000 |
| Fixed Priority | 0.834 | 0.834 | 0.834 | 0.000 | 2.075 | 0.000 | 0.202 |

DQN vs baseline (paired by eval seed; negative rel_diff = DQN has lower AoI):

| baseline | dqn_mean | base_mean | rel_diff_pct | t_p | t_p_holm | cohens_dz |
|---|---|---|---|---|---|---|
| Round Robin | 0.1354 | 0.1505 | -10.01 | 9.674e-45 | 1.741e-43 | -184.6 |
| Fixed Priority | 0.1354 | 0.834 | -83.76 | 1.688e-76 | 3.883e-75 | -8665 |
| Random | 0.1354 | 0.2941 | -53.96 | 1.605e-26 | 1.021e-25 | -20.27 |
| Max-Weight | 0.1354 | 0.1285 | 5.349 | 1.59e-38 | 2.067e-37 | 86.92 |
| Channel-Aware Greedy | 0.1354 | 0.1285 | 5.344 | 1.363e-37 | 1.499e-36 | 77.63 |

## S1: Weak links

| policy | cw_aoi | ci_lo | ci_hi | wasted_pct | shield_pct | urgent_viol_pct | max_urgent_aoi |
|---|---|---|---|---|---|---|---|
| Max-Weight | 0.129 | 0.129 | 0.129 | 0.000 | 0.000 | 0.000 | 0.220 |
| Channel-Aware Greedy | 0.129 | 0.129 | 0.129 | 0.000 | 0.000 | 0.000 | 0.220 |
| DQN (+shield) | 0.134 | 0.133 | 0.136 | 0.000 | 0.000 | 0.000 | 0.302 |
| Round Robin | 0.150 | 0.150 | 0.150 | 0.000 | 0.000 | 0.000 | 0.400 |
| Random | 0.294 | 0.291 | 0.297 | 0.000 | 0.164 | 0.107 | 2.000 |
| Fixed Priority | 0.834 | 0.834 | 0.834 | 0.000 | 2.075 | 0.000 | 0.202 |

DQN vs baseline (paired by eval seed; negative rel_diff = DQN has lower AoI):

| baseline | dqn_mean | base_mean | rel_diff_pct | t_p | t_p_holm | cohens_dz |
|---|---|---|---|---|---|---|
| Round Robin | 0.1345 | 0.1505 | -10.65 | 1.089e-49 | 2.287e-48 | -336.3 |
| Fixed Priority | 0.1345 | 0.834 | -83.88 | 1.33e-80 | 3.325e-79 | -1.425e+04 |
| Random | 0.1345 | 0.2941 | -54.29 | 1.459e-26 | 1.021e-25 | -20.37 |
| Max-Weight | 0.1345 | 0.1285 | 4.604 | 1.806e-41 | 2.889e-40 | 124.2 |
| Channel-Aware Greedy | 0.1345 | 0.1289 | 4.35 | 3.322e-34 | 2.99e-33 | 51.49 |

## S2: Co-channel interferer

| policy | cw_aoi | ci_lo | ci_hi | wasted_pct | shield_pct | urgent_viol_pct | max_urgent_aoi |
|---|---|---|---|---|---|---|---|
| Max-Weight | 0.129 | 0.129 | 0.129 | 0.000 | 0.000 | 0.000 | 0.218 |
| Channel-Aware Greedy | 0.129 | 0.129 | 0.129 | 0.000 | 0.000 | 0.000 | 0.400 |
| DQN (+shield) | 0.135 | 0.133 | 0.138 | 0.000 | 0.000 | 0.000 | 0.400 |
| Round Robin | 0.151 | 0.151 | 0.151 | 0.000 | 0.000 | 0.000 | 0.400 |
| Random | 0.297 | 0.294 | 0.302 | 0.000 | 0.167 | 0.110 | 2.013 |
| Fixed Priority | 0.834 | 0.834 | 0.834 | 0.000 | 2.075 | 0.000 | 0.204 |

DQN vs baseline (paired by eval seed; negative rel_diff = DQN has lower AoI):

| baseline | dqn_mean | base_mean | rel_diff_pct | t_p | t_p_holm | cohens_dz |
|---|---|---|---|---|---|---|
| Round Robin | 0.1354 | 0.1505 | -10.02 | 1.079e-45 | 2.051e-44 | -207.2 |
| Fixed Priority | 0.1354 | 0.834 | -83.76 | 9.763e-78 | 2.343e-76 | -1.007e+04 |
| Random | 0.1354 | 0.2975 | -54.47 | 5.401e-25 | 1.62e-24 | -16.84 |
| Max-Weight | 0.1354 | 0.1286 | 5.338 | 3.137e-39 | 4.391e-38 | 94.67 |
| Channel-Aware Greedy | 0.1354 | 0.1286 | 5.335 | 1.746e-39 | 2.62e-38 | 97.64 |

## S3: Mobility (STA-4 walks out)

| policy | cw_aoi | ci_lo | ci_hi | wasted_pct | shield_pct | urgent_viol_pct | max_urgent_aoi |
|---|---|---|---|---|---|---|---|
| Max-Weight | 0.129 | 0.129 | 0.129 | 0.000 | 0.000 | 0.000 | 0.220 |
| Channel-Aware Greedy | 0.129 | 0.129 | 0.129 | 0.000 | 0.000 | 0.000 | 0.219 |
| DQN (+shield) | 0.135 | 0.133 | 0.138 | 0.000 | 0.000 | 0.000 | 0.316 |
| Round Robin | 0.150 | 0.150 | 0.150 | 0.000 | 0.000 | 0.000 | 0.400 |
| Random | 0.294 | 0.291 | 0.297 | 0.000 | 0.164 | 0.107 | 2.000 |
| Fixed Priority | 0.834 | 0.834 | 0.834 | 0.000 | 2.075 | 0.000 | 0.202 |

DQN vs baseline (paired by eval seed; negative rel_diff = DQN has lower AoI):

| baseline | dqn_mean | base_mean | rel_diff_pct | t_p | t_p_holm | cohens_dz |
|---|---|---|---|---|---|---|
| Round Robin | 0.1354 | 0.1505 | -10.01 | 9.674e-45 | 1.741e-43 | -184.6 |
| Fixed Priority | 0.1354 | 0.834 | -83.76 | 1.688e-76 | 3.883e-75 | -8665 |
| Random | 0.1354 | 0.2941 | -53.96 | 1.605e-26 | 1.021e-25 | -20.27 |
| Max-Weight | 0.1354 | 0.1285 | 5.349 | 1.59e-38 | 2.067e-37 | 86.92 |
| Channel-Aware Greedy | 0.1354 | 0.1285 | 5.344 | 1.363e-37 | 1.499e-36 | 77.63 |

## S4: Fault (STA-2 down 60-90 s)

| policy | cw_aoi | ci_lo | ci_hi | wasted_pct | shield_pct | urgent_viol_pct | max_urgent_aoi |
|---|---|---|---|---|---|---|---|
| Max-Weight | 0.802 | 0.790 | 0.814 | 0.167 | 0.033 | 9.813 | 32.200 |
| Channel-Aware Greedy | 0.804 | 0.792 | 0.815 | 0.167 | 0.033 | 9.823 | 32.200 |
| Round Robin | 0.825 | 0.813 | 0.837 | 0.167 | 0.033 | 9.813 | 32.200 |
| DQN (+shield) | 0.870 | 0.863 | 0.877 | 0.167 | 0.193 | 9.837 | 32.400 |
| Random | 0.972 | 0.960 | 0.985 | 0.167 | 0.226 | 10.003 | 33.100 |
| Fixed Priority | 1.512 | 1.500 | 1.524 | 0.167 | 2.108 | 9.813 | 32.200 |

DQN vs baseline (paired by eval seed; negative rel_diff = DQN has lower AoI):

| baseline | dqn_mean | base_mean | rel_diff_pct | t_p | t_p_holm | cohens_dz |
|---|---|---|---|---|---|---|
| Round Robin | 0.87 | 0.8251 | 5.443 | 5.227e-26 | 2.091e-25 | 19.05 |
| Fixed Priority | 0.87 | 1.512 | -42.45 | 3.106e-48 | 6.213e-47 | -281.9 |
| Random | 0.87 | 0.9723 | -10.52 | 1.422e-16 | 1.422e-16 | -6.004 |
| Max-Weight | 0.87 | 0.8023 | 8.44 | 2.053e-29 | 1.643e-28 | 28.8 |
| Channel-Aware Greedy | 0.87 | 0.8036 | 8.263 | 8.864e-25 | 1.773e-24 | 16.4 |

## S4 fault recovery

| family | recovery_s | recovery_max_s | others_peak_aoi_s | grants_to_dead_node_pct |
|---|---|---|---|---|
| cag | 1.320 | 2.300 | 1.120 | 1.950 |
| dqn | 1.320 | 2.300 | 15.649 | 1.837 |
| fpq | 1.320 | 2.300 | 20.000 | 2.000 |
| maxweight | 1.320 | 2.300 | 1.100 | 2.000 |
| random | 1.320 | 2.300 | 2.010 | 1.733 |
| rr | 1.320 | 2.300 | 0.301 | 2.000 |

## DQN spread across training seeds (mean cw-AoI)

| scenario | 0 | 1 | 2 | 3 | 4 |
|---|---|---|---|---|---|
| S0 | 0.1476 | 0.1256 | 0.1269 | 0.1268 | 0.1501 |
| S1 | 0.1440 | 0.1255 | 0.1279 | 0.1283 | 0.1467 |
| S2 | 0.1476 | 0.1256 | 0.1269 | 0.1269 | 0.1503 |
| S3 | 0.1476 | 0.1256 | 0.1269 | 0.1268 | 0.1501 |
| S4 | 0.8902 | 0.8382 | 0.8727 | 0.8571 | 0.8920 |
