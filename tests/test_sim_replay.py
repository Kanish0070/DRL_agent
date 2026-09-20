"""Tests for sim/replay.py (T2.5)."""

import csv

import pytest

from common.contracts.log_schema import SLOT_LOG_COLUMNS
from sim.replay import replay_log


def _write_synthetic_log(path, n_slots=20, t_slot=0.1):
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=SLOT_LOG_COLUMNS)
        writer.writeheader()
        for slot in range(1, n_slots + 1):
            granted = (slot - 1) % 4
            writer.writerow({
                "slot_id": slot, "timestamp_pi": slot * t_slot, "policy_id": "rr",
                "action_granted_node": granted, "shield_fired": 0,
                "uplink_received": 1, "delivered_node": granted,
                "delivered_age_us": int(t_slot * 1e6), "rssi_at_rx": -55.0,
                "queue_status": 1, "energy_proxy_cost": 1.0,
                "malformed_dropped": 0, "stale_dropped": 0,
                "aoi_n1": 0, "aoi_n2": 0, "aoi_n3": 0, "aoi_n4": 0,
                "rssi_n1": -50.0, "rssi_n2": -55.0, "rssi_n3": -63.0, "rssi_n4": -72.0,
            })


def test_replay_matches_direct_metrics_computation(tmp_path):
    log_path = tmp_path / "synthetic.csv"
    _write_synthetic_log(log_path, n_slots=20)

    summary = replay_log(log_path, t_slot=0.1)

    assert summary["n_rows"] == 20
    # 20 slots round-robin over 4 nodes -> each delivered exactly 5 times,
    # every delivery is the freshest possible sample (age = t_slot). The
    # last round grants 0,1,2,3 in order, so by the final slot each node
    # has aged since its own last delivery by a different amount (see
    # test_sim_metrics.py::test_twenty_slot_hand_traced_scenario for the
    # full derivation).
    assert list(summary["delivered_count"]) == [5, 5, 5, 5]
    assert summary["final_aoi"] == pytest.approx([0.4, 0.3, 0.2, 0.1])
    assert summary["wasted_slots"] == 0


def test_replay_rejects_mismatched_schema(tmp_path):
    bad_path = tmp_path / "bad.csv"
    with open(bad_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["not", "the", "right", "columns"])
        writer.writerow([1, 2, 3, 4])

    with pytest.raises(ValueError, match="do not match SLOT_LOG_COLUMNS"):
        replay_log(bad_path, t_slot=0.1)
