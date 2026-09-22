"""Tests for the P2 simulator core (T2.4) against its own task.md acceptance
criteria: deterministic per seed, no global RNG, AoI resets to the delivered
packet's age, the shield overrides ceiling violators, and throughput stays
well above a trivially-broken (e.g. accidentally O(n^2)) regression."""

import time

import numpy as np
import pytest

from common.config import load_measured_params, load_system_config
from common.metrics import calculate_reward
from sim.network import NetworkSimulator


def _minimal_config():
    return {
        "system": {"n_nodes": 4, "node_classes": ["urgent", "urgent", "important", "routine"]},
        "scheduler": {
            "weights": {"urgent": 10, "important": 3, "routine": 1},
            "thresholds": {"urgent": 200, "important": 500, "routine": 1000},
            "shield_ceilings_s": {"urgent": 2.0, "important": 6.0, "routine": 20.0},
            "dui_alpha": 2.0, "dui_lambda": 1.5, "dui_beta": 0.5,
        },
    }


def _minimal_measured_params(mean_rssi=(-65.0, -72.0, -80.0, -88.0), fading_std=0.0):
    return {
        "channel": {
            "r50_dbm": -82.0, "beta_db": 4.0,
            "node_mean_rssi_dbm": list(mean_rssi),
            "fading_std_db": fading_std,
            "t_slot_s": 0.1, "sample_interval_s": 0.1,
        },
        "provenance": {"source": "test_fixture"},
    }


def test_aoi_resets_to_delivered_packet_age_on_successful_delivery():
    sim = NetworkSimulator(_minimal_config(),
                            _minimal_measured_params(mean_rssi=(-30.0, -30.0, -30.0, -30.0)),
                            seed=0)

    result = sim.step(action=0)

    assert result.uplink_received is True
    assert result.delivered_node == 0
    assert result.aoi[0] == pytest.approx(result.delivered_age_s)
    assert result.aoi[0] != 0.0


def test_non_granted_nodes_age_by_slot_duration():
    sim = NetworkSimulator(_minimal_config(), _minimal_measured_params(), seed=0)
    result = sim.step(action=0)
    assert result.aoi[1] == pytest.approx(0.1)
    assert result.aoi[2] == pytest.approx(0.1)
    assert result.aoi[3] == pytest.approx(0.1)


def test_shield_overrides_action_for_ceiling_violator():
    sim = NetworkSimulator(_minimal_config(), _minimal_measured_params(), seed=0)
    sim.aoi[3] = 25.0  # routine's shield ceiling is 20.0s -> violation

    result = sim.step(action=0)  # policy proposes node 0

    assert result.shield_fired is True
    assert result.granted_node == 3


def test_shield_does_not_fire_below_ceiling():
    sim = NetworkSimulator(_minimal_config(), _minimal_measured_params(), seed=0)
    result = sim.step(action=2)
    assert result.shield_fired is False
    assert result.granted_node == 2


def test_rejects_out_of_range_action():
    sim = NetworkSimulator(_minimal_config(), _minimal_measured_params(), seed=0)
    with pytest.raises(ValueError):
        sim.step(action=4)


def test_reward_matches_calculate_reward_of_dui():
    sim = NetworkSimulator(_minimal_config(), _minimal_measured_params(), seed=0)
    result = sim.step(action=0)
    assert sim.reward(result) == calculate_reward(result.dui)


def _run_round_robin(config, params, seed, n_slots=50):
    sim = NetworkSimulator(config, params, seed=seed)
    rows = []
    for slot in range(n_slots):
        result = sim.step(slot % sim.n_nodes)
        rows.append((result.granted_node, result.uplink_received, result.delivered_node,
                      tuple(result.aoi.tolist()), tuple(result.rssi.tolist())))
    return rows


def test_same_seed_produces_bitwise_identical_run():
    config = load_system_config("config/system.yaml")
    params = load_measured_params("config/measured_params.yaml")
    assert _run_round_robin(config, params, seed=123) == _run_round_robin(config, params, seed=123)


def test_different_seeds_produce_different_runs():
    config = load_system_config("config/system.yaml")
    params = load_measured_params("config/measured_params.yaml")
    assert _run_round_robin(config, params, seed=1) != _run_round_robin(config, params, seed=2)


def test_no_global_rng_interference_between_instances():
    config = load_system_config("config/system.yaml")
    params = load_measured_params("config/measured_params.yaml")

    sim_a = NetworkSimulator(config, params, seed=11)
    solo = [sim_a.step(0).aoi.copy() for _ in range(5)]

    sim_b = NetworkSimulator(config, params, seed=11)
    sim_c = NetworkSimulator(config, params, seed=999)
    interleaved = []
    for _ in range(5):
        interleaved.append(sim_b.step(0).aoi.copy())
        sim_c.step(0)

    for solo_aoi, interleaved_aoi in zip(solo, interleaved):
        assert np.array_equal(solo_aoi, interleaved_aoi)


def test_meets_minimum_throughput_smoke():
    config = load_system_config("config/system.yaml")
    params = load_measured_params("config/measured_params.yaml")
    sim = NetworkSimulator(config, params, seed=0)

    n_slots = 20000
    start = time.perf_counter()
    for slot in range(n_slots):
        sim.step(slot % sim.n_nodes)
    elapsed = time.perf_counter() - start

    # Generous CI-safe floor (P2's real target is >=1e4 slots/sec); this
    # only guards against an accidental order-of-magnitude regression.
    assert n_slots / elapsed > 3000
