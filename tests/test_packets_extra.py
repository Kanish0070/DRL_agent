import struct
from common.contracts.packets import (
    DataPacket, HeartbeatPacket, HelloPacket, ControlPacket,
    MSG_DATA, MSG_HEARTBEAT, MSG_HELLO, MSG_CONTROL,
    PacketHeader, crc16_ccitt
)

def test_data_packet_golden_bytes():
    header = PacketHeader(msg_type=MSG_DATA, node_id=1, flags=0)
    packet = DataPacket(header=header, slot_id=1, age_at_tx_us=100_000)
    packed = packet.pack()
    assert len(packed) == 6 + 8 + 2
    body, crc_bytes = packed[:-2], packed[-2:]
    (crc,) = struct.unpack("<H", crc_bytes)
    assert crc == crc16_ccitt(body)

def test_heartbeat_packet_golden_bytes():
    header = PacketHeader(msg_type=MSG_HEARTBEAT, node_id=1, flags=0)
    packet = HeartbeatPacket(header=header, rssi=-65)
    packed = packet.pack()
    assert len(packed) == 6 + 4 + 2
    body, crc_bytes = packed[:-2], packed[-2:]
    (crc,) = struct.unpack("<H", crc_bytes)
    assert crc == crc16_ccitt(body)

def test_hello_packet_golden_bytes():
    header = PacketHeader(msg_type=MSG_HELLO, node_id=1, flags=0)
    packet = HelloPacket(header=header)
    packed = packet.pack()
    assert len(packed) == 6 + 0 + 2
    body, crc_bytes = packed[:-2], packed[-2:]
    (crc,) = struct.unpack("<H", crc_bytes)
    assert crc == crc16_ccitt(body)

def test_control_packet_golden_bytes():
    header = PacketHeader(msg_type=MSG_CONTROL, node_id=1, flags=0)
    packet = ControlPacket(header=header, command_code=2)
    packed = packet.pack()
    assert len(packed) == 6 + 1 + 2
    body, crc_bytes = packed[:-2], packed[-2:]
    (crc,) = struct.unpack("<H", crc_bytes)
    assert crc == crc16_ccitt(body)
