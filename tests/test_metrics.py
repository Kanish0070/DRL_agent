"""Tests for the Dynamic Urgency Index (DUI) and reward (criticality_metric_plan.md)."""

import numpy as np

from common.metrics import calculate_reward, compute_dui, criticality_weighted_aoi

WEIGHTS = np.array([10.0, 10.0, 3.0, 1.0])
THRESHOLDS = np.array([0.2, 0.2, 0.5, 1.0])  # seconds


def test_dui_monotonicity_with_aoi():
    # For fixed queue and weight, DUI must strictly increase as AoI grows.
    queue = np.zeros(4)
    aoi_t0 = np.array([0.05, 0.05, 0.05, 0.05])
    aoi_t1 = aoi_t0 + 0.01

    dui_t0 = compute_dui(aoi_t0, queue, WEIGHTS, THRESHOLDS, alpha=2.0, lambd=1.5, beta=0.5)
    dui_t1 = compute_dui(aoi_t1, queue, WEIGHTS, THRESHOLDS, alpha=2.0, lambd=1.5, beta=0.5)

    assert np.all(dui_t1 > dui_t0)


def test_nonlinear_penalty_lets_near_threshold_node_overtake_higher_weight():
    # A low-weight node approaching its threshold should be able to overtake
    # a higher-weight node that still has a low AoI -- proving the alpha>=2
    # non-linear term actually creates urgency, not just the linear w*AoI term.
    queue = np.zeros(2)
    weights = np.array([10.0, 1.0])       # node 0 = urgent, node 1 = routine
    thresholds = np.array([0.2, 1.0])
    aoi = np.array([0.02, 0.95])          # node 0 fresh; node 1 nearly at its ceiling

    dui = compute_dui(aoi, queue, weights, thresholds, alpha=2.0, lambd=1.5, beta=0.5)

    assert dui[1] > dui[0]


def test_queue_penalty_increases_dui():
    aoi = np.array([0.05])
    weights = np.array([1.0])
    thresholds = np.array([1.0])

    dui_empty = compute_dui(aoi, np.array([0.0]), weights, thresholds, alpha=2.0, lambd=1.5, beta=0.5)
    dui_occupied = compute_dui(aoi, np.array([1.0]), weights, thresholds, alpha=2.0, lambd=1.5, beta=0.5)

    assert dui_occupied[0] > dui_empty[0]


def test_reward_is_negative_sum_of_dui():
    dui = np.array([1.0, 2.0, 3.0])
    assert calculate_reward(dui) == -6.0


def test_reward_improves_as_urgency_drops():
    high_urgency = np.array([5.0, 5.0])
    low_urgency = np.array([1.0, 1.0])
    assert calculate_reward(low_urgency) > calculate_reward(high_urgency)


def test_criticality_weighted_aoi_matches_manual_formula():
    aoi = np.array([0.1, 0.2, 0.3, 0.4])
    expected = float(np.sum(WEIGHTS * aoi) / np.sum(WEIGHTS))
    assert criticality_weighted_aoi(aoi, WEIGHTS) == expected


def test_criticality_weighted_aoi_dominated_by_high_weight_node():
    # Node 0 (weight 10) at high AoI should dominate the weighted mean even
    # though the other three nodes (weights 10, 3, 1) are all near zero.
    weights = np.array([10.0, 10.0, 3.0, 1.0])
    aoi_urgent_high = np.array([1.0, 0.0, 0.0, 0.0])
    aoi_routine_high = np.array([0.0, 0.0, 0.0, 1.0])

    assert (criticality_weighted_aoi(aoi_urgent_high, weights)
            > criticality_weighted_aoi(aoi_routine_high, weights))
