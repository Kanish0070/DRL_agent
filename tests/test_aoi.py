"""Tests for the single authoritative AoI implementation (D0.1, D2.1)."""

from common.contracts.aoi import compute_delivered_age, update_aoi_for_slot


def test_no_packet_ages_by_slot_duration():
    assert update_aoi_for_slot(current_aoi=1.5, packet_arrived=False,
                                delivered_age=999.0, t_slot=0.1) == 1.5 + 0.1


def test_packet_arrival_resets_to_delivered_age():
    # current_aoi and t_slot must be ignored entirely on arrival (D0.1):
    # AoI resets to the age of the delivered packet, not to zero.
    result = update_aoi_for_slot(current_aoi=8.0, packet_arrived=True,
                                  delivered_age=0.037, t_slot=0.1)
    assert result == 0.037


def test_aoi_never_resets_to_zero_on_arrival():
    result = update_aoi_for_slot(current_aoi=5.0, packet_arrived=True,
                                  delivered_age=0.02, t_slot=0.1)
    assert result != 0.0


def test_compute_delivered_age_matches_manual_formula():
    # generation_age = age_at_tx_us (as seconds) + estimated uplink delay;
    # total age adds the time elapsed since the packet was received (D2.1).
    t_now_pi = 100.5
    t_rx_pi = 100.0
    age_at_tx_us = 20_000  # 20 ms spent on-node before TX
    d_up_hat = 0.005  # 5 ms estimated uplink delay

    expected = (t_now_pi - t_rx_pi) + (age_at_tx_us * 1e-6) + d_up_hat
    assert compute_delivered_age(t_now_pi, t_rx_pi, age_at_tx_us, d_up_hat) == expected


def test_compute_delivered_age_grows_with_time_since_rx():
    age_at_tx_us = 0
    d_up_hat = 0.0
    earlier = compute_delivered_age(t_now_pi=100.1, t_rx_pi=100.0,
                                     age_at_tx_us=age_at_tx_us, d_up_hat=d_up_hat)
    later = compute_delivered_age(t_now_pi=100.9, t_rx_pi=100.0,
                                   age_at_tx_us=age_at_tx_us, d_up_hat=d_up_hat)
    assert later > earlier
