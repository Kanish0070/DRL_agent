# NS-3 campaign summary

Runs: 160 (4 scenarios x 8 policies x 5 eval seeds). DQN rows pool its 5 training seeds.

## S6: 

| policy | cw_aoi | ci_lo | ci_hi | wasted_pct | shield_pct | urgent_viol_pct | max_urgent_aoi |
|---|---|---|---|---|---|---|---|
| Channel-Aware Greedy | 0.358 | 0.353 | 0.362 | 43.648 | 0.067 | 0.301 | 3.000 |
| DQN (+shield) | 0.369 | 0.363 | 0.376 | 44.498 | 0.150 | 0.418 | 4.400 |
| Round Robin | 0.476 | 0.459 | 0.492 | 49.137 | 0.134 | 0.997 | 4.100 |
| Fixed Priority | 0.965 | 0.956 | 0.973 | 34.786 | 6.372 | 0.455 | 3.300 |

DQN vs baseline (paired by eval seed; negative rel_diff = DQN has lower AoI):

| baseline | dqn_mean | base_mean | rel_diff_pct | t_p | t_p_holm | cohens_dz |
|---|---|---|---|---|---|---|
| Round Robin | 0.3693 | 0.4755 | -22.34 | 0.0004351 | 0.003046 | -4.777 |
| Fixed Priority | 0.3693 | 0.9646 | -61.72 | 7.457e-11 | 8.949e-10 | -238.2 |
| Channel-Aware Greedy | 0.3693 | 0.3581 | 3.126 | 0.02329 | 0.04659 | 1.598 |

## S7: 

| policy | cw_aoi | ci_lo | ci_hi | wasted_pct | shield_pct | urgent_viol_pct | max_urgent_aoi |
|---|---|---|---|---|---|---|---|
| Channel-Aware Greedy | 0.808 | 0.766 | 0.856 | 60.917 | 5.040 | 11.794 | 7.100 |
| Round Robin | 0.809 | 0.772 | 0.845 | 54.458 | 4.003 | 11.004 | 8.300 |
| DQN (+shield) | 0.880 | 0.858 | 0.902 | 59.542 | 5.577 | 12.058 | 9.200 |
| Fixed Priority | 1.392 | 1.363 | 1.414 | 52.677 | 10.622 | 11.995 | 11.101 |

DQN vs baseline (paired by eval seed; negative rel_diff = DQN has lower AoI):

| baseline | dqn_mean | base_mean | rel_diff_pct | t_p | t_p_holm | cohens_dz |
|---|---|---|---|---|---|---|
| Round Robin | 0.8801 | 0.8085 | 8.851 | 0.0499 | 0.0499 | 1.243 |
| Fixed Priority | 0.8801 | 1.392 | -36.76 | 5.09e-06 | 4.581e-05 | -14.71 |
| Channel-Aware Greedy | 0.8801 | 0.8084 | 8.873 | 0.0008258 | 0.004955 | 4.048 |

## S8: 

| policy | cw_aoi | ci_lo | ci_hi | wasted_pct | shield_pct | urgent_viol_pct | max_urgent_aoi |
|---|---|---|---|---|---|---|---|
| Round Robin | 0.375 | 0.373 | 0.378 | 23.360 | 0.007 | 0.007 | 2.000 |
| Channel-Aware Greedy | 0.381 | 0.376 | 0.388 | 40.402 | 0.462 | 1.392 | 4.500 |
| DQN (+shield) | 0.406 | 0.396 | 0.416 | 44.341 | 0.399 | 1.649 | 4.700 |
| Fixed Priority | 1.064 | 1.056 | 1.078 | 60.422 | 2.999 | 0.997 | 3.100 |

DQN vs baseline (paired by eval seed; negative rel_diff = DQN has lower AoI):

| baseline | dqn_mean | base_mean | rel_diff_pct | t_p | t_p_holm | cohens_dz |
|---|---|---|---|---|---|---|
| Round Robin | 0.4058 | 0.3754 | 8.097 | 0.004285 | 0.01714 | 2.612 |
| Fixed Priority | 0.4058 | 1.064 | -61.88 | 2.614e-08 | 2.875e-07 | -55.04 |
| Channel-Aware Greedy | 0.4058 | 0.3814 | 6.391 | 0.01325 | 0.03974 | 1.897 |

## S9: 

| policy | cw_aoi | ci_lo | ci_hi | wasted_pct | shield_pct | urgent_viol_pct | max_urgent_aoi |
|---|---|---|---|---|---|---|---|
| Round Robin | 0.444 | 0.440 | 0.449 | 36.459 | 0.080 | 0.308 | 4.000 |
| Channel-Aware Greedy | 0.503 | 0.494 | 0.512 | 52.048 | 0.830 | 2.162 | 5.000 |
| DQN (+shield) | 0.532 | 0.518 | 0.546 | 53.246 | 1.056 | 3.549 | 6.900 |
| Fixed Priority | 1.156 | 1.146 | 1.166 | 64.391 | 5.234 | 3.159 | 4.700 |

DQN vs baseline (paired by eval seed; negative rel_diff = DQN has lower AoI):

| baseline | dqn_mean | base_mean | rel_diff_pct | t_p | t_p_holm | cohens_dz |
|---|---|---|---|---|---|---|
| Round Robin | 0.5321 | 0.444 | 19.85 | 3.401e-05 | 0.0002721 | 9.129 |
| Fixed Priority | 0.5321 | 1.156 | -53.97 | 2.766e-07 | 2.766e-06 | -30.51 |
| Channel-Aware Greedy | 0.5321 | 0.5034 | 5.716 | 0.002932 | 0.01466 | 2.896 |

## DQN spread across training seeds (mean cw-AoI)

| scenario | 0 | 1 | 2 | 3 | 4 |
|---|---|---|---|---|---|
| S6 | 0.3681 | 0.3710 | 0.3603 | 0.3694 | 0.3776 |
| S7 | 0.8901 | 0.8687 | 0.8743 | 0.8817 | 0.8858 |
| S8 | 0.4398 | 0.4002 | 0.3868 | 0.4002 | 0.4019 |
| S9 | 0.5284 | 0.5557 | 0.4792 | 0.5672 | 0.5301 |
