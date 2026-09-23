# Evaluation Protocol for Baselines and DQN

**Note:** All results produced by simulation in P3/P6 are on PLACEHOLDER `config/measured_params.yaml` parameters pending the real P1 hardware campaign. The current placeholder distances put nodes in the logistic curve's sensitive region differently than physical tests might, so simulated PDR is unrealistically flat. This will flatten Channel-Aware Greedy and Oracle advantages over Max-Weight.

## Primary and Secondary Statistics
- **Primary Statistic:** Criticality-weighted mean AoI per run (D6.1).
- **Secondary Statistics:** Wasted-slot rate, total energy.

## Statistical Testing
- A paired or independent t-test (depending on seed pairing) will be used to compare DQN to RR/FPQ.
- Significance threshold: `p < 0.05`.
- Negative results against CAG (DQN vs CAG) will be reported honestly.

## Seeds
- `train_seeds`: Used exclusively for DQN training.
- `eval_seeds`: Used for evaluating baselines and DQN.
- Train and eval seeds are strictly disjoint.

