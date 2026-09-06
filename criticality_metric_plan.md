## Goal Description
The objective is to design a robust and effective **Criticality Metric** for the AoI_DRL_Scheduler. Based on the `AoI_DRL_Scheduler_Engineering_Blueprint.md` and current literature on AoI scheduling, a simple linear weighted AoI ($w_i \times \Delta_i$) is often insufficient for mixed-criticality networks, as it does not adequately penalize nodes approaching their safety ceilings and ignores queue buildup. 

This plan proposes the **Dynamic Urgency Index (DUI)**, a composite metric that integrates dynamic criticality weights, non-linear AoI growth, and queue lengths, directly mapping to the 16-D state vector (as identified in audit finding F4.1) and the E12 shielding safety override.

## User Review Required
> [!IMPORTANT]
> **Metric Non-linearity:** The proposed metric uses an exponential/polynomial term for AoI. This makes the reward function non-linear. The DRL agent will prioritize nodes much more aggressively as they near their AoI threshold $\tau_i$. Do you approve of tuning a non-linear parameter $\alpha$ (e.g., $\alpha=2$), or would you prefer to stick to strict linear weighting with just the safety shield fallback?

> [!WARNING]
> **Queue Weighting ($\beta$):** We are introducing a queue penalty term $\beta \times Q_i(t)$. If $\beta$ is too high, the scheduler might act like a standard queue-clearing algorithm rather than an AoI-minimizing one. This will need empirical tuning in Phase 6. 

## Open Questions
> [!CAUTION]
> 1. What are the specific target AoI thresholds ($\tau_i$) for Urgent, Important, and Routine classes before the Phase 1 hardware timing spike is completed? We can use placeholder values for now.
> 2. For the E19 live dynamic-escalation demo (alarm button), does the node remain at Urgent ($w=10$) indefinitely, or does it decay back to its baseline criticality after the alarm is serviced?

## Proposed Changes

We will formalize the **Dynamic Urgency Index (DUI)** for a node $i$ at time $t$ as:
$$DUI_i(t) = w_i(t) \times \left( \Delta_i(t) + \lambda \left( \frac{\Delta_i(t)}{\tau_i} \right)^\alpha \right) + \beta \times Q_i(t)$$

Where:
* $w_i(t) \in \{1, 3, 10\}$: Dynamic weight of the node (16-D state inclusion).
* $\Delta_i(t)$: Generation-time Age of Information.
* $\tau_i$: Soft threshold/deadline for class $i$.
* $\alpha \ge 2$: Non-linear penalty factor to create a sharp gradient as $\Delta_i \to \tau_i$.
* $Q_i(t)$: Current queue length of node $i$.
* $\lambda, \beta$: Tunable hyperparameters for the reward function.

The DRL Agent's Reward Function for slot $t$ will simply be the negative sum of all nodes' DUIs:
$$R(t) = - \sum_{i=1}^{N} DUI_i(t)$$

---

### Phase 0: Common Contracts
Updating the shared `state_spec.py` and `config/system.yaml` to formalize the metric parameters so they are identical in Python and C++.

#### [MODIFY] config/system.yaml
```yaml
scheduler:
  # Criticality weights
  weights:
    urgent: 10
    important: 3
    routine: 1
  # DUI Metric parameters (TO BE TUNED)
  dui_alpha: 2.0
  dui_lambda: 1.5
  dui_beta: 0.5
  # Soft AoI thresholds in ms
  thresholds:
    urgent: 200
    important: 500
    routine: 1000
```

### Phase 2: Simulation Core
Implementing the reward calculation mathematically to ensure it can be reused by the baseline evaluations (Phase 3) and DRL Environment (Phase 4).

#### [NEW] common/metrics.py
```python
import numpy as np

def compute_dui(aoi: np.ndarray, queue: np.ndarray, weights: np.ndarray, 
                thresholds: np.ndarray, alpha: float, lambd: float, beta: float) -> np.ndarray:
    """
    Computes the Dynamic Urgency Index (DUI) for all nodes.
    """
    # Base weighted AoI
    base_aoi = weights * aoi
    
    # Non-linear penalty as AoI approaches/exceeds threshold
    threshold_penalty = lambd * np.power(aoi / thresholds, alpha)
    
    # Queue penalty
    queue_penalty = beta * queue
    
    return base_aoi + (weights * threshold_penalty) + queue_penalty

def calculate_reward(dui_scores: np.ndarray) -> float:
    """
    Reward is the negative sum of the network's total urgency.
    """
    return -float(np.sum(dui_scores))
```

### Phase 4: RL Environment & Shielding
The shielding logic will use the same thresholds. If $\Delta_i(t) \ge C_{max}$ (where $C_{max}$ is derived from $\tau_i$), the shield activates before the DRL action is taken.

#### [MODIFY] env/shielding.py
```python
def apply_safety_shield(state_vector: np.ndarray, dqn_action: int, max_thresholds: np.ndarray) -> int:
    """
    Overrides the DQN action if a node's AoI exceeds its hard safety ceiling.
    """
    # Extract AoI from the 16-D state vector (Assumes state_spec layout)
    current_aois = state_vector[:, 0] 
    
    # Check for hard violations
    violations = current_aois >= max_thresholds
    if np.any(violations):
        # Force grant to the violating node with the highest criticality weight
        weights = state_vector[:, 3]
        critical_violators = np.where(violations)[0]
        forced_node = critical_violators[np.argmax(weights[critical_violators])]
        return forced_node
        
    return dqn_action
```

## Verification Plan

### Automated Tests
1. **Metric Monotonicity Test:** `pytest tests/test_metrics.py -k "test_dui_monotonicity"`
   - Assert that for any fixed $Q$ and $w$, $DUI(t+1) > DUI(t)$.
2. **Non-Linear Penalty Test:** 
   - Assert that a node approaching its $\tau_i$ overtakes a higher-weighted node that has a low AoI (proving the non-linear term works).
3. **Shield Override Test:** `pytest tests/test_shielding.py`
   - Feed the shield a state where a Routine node exceeds its hard ceiling, and verify the DQN action is successfully overridden.

### Manual Verification
- Review the reward curves in TensorBoard during Phase 5 (Training). The agent should learn to schedule nodes *just before* they hit the non-linear $\tau_i$ spike.
- In the Phase 10 Dashboard, observe the "Urgency Index" plot. When the "Alarm Button" (E19) is pressed, the GUI should show a massive instantaneous spike in the node's DUI, immediately followed by the scheduler forcing a grant to that node.
