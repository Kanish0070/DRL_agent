"""Tests for the Dynamic Urgency Index reward metric (criticality_metric_plan.md)."""

import numpy as np
import pytest

from common.metrics import calculate_reward, compute_dui


def _dui_of(aoi, weight=10.0, threshold=0.2, alpha=2.0, lambd=1.5, beta=0.5, queue=1.0):
    return compute_dui(
        aoi=np.array([aoi]), queue=np.array([queue]), weights=np.array([weight]),
        thresholds=np.array([threshold]), alpha=alpha, lambd=lambd, beta=beta,
    )[0]


def test_dui_monotonicity_in_aoi():
    # For fixed weight/queue, DUI must strictly increase as AoI grows.
    earlier = _dui_of(aoi=0.05)
    later = _dui_of(aoi=0.15)
    assert later > earlier


def test_dui_nonlinear_term_overtakes_higher_weight_low_aoi_node():
    # A low-AoI, high-weight node vs. a node approaching its own threshold:
    # the non-linear penalty should let the near-threshold node win even
    # with a smaller weight, proving the threshold term actually matters.
    near_threshold = _dui_of(aoi=0.19, weight=3.0, threshold=0.2)
    far_from_threshold_high_weight = _dui_of(aoi=0.01, weight=10.0, threshold=0.2)
    assert near_threshold > far_from_threshold_high_weight


def test_dui_zero_alpha_lambda_reduces_to_linear_plus_queue():
    aoi = np.array([1.0, 2.0])
    queue = np.array([0.0, 1.0])
    weights = np.array([10.0, 3.0])
    thresholds = np.array([0.2, 0.5])

    dui = compute_dui(aoi, queue, weights, thresholds, alpha=2.0, lambd=0.0, beta=0.5)
    expected_linear = weights * aoi + 0.5 * queue
    assert dui == pytest.approx(expected_linear)


def test_calculate_reward_is_negative_sum():
    dui_scores = np.array([1.0, 2.0, 3.0, 4.0])
    assert calculate_reward(dui_scores) == pytest.approx(-10.0)


def test_calculate_reward_higher_urgency_gives_more_negative_reward():
    low_urgency = calculate_reward(np.array([0.1, 0.1, 0.1, 0.1]))
    high_urgency = calculate_reward(np.array([5.0, 5.0, 5.0, 5.0]))
    assert high_urgency < low_urgency
