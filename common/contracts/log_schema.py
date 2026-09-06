from typing import List, Dict

# Frozen schema for the per-slot CSV logging (E15, F9.2)
SLOT_LOG_COLUMNS = [
    "slot_id",
    "timestamp_pi",
    "policy_id",
    "action_granted_node",
    "shield_fired",
    "uplink_received",
    "delivered_node",
    "delivered_age_us",
    "rssi_at_rx",
    "queue_status",
    "energy_proxy_cost",
    # Network metrics per slot
    "malformed_dropped",
    "stale_dropped",
    # State tracking per node
    "aoi_n1", "aoi_n2", "aoi_n3", "aoi_n4",
    "rssi_n1", "rssi_n2", "rssi_n3", "rssi_n4"
]

# JSONL Event Types
EVENT_NODE_HELLO = "NODE_HELLO"
EVENT_NODE_HEARTBEAT = "NODE_HEARTBEAT"
EVENT_NODE_UNREACHABLE = "NODE_UNREACHABLE"
EVENT_NODE_RECOVERED = "NODE_RECOVERED"
EVENT_SHIELD_ACTIVATED = "SHIELD_ACTIVATED"
EVENT_ALARM_ESCALATED = "ALARM_ESCALATED"
EVENT_ALARM_CLEARED = "ALARM_CLEARED"

def validate_slot_row(row: dict) -> bool:
    """Validates that a row dictionary matches the frozen CSV schema."""
    return set(row.keys()) == set(SLOT_LOG_COLUMNS)
