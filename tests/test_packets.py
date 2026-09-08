"""Tests for the wire packet contract: header framing, CRC16, and a
golden-bytes fixture for GrantPacket (P0 acceptance criterion)."""

import struct

import pytest

from common.contracts.packets import (
    FLAG_ALARM_LATCHED,
    GrantPacket,
    MAGIC_BYTES,
    MSG_GRANT,
    PacketHeader,
    VERSION,
    crc16_ccitt,
)


def test_crc16_matches_standard_check_value():
    # CRC-16/CCITT-FALSE reference check value for ASCII "123456789".
    assert crc16_ccitt(b"123456789") == 0x29B1


def test_header_pack_is_six_bytes():
    header = PacketHeader(msg_type=MSG_GRANT, node_id=2, flags=0)
    assert len(header.pack()) == 6


def test_header_round_trips_through_pack_unpack():
    header = PacketHeader(msg_type=MSG_GRANT, node_id=3, flags=FLAG_ALARM_LATCHED)
    packed = header.pack() + b"\x01\x02\x03"
    unpacked, rest = PacketHeader.unpack(packed)
    assert unpacked == header
    assert rest == b"\x01\x02\x03"


def test_header_unpack_rejects_bad_magic():
    bad = struct.pack("<HBBBB", 0xDEAD, VERSION, MSG_GRANT, 0, 0)
    with pytest.raises(ValueError, match="Invalid magic"):
        PacketHeader.unpack(bad)


def test_header_unpack_rejects_version_mismatch():
    bad = struct.pack("<HBBBB", MAGIC_BYTES, VERSION + 1, MSG_GRANT, 0, 0)
    with pytest.raises(ValueError, match="Version mismatch"):
        PacketHeader.unpack(bad)


def test_header_unpack_rejects_short_buffer():
    with pytest.raises(ValueError, match="too short"):
        PacketHeader.unpack(b"\x00\x01\x02")


def test_grant_packet_golden_bytes():
    """
    Golden-bytes fixture (P0 acceptance criterion): a fixed GrantPacket
    must always serialize to this exact byte sequence. If this breaks,
    the wire format changed -- which means every node in the field would
    need reflashing, so it must never happen silently.
    """
    header = PacketHeader(msg_type=MSG_GRANT, node_id=2, flags=0)
    packet = GrantPacket(header=header, slot_id=42, deadline_us=100_000)

    packed = packet.pack()

    assert packed.hex() == "1da0010102002a000000a0860100e525"
    assert len(packed) == 6 + 8 + 2  # header + (slot_id, deadline_us) + crc16


def test_grant_packet_crc_is_over_header_and_payload_only():
    header = PacketHeader(msg_type=MSG_GRANT, node_id=1, flags=0)
    packet = GrantPacket(header=header, slot_id=1, deadline_us=1)
    packed = packet.pack()

    body, crc_bytes = packed[:-2], packed[-2:]
    (crc,) = struct.unpack("<H", crc_bytes)
    assert crc == crc16_ccitt(body)
