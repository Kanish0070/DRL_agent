"""Tests for the frozen 16-D state vector contract (D4.1) and its parity
hash (D7.1), which guards against silent train/deploy drift."""

import numpy as np
import pytest

from common.contracts.state_spec import (
    DELTA_MAX,
    NetworkState,
    NodeState,
    RSSI_MIN,
    RSSI_RANGE,
    W_MAX,
    get_state_schema_hash,
)


def test_node_state_normalizes_mid_range_values():
    node = NodeState(aoi=1.0, queue=1, rssi=-65.0, weight=10.0)
    vec = node.to_normalized_vector()
    assert vec.shape == (4,)
    assert vec[0] == pytest.approx(1.0 / DELTA_MAX)
    assert vec[1] == 1.0
    assert vec[2] == pytest.approx((-65.0 - RSSI_MIN) / RSSI_RANGE)
    assert vec[3] == pytest.approx(10.0 / W_MAX)


def test_node_state_clamps_aoi_above_delta_max():
    node = NodeState(aoi=DELTA_MAX * 5, queue=0, rssi=-60.0, weight=1.0)
    assert node.to_normalized_vector()[0] == 1.0


def test_node_state_clamps_rssi_outside_range():
    below = NodeState(aoi=0.0, queue=0, rssi=RSSI_MIN - 50, weight=1.0)
    above = NodeState(aoi=0.0, queue=0, rssi=RSSI_MIN + RSSI_RANGE + 50, weight=1.0)
    assert below.to_normalized_vector()[2] == 0.0
    assert above.to_normalized_vector()[2] == 1.0


def test_network_state_requires_exactly_four_nodes():
    node = NodeState(aoi=0.0, queue=0, rssi=-60.0, weight=1.0)
    with pytest.raises(ValueError):
        NetworkState(nodes=[node, node, node])


def test_network_state_flattens_to_16d_vector():
    nodes = [NodeState(aoi=float(i), queue=i % 2, rssi=-60.0, weight=1.0) for i in range(4)]
    vec = NetworkState(nodes=nodes).to_vector()
    assert vec.shape == (16,)
    assert vec.dtype == np.float32


def test_schema_hash_is_deterministic():
    assert get_state_schema_hash() == get_state_schema_hash()


def test_schema_hash_matches_frozen_golden_value():
    # Regression guard: this MUST only change alongside a deliberate,
    # reviewed change to the state schema (dimensions/features/normalization
    # constants). If this test breaks unexpectedly, something silently
    # changed the state contract -- that is exactly the drift D7.1 exists
    # to catch, on both the training and deployment sides.
    assert get_state_schema_hash() == "7c486950"
