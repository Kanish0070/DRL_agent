"""Tests for sim/channel.py (T2.1)."""

import numpy as np
import pytest
import yaml

from sim.channel import ChannelModel, ChannelParams, path_loss_db, success_probability_from_rssi

MEASURED_PARAMS_PATH = "config/measured_params.yaml"


@pytest.fixture
def params() -> ChannelParams:
    with open(MEASURED_PARAMS_PATH) as f:
        raw = yaml.safe_load(f)
    return ChannelParams.from_measured_params(raw)


def test_path_loss_increases_with_distance(params):
    losses = path_loss_db(np.array([5.0, 10.0, 20.0]), params)
    assert losses[0] < losses[1] < losses[2]


def test_success_probability_decreases_with_worse_rssi(params):
    strong = success_probability_from_rssi(np.array([-40.0]), params)[0]
    weak = success_probability_from_rssi(np.array([-100.0]), params)[0]
    assert strong > weak


def test_success_probability_is_half_at_r50(params):
    p = success_probability_from_rssi(np.array([params.logistic_r50_dbm]), params)[0]
    assert p == pytest.approx(0.5)


def test_channel_step_is_deterministic_given_seed(params):
    distances = np.array([5.0, 8.0, 12.0, 18.0])

    rng_a = np.random.Generator(np.random.PCG64(42))
    channel_a = ChannelModel(distances, params)
    trace_a = []
    for _ in range(50):
        channel_a.step(rng_a)
        trace_a.append(channel_a.rssi_all().copy())

    rng_b = np.random.Generator(np.random.PCG64(42))
    channel_b = ChannelModel(distances, params)
    trace_b = []
    for _ in range(50):
        channel_b.step(rng_b)
        trace_b.append(channel_b.rssi_all().copy())

    for a, b in zip(trace_a, trace_b):
        assert np.array_equal(a, b)


def test_closer_node_has_better_rssi_on_average(params):
    distances = np.array([5.0, 40.0])
    channel = ChannelModel(distances, params)
    rng = np.random.Generator(np.random.PCG64(1))

    close_rssi, far_rssi = [], []
    for _ in range(2000):
        channel.step(rng)
        close_rssi.append(channel.rssi(0))
        far_rssi.append(channel.rssi(1))

    assert np.mean(close_rssi) > np.mean(far_rssi)


def test_gilbert_elliott_state_transitions_occur(params):
    # With enough slots, the burst chain must actually visit BAD at least
    # once (prob_good_to_bad=0.02 over thousands of slots).
    distances = np.array([10.0])
    channel = ChannelModel(distances, params)
    rng = np.random.Generator(np.random.PCG64(7))

    visited_bad = False
    for _ in range(5000):
        channel.step(rng)
        if channel.ge_state[0] == 1:
            visited_bad = True
            break
    assert visited_bad
