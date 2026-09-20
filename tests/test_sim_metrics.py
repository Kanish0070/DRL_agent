"""Tests for sim/metrics.py (T2.3) -- a hand-checked short trace."""

import pytest

from sim.metrics import MetricsTracker


def test_no_delivery_ages_all_nodes_by_t_slot():
    tracker = MetricsTracker(n_nodes=4)
    tracker.step(granted_node=0, packet_arrived=False, delivered_age=0.0, t_slot=0.1)
    assert list(tracker.aoi) == pytest.approx([0.1, 0.1, 0.1, 0.1])


def test_delivery_resets_only_the_granted_node():
    tracker = MetricsTracker(n_nodes=4)
    tracker.step(granted_node=0, packet_arrived=False, delivered_age=0.0, t_slot=0.1)  # aoi -> [.1,.1,.1,.1]
    tracker.step(granted_node=1, packet_arrived=True, delivered_age=0.05, t_slot=0.1)
    assert tracker.aoi[0] == pytest.approx(0.2)   # not granted: keeps ageing
    assert tracker.aoi[1] == pytest.approx(0.05)  # granted + delivered: reset
    assert tracker.aoi[2] == pytest.approx(0.2)
    assert tracker.aoi[3] == pytest.approx(0.2)


def test_wasted_slot_costs_energy_but_resets_nothing():
    tracker = MetricsTracker(n_nodes=4, tx_power_proxy=2.0)
    tracker.step(granted_node=2, packet_arrived=False, delivered_age=0.0, t_slot=0.1)
    assert tracker.wasted_slots == 1
    assert tracker.total_energy == pytest.approx(0.2)  # 2.0 * 0.1
    assert list(tracker.aoi) == pytest.approx([0.1, 0.1, 0.1, 0.1])


def test_successful_delivery_still_costs_energy():
    tracker = MetricsTracker(n_nodes=4, tx_power_proxy=1.0)
    tracker.step(granted_node=0, packet_arrived=True, delivered_age=0.02, t_slot=0.1)
    assert tracker.total_energy == pytest.approx(0.1)
    assert tracker.wasted_slots == 0
    assert tracker.delivered_count[0] == 1


def test_twenty_slot_hand_traced_scenario():
    # Round-robin over 4 nodes, every delivery succeeds with age = t_slot
    # (the newest possible LCFS-1 sample). Slots 0..19 grant nodes
    # 0,1,2,3,0,1,2,3,...; the last round (slots 16-19) grants 0,1,2,3
    # respectively, so by the end: node 3 was just delivered (aoi=0.1),
    # node 2 aged one more slot since its slot-18 delivery (0.1+0.1=0.2),
    # node 1 aged two more since slot 17 (0.1+0.2=0.3), node 0 aged three
    # more since slot 16 (0.1+0.3=0.4).
    tracker = MetricsTracker(n_nodes=4)
    t_slot = 0.1
    for slot in range(20):
        granted = slot % 4
        tracker.step(granted, packet_arrived=True, delivered_age=t_slot, t_slot=t_slot)

    assert list(tracker.aoi) == pytest.approx([0.4, 0.3, 0.2, 0.1])
    assert list(tracker.delivered_count) == [5, 5, 5, 5]
    assert tracker.wasted_slots == 0
