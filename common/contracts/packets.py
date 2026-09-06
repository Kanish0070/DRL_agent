import struct
from dataclasses import dataclass
from typing import Optional, bytes

MAGIC_BYTES = 0xA01D
VERSION = 1

# Message Types
MSG_GRANT = 0x01
MSG_DATA = 0x02
MSG_HEARTBEAT = 0x03
MSG_HELLO = 0x04
MSG_CONTROL = 0x05

# Flags
FLAG_ALARM_LATCHED = 1 << 0
FLAG_SENSOR_FAULT  = 1 << 1
FLAG_POST_REBOOT   = 1 << 2
FLAG_ALARM_ACK     = 1 << 3  # Added during self-audit to fix latch race

def crc16_ccitt(data: bytes) -> int:
    """CRC16-CCITT (poly 0x1021, init 0xFFFF)."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ 0x1021
            else:
                crc <<= 1
            crc &= 0xFFFF
    return crc

@dataclass
class PacketHeader:
    msg_type: int
    node_id: int
    flags: int

    def pack(self) -> bytes:
        # < = little-endian, H = u16, B = u8
        return struct.pack("<HBBBB", MAGIC_BYTES, VERSION, self.msg_type, self.node_id, self.flags)

    @classmethod
    def unpack(cls, data: bytes) -> Tuple['PacketHeader', bytes]:
        if len(data) < 6:
            raise ValueError("Packet too short for header")
        magic, version, msg_type, node_id, flags = struct.unpack("<HBBBB", data[:6])
        if magic != MAGIC_BYTES:
            raise ValueError(f"Invalid magic: {hex(magic)}")
        if version != VERSION:
            raise ValueError(f"Version mismatch: {version}")
        return cls(msg_type, node_id, flags), data[6:]

@dataclass
class GrantPacket:
    header: PacketHeader
    slot_id: int
    deadline_us: int
    
    def pack(self) -> bytes:
        payload = struct.pack("<II", self.slot_id, self.deadline_us)
        data = self.header.pack() + payload
        crc = crc16_ccitt(data)
        return data + struct.pack("<H", crc)

# TODO: Add DATA, HEARTBEAT, HELLO, CONTROL models similarly
