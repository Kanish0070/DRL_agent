# NS-3 campaign summary

Runs: 480 (3 scenarios x 8 policies x 20 eval seeds). DQN rows pool its 5 training seeds.

## T1: 

| policy | cw_aoi | ci_lo | ci_hi | wasted_pct | shield_pct | urgent_viol_pct | max_urgent_aoi |
|---|---|---|---|---|---|---|---|
| Channel-Aware Greedy | 0.190 | 0.188 | 0.193 | 16.387 | 0.032 | 0.131 | 2.700 |
| DQN (+shield) | 0.198 | 0.187 | 0.217 | 17.359 | 0.028 | 0.106 | 2.900 |
| Round Robin | 0.218 | 0.217 | 0.219 | 19.945 | 0.000 | 0.000 | 1.901 |
| Fixed Priority | 0.864 | 0.862 | 0.866 | 12.462 | 2.947 | 0.112 | 2.600 |

DQN vs baseline (paired by eval seed; negative rel_diff = DQN has lower AoI):

| baseline | dqn_mean | base_mean | rel_diff_pct | t_p | t_p_holm | cohens_dz |
|---|---|---|---|---|---|---|
| Round Robin | 0.1981 | 0.218 | -9.142 | 0.02727 | 0.1364 | -0.5348 |
| Fixed Priority | 0.1981 | 0.8639 | -77.07 | 1.345e-25 | 1.076e-24 | -18.12 |
| Channel-Aware Greedy | 0.1981 | 0.1904 | 4.004 | 0.3565 | 0.8305 | 0.2113 |

## T2: 

| policy | cw_aoi | ci_lo | ci_hi | wasted_pct | shield_pct | urgent_viol_pct | max_urgent_aoi |
|---|---|---|---|---|---|---|---|
| Channel-Aware Greedy | 0.217 | 0.205 | 0.238 | 19.896 | 0.047 | 0.169 | 3.000 |
| DQN (+shield) | 0.246 | 0.216 | 0.285 | 20.928 | 0.056 | 0.115 | 2.802 |
| Round Robin | 0.325 | 0.239 | 0.472 | 24.086 | 0.075 | 0.060 | 3.700 |
| Fixed Priority | 0.880 | 0.869 | 0.900 | 15.065 | 3.176 | 0.167 | 2.800 |

DQN vs baseline (paired by eval seed; negative rel_diff = DQN has lower AoI):

| baseline | dqn_mean | base_mean | rel_diff_pct | t_p | t_p_holm | cohens_dz |
|---|---|---|---|---|---|---|
| Round Robin | 0.2462 | 0.325 | -24.24 | 0.2768 | 0.8305 | -0.2503 |
| Fixed Priority | 0.2462 | 0.88 | -72.02 | 2.188e-17 | 1.532e-16 | -6.64 |
| Channel-Aware Greedy | 0.2462 | 0.2167 | 13.63 | 0.1844 | 0.7376 | 0.308 |

## T3: 

| policy | cw_aoi | ci_lo | ci_hi | wasted_pct | shield_pct | urgent_viol_pct | max_urgent_aoi |
|---|---|---|---|---|---|---|---|
| DQN (+shield) | 0.173 | 0.172 | 0.175 | 13.146 | 0.022 | 0.076 | 2.800 |
| Channel-Aware Greedy | 0.174 | 0.172 | 0.176 | 12.549 | 0.018 | 0.085 | 2.800 |
| Round Robin | 0.198 | 0.196 | 0.200 | 14.873 | 0.000 | 0.002 | 2.000 |
| Fixed Priority | 0.858 | 0.856 | 0.860 | 9.597 | 2.684 | 0.115 | 2.700 |

DQN vs baseline (paired by eval seed; negative rel_diff = DQN has lower AoI):

| baseline | dqn_mean | base_mean | rel_diff_pct | t_p | t_p_holm | cohens_dz |
|---|---|---|---|---|---|---|
| Round Robin | 0.1734 | 0.1981 | -12.44 | 7.462e-17 | 4.477e-16 | -6.216 |
| Fixed Priority | 0.1734 | 0.8577 | -79.78 | 9.595e-46 | 8.635e-45 | -208.5 |
| Channel-Aware Greedy | 0.1734 | 0.1737 | -0.1274 | 0.7672 | 0.8305 | -0.06717 |

## DQN spread across training seeds (mean cw-AoI)

| scenario | 0 | 1 | 2 | 3 | 4 |
|---|---|---|---|---|---|
| T1 | 0.2050 | 0.1828 | 0.1840 | 0.2237 | 0.1948 |
| T2 | 0.2008 | 0.2594 | 0.2807 | 0.2092 | 0.2810 |
| T3 | 0.1780 | 0.1666 | 0.1701 | 0.1704 | 0.1820 |
