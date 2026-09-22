"""Tests for the logistic p_s(RSSI) channel model (D1.2) and RSSI sampling."""

import numpy as np
import pytest

from common.config import load_measured_params
from sim.channel import ChannelModel, delivery_probability


def test_delivery_probability_is_half_at_r50():
    assert delivery_probability(-82.0, r50_dbm=-82.0, beta_db=4.0) == pytest.approx(0.5)


def test_delivery_probability_increases_with_rssi():
    weak = delivery_probability(-90.0, r50_dbm=-82.0, beta_db=4.0)
    strong = delivery_probability(-60.0, r50_dbm=-82.0, beta_db=4.0)
    assert strong > weak


def test_delivery_probability_stays_in_unit_interval():
    rssi = np.array([-120.0, -82.0, 0.0])
    ps = delivery_probability(rssi, r50_dbm=-82.0, beta_db=4.0)
    assert np.all(ps >= 0.0) and np.all(ps <= 1.0)


def test_measured_params_load_and_validate():
    params = load_measured_params("config/measured_params.yaml")
    assert len(params["channel"]["node_mean_rssi_dbm"]) == 4
    assert params["provenance"]["source"] == "ns3_derived_placeholder"


def _make_model(seed: int) -> ChannelModel:
    params = load_measured_params("config/measured_params.yaml")
    rng = np.random.default_rng(seed)
    return ChannelModel.from_measured_params(params, rng)


def test_same_seed_is_bitwise_deterministic():
    model_a = _make_model(seed=42)
    model_b = _make_model(seed=42)

    rssi_a = [model_a.sample_rssi().copy() for _ in range(5)]
    rssi_b = [model_b.sample_rssi().copy() for _ in range(5)]

    for a, b in zip(rssi_a, rssi_b):
        assert np.array_equal(a, b)


def test_different_seeds_diverge():
    model_a = _make_model(seed=1)
    model_b = _make_model(seed=2)

    rssi_a = model_a.sample_rssi()
    rssi_b = model_b.sample_rssi()

    assert not np.array_equal(rssi_a, rssi_b)


def test_two_models_do_not_share_global_rng_state():
    # Interleaving draws from two independently-seeded models must not
    # perturb each other -- proves no global np.random state is touched.
    model_a = _make_model(seed=7)
    model_b = _make_model(seed=7)

    solo = [model_a.sample_rssi().copy() for _ in range(3)]

    model_c = _make_model(seed=99)
    interleaved = []
    for _ in range(3):
        interleaved.append(model_b.sample_rssi().copy())
        model_c.sample_rssi()

    for a, b in zip(solo, interleaved):
        assert np.array_equal(a, b)


def test_try_deliver_is_bernoulli_with_expected_rate():
    rng = np.random.default_rng(123)
    model = ChannelModel(
        node_mean_rssi_dbm=[-82.0, -82.0, -82.0, -82.0],
        r50_dbm=-82.0, beta_db=4.0, fading_std_db=0.0, rng=rng,
    )
    model.sample_rssi()  # RSSI == r50 exactly (no jitter) -> p_s == 0.5

    outcomes = [model.try_deliver(0) for _ in range(4000)]
    rate = sum(outcomes) / len(outcomes)
    assert 0.45 < rate < 0.55
