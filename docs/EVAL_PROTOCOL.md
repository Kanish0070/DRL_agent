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

---

## NS-3 Evaluation Protocol Addendum (Phase N4)
*Pre-registered before executing ns-3 evaluation runs to prevent HARKing / p-hacking.*

### 1. Scenario Matrix
| ID | Scenario | Configuration | Hypothesis |
|---|---|---|---|
| **S0** | Nominal | 5, 8, 12, 18 m; 20 dBm tx power | AoI-aware schedulers (MW, CAG, DQN) tie; all beat RR/FPQ/Random. |
| **S1** | Weak Links | Scaled distance / lower tx power (far node in −85 to −78 dBm) | Channel awareness matters: CAG and DQN outperform Max-Weight. |
| **S2** | Bursty Interferer | Co-channel/hidden-terminal interferer on STA-4 (10–20% link loss) | DQN + safety shield keeps urgent-class AoI bounded under burst packet drops. |
| **S3** | Dynamic Mobility | Routine STA-4 walks from 18 m to coverage edge and returns (1.0 m/s) | Policy dynamically adapts scheduling as link RSSI drops and recovers. |
| **S4** | Fault Injection | Urgent STA-2 fails at t=30s for 30s, then recovers | Liveness masking prevents wasting grants on unreachable node; recovery is bounded. |

### 2. Evaluated Policies
1. **Round Robin (RR)**
2. **Fixed Priority Queue (FPQ)**
3. **Random**
4. **Max-Weight (MW)**
5. **Channel-Aware Greedy (CAG)**
6. **DQN (Seeds 0–4)**: Frozen MLP policies exported in `deploy/artifacts/`
7. **DQN (No Shield)**: Ablation variant to measure shield impact

### 3. Primary & Secondary Metrics
- **Primary Statistic:** Criticality-Weighted Mean AoI (D6.1):
  $$\bar{\Delta}_{\text{cw}} = \frac{1}{T} \sum_{t=1}^T \sum_{i=1}^N w_i \Delta_i(t)$$
- **Secondary Metrics:**
  - Class-wise P95 and P99 AoI
  - Fraction of time above soft thresholds (200 / 500 / 1000 ms)
  - Shield activation rate (target < 5% in S0)
  - Wasted slot rate (1 − PDR)
  - Recovery time in S4 (time for STA-2 AoI to return below soft threshold after reconnection)

### 4. Sim-to-NS3 Gap Statistics (D11.1)
1. **Metric Gap:** Absolute and percentage error in cw-mean AoI between Python simulation and ns-3 per policy:
   $$\text{Gap}_{\text{metric}} = |\bar{\Delta}_{\text{sim}} - \bar{\Delta}_{\text{ns3}}|$$
2. **Ranking Gap:** Kendall rank correlation coefficient ($\tau$) between simulation and ns-3 policy leaderboards:
   $$\tau = \frac{P - Q}{\sqrt{(P + Q + T) \cdot (P + Q + U)}}$$
3. **Transfer Gap:** Preservation of DQN's advantage over the best baseline across simulators:
   $$\Delta_{\text{transfer}} = (\bar{\Delta}_{\text{baseline}} - \bar{\Delta}_{\text{dqn}})_{\text{ns3}} - (\bar{\Delta}_{\text{baseline}} - \bar{\Delta}_{\text{dqn}})_{\text{sim}}$$


