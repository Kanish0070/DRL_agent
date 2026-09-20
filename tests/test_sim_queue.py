"""Tests for sim/queue.py (T2.2, decision D2.3)."""

import pytest

from sim.queue import NodeQueue


def test_lcfs_rejects_capacity_other_than_one():
    with pytest.raises(ValueError):
        NodeQueue(discipline="lcfs", capacity=2)


def test_lcfs_overwrites_stale_sample_with_fresh_one():
    q = NodeQueue(discipline="lcfs", capacity=1)
    q.push()
    q.age_all(0.1)
    q.age_all(0.1)  # sample is now 0.2s old
    q.push()  # fresh sample arrives, overwrites the old one
    assert q.pop_for_delivery() == pytest.approx(0.0)


def test_lcfs_empty_after_delivery():
    q = NodeQueue(discipline="lcfs", capacity=1)
    q.push()
    q.pop_for_delivery()
    assert not q.has_data()


def test_pop_from_empty_queue_raises():
    q = NodeQueue(discipline="lcfs", capacity=1)
    with pytest.raises(ValueError):
        q.pop_for_delivery()


def test_alarm_latch_survives_data_overwrite():
    q = NodeQueue(discipline="lcfs", capacity=1)
    q.push(is_alarm=True)
    q.push(is_alarm=False)  # a routine sample overwrites the data...
    assert q.alarm_latched  # ...but the alarm must still be latched


def test_alarm_latch_cleared_only_explicitly():
    q = NodeQueue(discipline="lcfs", capacity=1)
    q.push(is_alarm=True)
    q.clear_alarm()
    assert not q.alarm_latched


def test_fifo_delivers_oldest_first():
    q = NodeQueue(discipline="fifo", capacity=3)
    q.push()  # sample A, age 0
    q.age_all(0.1)  # A is 0.1s old
    q.push()  # sample B, age 0
    # A is older (0.1s) than B (0.0s); FIFO must deliver A first.
    assert q.pop_for_delivery() == pytest.approx(0.1)
    assert q.pop_for_delivery() == pytest.approx(0.0)


def test_fifo_tail_drops_when_full():
    q = NodeQueue(discipline="fifo", capacity=2)
    q.push()
    q.push()
    q.push()  # capacity 2: this arrival is dropped
    delivered = [q.pop_for_delivery(), q.pop_for_delivery()]
    assert len(delivered) == 2
    assert not q.has_data()
