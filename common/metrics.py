"""Dynamic Urgency Index (DUI) -- the reward metric formalized in
criticality_metric_plan.md (decision D3.1). A linear weighted-AoI term is
supplemented with a non-linear penalty that sharpens as a node's AoI
approaches its soft threshold, plus a queue-length term.

    DUI_i(t) = w_i * (Delta_i(t) + lambda * (Delta_i(t) / tau_i)^alpha) + beta * Q_i(t)
    R(t) = -sum_i DUI_i(t)

All inputs are plain numpy arrays over the 4 nodes, matching the ordering
used throughout the project (NetworkState.nodes, config.system.node_classes).
"""

import numpy as np


def compute_dui(
    aoi: np.ndarray,
    queue: np.ndarray,
    weights: np.ndarray,
    thresholds: np.ndarray,
    alpha: float,
    lambd: float,
    beta: float,
) -> np.ndarray:
    """Computes the Dynamic Urgency Index for every node."""
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
