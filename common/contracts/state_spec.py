import hashlib
import json
from dataclasses import dataclass, asdict
from typing import List, Tuple
import numpy as np

# Constants from Section 12.2 (Variable table)
DELTA_MAX = 10.0
W_MAX = 10.0
RSSI_MIN = -100.0
RSSI_RANGE = 70.0

@dataclass
class NodeState:
    aoi: float          # Δ_i in seconds
    queue: int          # q_i in {0, 1}
    rssi: float         # ρ_i in dBm
    weight: float       # w_i criticality weight

    def to_normalized_vector(self) -> np.ndarray:
        """Normalizes and returns the 4-D state vector for this node."""
        aoi_norm = min(self.aoi / DELTA_MAX, 1.0)
        queue_norm = float(self.queue)
        rssi_norm = max(0.0, min(1.0, (self.rssi - RSSI_MIN) / RSSI_RANGE))
        weight_norm = self.weight / W_MAX
        return np.array([aoi_norm, queue_norm, rssi_norm, weight_norm], dtype=np.float32)

@dataclass
class NetworkState:
    nodes: List[NodeState]  # Must be exactly 4 nodes
    
    def __post_init__(self):
        if len(self.nodes) != 4:
            raise ValueError("NetworkState requires exactly 4 NodeState objects")

    def to_vector(self) -> np.ndarray:
        """Flattens the network state into a 16-D normalized vector."""
        return np.concatenate([node.to_normalized_vector() for node in self.nodes])

def get_state_schema_hash() -> str:
    """
    Returns a hash of the state schema definition. 
    This is used to prevent silent train/deploy mismatches (D7.1 parity gate).
    """
    schema_def = {
        "dimensions": 16,
        "nodes": 4,
        "features_per_node": ["aoi_norm", "queue_norm", "rssi_norm", "weight_norm"],
        "normalizations": {
            "aoi_max": DELTA_MAX,
            "weight_max": W_MAX,
            "rssi_min": RSSI_MIN,
            "rssi_range": RSSI_RANGE
        }
    }
    encoded = json.dumps(schema_def, sort_keys=True).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()[:8]
