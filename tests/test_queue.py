"""Tests for the LCFS-1 queue with a sticky alarm latch (D2.3)."""

import pytest

from sim.queue import LcfsAlarmQueue


def test_starts_empty_until_first_sample_is_due():
    q = LcfsAlarmQueue(sample_interval_s=0.1, next_sample_due_s=0.1)
    assert q.occupied is False


def test_advance_to_generates_sample_when_due():
    q = LcfsAlarmQueue(sample_interval_s=0.1)
    q.advance_to(now_s=0.0)
    assert q.occupied is True
    assert q.generation_time_s == 0.0


def test_later_sample_overwrites_earlier_unsent_one():
    q = LcfsAlarmQueue(sample_interval_s=0.1)
    q.advance_to(now_s=0.0)
    q.advance_to(now_s=0.1)
    # Never sent between the two advances -- LCFS-1 overwrite, not a queue.
    assert q.generation_time_s == 0.1
    assert q.occupied is True


def test_multiple_periods_in_one_advance_keep_only_latest():
    q = LcfsAlarmQueue(sample_interval_s=0.1)
    q.advance_to(now_s=0.35)  # samples due at 0.0, 0.1, 0.2, 0.3
    assert q.generation_time_s == pytest.approx(0.3)


def test_take_empties_queue_and_returns_generation_time():
    q = LcfsAlarmQueue(sample_interval_s=0.1)
    q.advance_to(now_s=0.0)
    gen_time = q.take()
    assert gen_time == 0.0
    assert q.occupied is False


def test_take_on_empty_queue_returns_none():
    q = LcfsAlarmQueue(sample_interval_s=0.1, next_sample_due_s=1.0)
    assert q.take() is None


def test_alarm_latch_survives_overwrite_by_non_alarm_sample():
    q = LcfsAlarmQueue(sample_interval_s=0.1)
    q.advance_to(now_s=0.0, is_alarm=True)
    assert q.alarm_latched is True

    # A later, ordinary (non-alarm) sample overwrites the buffered data...
    q.advance_to(now_s=0.1, is_alarm=False)
    # ...but the latch must still be set (P8 acceptance criteria).
    assert q.alarm_latched is True


def test_alarm_latch_survives_being_taken():
    q = LcfsAlarmQueue(sample_interval_s=0.1)
    q.advance_to(now_s=0.0, is_alarm=True)
    q.take()
    assert q.alarm_latched is True


def test_ack_alarm_clears_latch():
    q = LcfsAlarmQueue(sample_interval_s=0.1)
    q.advance_to(now_s=0.0, is_alarm=True)
    q.ack_alarm()
    assert q.alarm_latched is False


def test_non_alarm_samples_never_set_latch():
    q = LcfsAlarmQueue(sample_interval_s=0.1)
    q.advance_to(now_s=0.0, is_alarm=False)
    assert q.alarm_latched is False
