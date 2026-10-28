# NS-3 campaign summary

Runs: 80 (2 scenarios x 8 policies x 5 eval seeds). DQN rows pool its 5 training seeds.

## S10: 

| policy | cw_aoi | ci_lo | ci_hi | wasted_pct | shield_pct | urgent_viol_pct | max_urgent_aoi |
|---|---|---|---|---|---|---|---|
| DQN (+shield) | 0.173 | 0.170 | 0.175 | 13.015 | 0.027 | 0.104 | 2.700 |
| Channel-Aware Greedy | 0.175 | 0.171 | 0.180 | 12.430 | 0.047 | 0.141 | 3.000 |
| Round Robin | 0.197 | 0.194 | 0.200 | 14.759 | 0.000 | 0.000 | 1.900 |
| Fixed Priority | 0.857 | 0.854 | 0.859 | 9.618 | 2.691 | 0.094 | 2.400 |

DQN vs baseline (paired by eval seed; negative rel_diff = DQN has lower AoI):

| baseline | dqn_mean | base_mean | rel_diff_pct | t_p | t_p_holm | cohens_dz |
|---|---|---|---|---|---|---|
| Round Robin | 0.1726 | 0.1968 | -12.28 | 0.0002905 | 0.001452 | -5.299 |
| Fixed Priority | 0.1726 | 0.8567 | -79.85 | 4.487e-12 | 2.692e-11 | -480.9 |
| Channel-Aware Greedy | 0.1726 | 0.1754 | -1.58 | 0.3728 | 1 | -0.4483 |

## S11: 

| policy | cw_aoi | ci_lo | ci_hi | wasted_pct | shield_pct | urgent_viol_pct | max_urgent_aoi |
|---|---|---|---|---|---|---|---|
| Fixed Priority | 7.052 | 2.229 | 13.210 | 20.502 | 3.012 | 0.060 | 2.400 |
| DQN (+shield) | 7.222 | 4.213 | 10.715 | 22.537 | 0.084 | 0.120 | 2.801 |
| Channel-Aware Greedy | 7.644 | 1.444 | 16.328 | 22.925 | 0.020 | 0.141 | 2.800 |
| Round Robin | 7.954 | 2.014 | 16.658 | 23.755 | 0.830 | 0.067 | 2.700 |

DQN vs baseline (paired by eval seed; negative rel_diff = DQN has lower AoI):

| baseline | dqn_mean | base_mean | rel_diff_pct | t_p | t_p_holm | cohens_dz |
|---|---|---|---|---|---|---|
| Round Robin | 7.222 | 7.954 | -9.204 | 0.197 | 0.7879 | -0.6915 |
| Fixed Priority | 7.222 | 7.052 | 2.414 | 0.8577 | 1 | 0.0855 |
| Channel-Aware Greedy | 7.222 | 7.644 | -5.517 | 0.4028 | 1 | -0.4181 |

## DQN spread across training seeds (mean cw-AoI)

| scenario | 0 | 1 | 2 | 3 | 4 |
|---|---|---|---|---|---|
| S10 | 0.1760 | 0.1672 | 0.1709 | 0.1684 | 0.1805 |
| S11 | 6.5001 | 7.6773 | 6.5783 | 7.6847 | 7.6697 |
