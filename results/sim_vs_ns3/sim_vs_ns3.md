# Sim-to-ns3 gap

Python simulator vs NS-3 evaluation of the same policies (criticality-weighted mean AoI, seconds, lower is better).
NS-3 S0 is the nominal scenario; S1-S4 are stress scenarios (see `results/ns3_campaign/README.md`).

## Per-policy means

| policy | py_cw | py_lo | py_hi | py_wasted_pct | ns3_S0 | ns3_S1 | ns3_S2 | ns3_S3 | ns3_S4 |
|---|---|---|---|---|---|---|---|---|---|
| rr | 0.3855 | 0.3806 | 0.3908 | 27.8700 | 0.1722 | 0.2187 | 0.1736 | 0.1788 | 0.7986 |
| fpq | 0.9912 | 0.9883 | 0.9944 | 24.7250 | 0.8503 | 0.8642 | 0.8514 | 0.8528 | 1.5040 |
| random | 0.5110 | 0.5041 | 0.5176 | 27.2100 | 0.3172 | 0.3595 | 0.3211 | 0.3248 | 0.9750 |
| maxweight | 0.3427 | 0.3378 | 0.3477 | 26.7050 | 0.1495 | 0.1832 | 0.1532 | 0.1572 | 0.7994 |
| cag | 0.3528 | 0.3481 | 0.3569 | 25.0300 | 0.1490 | 0.1918 | 0.1533 | 0.1593 | 0.7994 |
| oracle | 0.3390 | 0.3362 | 0.3420 | 21.5700 | nan | nan | nan | nan | nan |
| dqn | 0.3440 | 0.3402 | 0.3477 | 26.6100 | 0.1565 | 0.1904 | 0.1602 | 0.1644 | 0.8639 |

## Rank agreement (Kendall tau over rr, fpq, random, maxweight, cag, dqn)

| scenario | kendall_tau | p_value | n_policies | python_order | ns3_order |
|---|---|---|---|---|---|
| S0 | 0.7333 | 0.0556 | 6 | maxweight < dqn < cag < rr < random < fpq | cag < maxweight < dqn < rr < random < fpq |
| S1 | 1.0000 | 0.0028 | 6 | maxweight < dqn < cag < rr < random < fpq | maxweight < dqn < cag < rr < random < fpq |
| S2 | 0.8667 | 0.0167 | 6 | maxweight < dqn < cag < rr < random < fpq | maxweight < cag < dqn < rr < random < fpq |
| S3 | 0.8667 | 0.0167 | 6 | maxweight < dqn < cag < rr < random < fpq | maxweight < cag < dqn < rr < random < fpq |
| S4 | 0.4667 | 0.2722 | 6 | maxweight < dqn < cag < rr < random < fpq | rr < maxweight < cag < dqn < random < fpq |

## DQN vs baseline, paired by eval seed (negative = DQN has lower AoI)

| simulator | scenario | baseline | dqn_rel_diff_pct | t_p | n_pairs |
|---|---|---|---|---|---|
| python | - | cag | -2.476 | 0.006733 | 20 |
| python | - | maxweight | 0.3938 | 0.569 | 20 |
| python | - | rr | -10.77 | 1.798e-10 | 20 |
| python | - | random | -32.67 | 9.102e-20 | 20 |
| python | - | fpq | -65.29 | 5.696e-36 | 20 |
| ns3 | S0 | cag | 5.024 | 1.154e-12 | 20 |
| ns3 | S0 | maxweight | 4.693 | 4.499e-12 | 20 |
| ns3 | S0 | rr | -9.082 | 3.762e-14 | 20 |
| ns3 | S0 | random | -50.66 | 1.438e-25 | 20 |
| ns3 | S0 | fpq | -81.59 | 1.056e-51 | 20 |
| ns3 | S1 | cag | -0.7272 | 0.6316 | 20 |
| ns3 | S1 | maxweight | 3.921 | 0.007875 | 20 |
| ns3 | S1 | rr | -12.95 | 1.45e-08 | 20 |
| ns3 | S1 | random | -47.04 | 3.582e-22 | 20 |
| ns3 | S1 | fpq | -77.97 | 9.94e-34 | 20 |
| ns3 | S2 | cag | 4.471 | 6.848e-13 | 20 |
| ns3 | S2 | maxweight | 4.569 | 3.379e-12 | 20 |
| ns3 | S2 | rr | -7.706 | 2.651e-11 | 20 |
| ns3 | S2 | random | -50.12 | 6.282e-25 | 20 |
| ns3 | S2 | fpq | -81.18 | 1.687e-50 | 20 |
| ns3 | S3 | cag | 3.203 | 0.08876 | 20 |
| ns3 | S3 | maxweight | 4.599 | 0.02409 | 20 |
| ns3 | S3 | rr | -8.006 | 0.0001899 | 20 |
| ns3 | S3 | random | -49.37 | 3.343e-21 | 20 |
| ns3 | S3 | fpq | -80.72 | 5.591e-34 | 20 |
| ns3 | S4 | cag | 8.064 | 3.715e-22 | 20 |
| ns3 | S4 | maxweight | 8.068 | 2.949e-22 | 20 |
| ns3 | S4 | rr | 8.173 | 9.81e-12 | 20 |
| ns3 | S4 | random | -11.4 | 4.08e-13 | 20 |
| ns3 | S4 | fpq | -42.56 | 3.9e-37 | 20 |

## Caveats (quote these with the numbers)

- The Python runs are 1000 slots (100 s); NS-3 runs are 3000 slots (300 s). Absolute AoI values are not comparable; compare rankings and relative differences.
- Loss regimes differ: Python wasted-slot rate is about 25% (placeholder channel parameters), NS-3 S0 is about 6%.
- The Python logs were produced on placeholder parameters (`params_source=placeholder_pending_p1`) from the commits listed below, with a dirty working tree.
- The Python `dqn` runs carry only `policy_id=dqn`; which of the 5 training seeds produced them is not recorded. NS-3 pools all 5 training seeds.
- The Python simulator includes an `oracle` policy that NS-3 does not; it is excluded from the rank comparison.
- All numbers are simulation results; none come from hardware.

## Python run provenance

| policy | git_sha | params | slots | n |
|---|---|---|---|---|
| cag | f0cb92b | placeholder_pending_p1 | 1000 | 20 |
| dqn | f0cb92b | placeholder_pending_p1 | 1000 | 20 |
| fpq | f0cb92b | placeholder_pending_p1 | 1000 | 20 |
| maxweight | f0cb92b | placeholder_pending_p1 | 1000 | 20 |
| oracle | f0cb92b | placeholder_pending_p1 | 1000 | 20 |
| random | f0cb92b | placeholder_pending_p1 | 1000 | 20 |
| rr | f0cb92b | placeholder_pending_p1 | 1000 | 20 |
