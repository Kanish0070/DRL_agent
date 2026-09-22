"""Dynamic Urgency Index (DUI) and reward, as specified in criticality_metric_plan.md.

This is the single authoritative implementation of the reward-shaping metric
used by sim/network.py (P2), the baseline schedulers' channel-aware scoring
(P3), and the RL reward function (P4) -- mirrors the role common/contracts/aoi.py
plays for the AoI update rule, so training and evaluation can never silently
diverge on what "urgency" means.
"""

import numpy as np


def compute_dui(aoi: np.ndarray, queue: np.ndarray, weights: np.ndarray,
                 thresholds: np.ndarray, alpha: float, lambd: float, beta: float) -> np.ndarray:
    """
    DUI_i(t) = w_i * (AoI_i + lambda * (AoI_i / threshold_i)^alpha) + beta * queue_i

    All arguments except the scalars (alpha, lambd, beta) are per-node arrays
    of equal length. `thresholds` must be in the same units as `aoi`.
    """
    base_aoi = weights * aoi
    threshold_penalty = lambd * np.power(aoi / thresholds, alpha)
    queue_penalty = beta * queue
    return base_aoi + (weights * threshold_penalty) + queue_penalty


def calculate_reward(dui_scores: np.ndarray) -> float:
    """Reward is the negative sum of the network's total urgency."""
    return -float(np.sum(dui_scores))


def criticality_weighted_aoi(aoi: np.ndarray, weights: np.ndarray) -> float:
    """
    D6.1: the primary reporting statistic -- criticality-weighted mean AoI
    across nodes for a single slot/sample. Callers average this over slots
    to get the run-level statistic.
    """
    return float(np.sum(weights * aoi) / np.sum(weights))
