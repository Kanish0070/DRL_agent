# NS-3 campaign summary

Runs: 1000 (5 scenarios x 10 policies x 20 eval seeds). DQN rows pool its 5 training seeds.

## S0: Nominal

| policy | cw_aoi | ci_lo | ci_hi | wasted_pct | shield_pct | urgent_viol_pct | max_urgent_aoi |
|---|---|---|---|---|---|---|---|
| Channel-Aware Greedy | 0.149 | 0.147 | 0.151 | 6.245 | 0.015 | 0.065 | 2.700 |
| Max-Weight | 0.150 | 0.148 | 0.151 | 6.260 | 0.020 | 0.080 | 2.700 |
| DQN (+shield) | 0.157 | 0.154 | 0.159 | 6.220 | 0.018 | 0.081 | 2.700 |
| Round Robin | 0.172 | 0.170 | 0.174 | 4.483 | 0.007 | 0.010 | 2.400 |
| Random | 0.317 | 0.314 | 0.320 | 4.550 | 0.269 | 0.251 | 3.600 |
| Fixed Priority | 0.850 | 0.849 | 0.852 | 5.947 | 2.267 | 0.084 | 2.700 |

DQN vs baseline (paired by eval seed; negative rel_diff = DQN has lower AoI):

| baseline | dqn_mean | base_mean | rel_diff_pct | t_p | t_p_holm | cohens_dz |
|---|---|---|---|---|---|---|
| Round Robin | 0.1565 | 0.1722 | -9.082 | 3.764e-14 | 5.27e-13 | -4.431 |
| Fixed Priority | 0.1565 | 0.8503 | -81.59 | 1.057e-51 | 2.642e-50 | -429.2 |
| Random | 0.1565 | 0.3172 | -50.66 | 1.438e-25 | 2.877e-24 | -18.06 |
| Max-Weight | 0.1565 | 0.1495 | 4.693 | 4.495e-12 | 4.045e-11 | 3.393 |
| Channel-Aware Greedy | 0.1565 | 0.149 | 5.024 | 1.154e-12 | 1.269e-11 | 3.664 |

## S1: Weak links

| policy | cw_aoi | ci_lo | ci_hi | wasted_pct | shield_pct | urgent_viol_pct | max_urgent_aoi |
|---|---|---|---|---|---|---|---|
| Max-Weight | 0.183 | 0.181 | 0.185 | 16.799 | 0.040 | 0.146 | 2.900 |
| DQN (+shield) | 0.190 | 0.187 | 0.197 | 17.158 | 0.039 | 0.145 | 3.000 |
| Channel-Aware Greedy | 0.192 | 0.189 | 0.195 | 16.457 | 0.052 | 0.152 | 2.900 |
| Round Robin | 0.219 | 0.217 | 0.221 | 20.177 | 0.010 | 0.044 | 3.000 |
| Random | 0.359 | 0.356 | 0.363 | 19.838 | 0.388 | 0.323 | 4.100 |
| Fixed Priority | 0.864 | 0.862 | 0.866 | 12.431 | 2.935 | 0.146 | 2.701 |

DQN vs baseline (paired by eval seed; negative rel_diff = DQN has lower AoI):

| baseline | dqn_mean | base_mean | rel_diff_pct | t_p | t_p_holm | cohens_dz |
|---|---|---|---|---|---|---|
| Round Robin | 0.1904 | 0.2187 | -12.95 | 1.45e-08 | 8.7e-08 | -2.098 |
| Fixed Priority | 0.1904 | 0.8642 | -77.97 | 9.941e-34 | 2.088e-32 | -48.6 |
| Random | 0.1904 | 0.3595 | -47.04 | 3.582e-22 | 6.089e-21 | -11.94 |
| Max-Weight | 0.1904 | 0.1832 | 3.921 | 0.007874 | 0.0315 | 0.664 |
| Channel-Aware Greedy | 0.1904 | 0.1918 | -0.7272 | 0.6316 | 0.6316 | -0.109 |

## S2: Co-channel interferer

| policy | cw_aoi | ci_lo | ci_hi | wasted_pct | shield_pct | urgent_viol_pct | max_urgent_aoi |
|---|---|---|---|---|---|---|---|
| Max-Weight | 0.153 | 0.151 | 0.155 | 6.822 | 0.025 | 0.134 | 2.700 |
| Channel-Aware Greedy | 0.153 | 0.151 | 0.156 | 6.889 | 0.025 | 0.136 | 2.700 |
| DQN (+shield) | 0.160 | 0.158 | 0.162 | 7.007 | 0.024 | 0.133 | 2.800 |
| Round Robin | 0.174 | 0.172 | 0.175 | 6.305 | 0.000 | 0.000 | 1.901 |
| Random | 0.321 | 0.317 | 0.326 | 6.365 | 0.264 | 0.191 | 3.300 |
| Fixed Priority | 0.851 | 0.849 | 0.854 | 5.780 | 2.293 | 0.126 | 2.600 |

DQN vs baseline (paired by eval seed; negative rel_diff = DQN has lower AoI):

| baseline | dqn_mean | base_mean | rel_diff_pct | t_p | t_p_holm | cohens_dz |
|---|---|---|---|---|---|---|
| Round Robin | 0.1602 | 0.1736 | -7.706 | 2.651e-11 | 1.856e-10 | -3.065 |
| Fixed Priority | 0.1602 | 0.8514 | -81.18 | 1.686e-50 | 4.047e-49 | -371 |
| Random | 0.1602 | 0.3211 | -50.12 | 6.282e-25 | 1.194e-23 | -16.7 |
| Max-Weight | 0.1602 | 0.1532 | 4.569 | 3.381e-12 | 3.381e-11 | 3.448 |
| Channel-Aware Greedy | 0.1602 | 0.1533 | 4.471 | 6.844e-13 | 8.213e-12 | 3.772 |

## S3: Mobility (STA-4 walks out)

| policy | cw_aoi | ci_lo | ci_hi | wasted_pct | shield_pct | urgent_viol_pct | max_urgent_aoi |
|---|---|---|---|---|---|---|---|
| Max-Weight | 0.157 | 0.155 | 0.159 | 8.384 | 0.037 | 0.146 | 4.300 |
| Channel-Aware Greedy | 0.159 | 0.157 | 0.162 | 8.208 | 0.042 | 0.162 | 4.400 |
| DQN (+shield) | 0.164 | 0.160 | 0.171 | 8.398 | 0.031 | 0.123 | 2.800 |
| Round Robin | 0.179 | 0.178 | 0.180 | 8.589 | 0.000 | 0.002 | 2.000 |
| Random | 0.325 | 0.322 | 0.328 | 8.447 | 0.298 | 0.231 | 4.200 |
| Fixed Priority | 0.853 | 0.851 | 0.855 | 6.620 | 2.401 | 0.179 | 4.200 |

DQN vs baseline (paired by eval seed; negative rel_diff = DQN has lower AoI):

| baseline | dqn_mean | base_mean | rel_diff_pct | t_p | t_p_holm | cohens_dz |
|---|---|---|---|---|---|---|
| Round Robin | 0.1644 | 0.1788 | -8.005 | 0.0001899 | 0.0009496 | -1.031 |
| Fixed Priority | 0.1644 | 0.8528 | -80.72 | 5.59e-34 | 1.23e-32 | -50.1 |
| Random | 0.1644 | 0.3248 | -49.37 | 3.343e-21 | 5.014e-20 | -10.61 |
| Max-Weight | 0.1644 | 0.1572 | 4.599 | 0.02409 | 0.07227 | 0.5481 |
| Channel-Aware Greedy | 0.1644 | 0.1593 | 3.203 | 0.08876 | 0.1775 | 0.4011 |

## S4: Fault (STA-2 down 60-90 s)

| policy | cw_aoi | ci_lo | ci_hi | wasted_pct | shield_pct | urgent_viol_pct | max_urgent_aoi |
|---|---|---|---|---|---|---|---|
| Round Robin | 0.799 | 0.794 | 0.807 | 5.157 | 0.008 | 9.446 | 31.900 |
| Max-Weight | 0.799 | 0.795 | 0.803 | 6.896 | 0.040 | 9.690 | 31.100 |
| Channel-Aware Greedy | 0.799 | 0.795 | 0.803 | 6.926 | 0.038 | 9.694 | 31.100 |
| DQN (+shield) | 0.864 | 0.860 | 0.868 | 6.776 | 0.196 | 9.720 | 32.000 |
| Random | 0.975 | 0.962 | 0.988 | 5.268 | 0.325 | 9.900 | 32.200 |
| Fixed Priority | 1.504 | 1.499 | 1.510 | 6.561 | 2.316 | 9.732 | 31.300 |

DQN vs baseline (paired by eval seed; negative rel_diff = DQN has lower AoI):

| baseline | dqn_mean | base_mean | rel_diff_pct | t_p | t_p_holm | cohens_dz |
|---|---|---|---|---|---|---|
| Round Robin | 0.8639 | 0.7986 | 8.173 | 9.81e-12 | 7.848e-11 | 3.245 |
| Fixed Priority | 0.8639 | 1.504 | -42.56 | 3.892e-37 | 8.951e-36 | -73.46 |
| Random | 0.8639 | 0.975 | -11.4 | 4.079e-13 | 5.303e-12 | -3.883 |
| Max-Weight | 0.8639 | 0.7994 | 8.068 | 2.948e-22 | 5.307e-21 | 12.07 |
| Channel-Aware Greedy | 0.8639 | 0.7994 | 8.064 | 3.714e-22 | 6.089e-21 | 11.92 |

## S4 fault recovery

| family | recovery_s | recovery_max_s | others_peak_aoi_s | grants_to_dead_node_pct |
|---|---|---|---|---|
| cag | 0.635 | 0.800 | 1.515 | 6.800 |
| dqn | 0.671 | 2.000 | 15.439 | 6.740 |
| fpq | 0.670 | 1.100 | 20.020 | 6.817 |
| maxweight | 0.630 | 0.800 | 1.490 | 6.783 |
| random | 0.880 | 1.900 | 2.100 | 6.683 |
| rr | 0.155 | 1.200 | 1.100 | 6.650 |

## DQN spread across training seeds (mean cw-AoI)

| scenario | 0 | 1 | 2 | 3 | 4 |
|---|---|---|---|---|---|
| S0 | 0.1676 | 0.1482 | 0.1486 | 0.1486 | 0.1696 |
| S1 | 0.1912 | 0.1827 | 0.1843 | 0.1994 | 0.1943 |
| S2 | 0.1717 | 0.1524 | 0.1516 | 0.1524 | 0.1728 |
| S3 | 0.1706 | 0.1544 | 0.1686 | 0.1572 | 0.1715 |
| S4 | 0.8830 | 0.8382 | 0.8637 | 0.8525 | 0.8819 |
