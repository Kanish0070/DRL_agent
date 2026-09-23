import numpy as np
from common.contracts.state_spec import DELTA_MAX, W_MAX, RSSI_MIN, RSSI_RANGE

def decode_observation(obs: np.ndarray, n_nodes: int = 4) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Inverse of NodeState.to_normalized_vector(), applied to all n_nodes
    at once. Must use the same constants as common.contracts.state_spec --
    import them, don't restate the numbers."""
    obs_reshaped = obs.reshape(n_nodes, 4)
    aoi = obs_reshaped[:, 0] * DELTA_MAX
    queue = obs_reshaped[:, 1]
    rssi = obs_reshaped[:, 2] * RSSI_RANGE + RSSI_MIN
    weights = obs_reshaped[:, 3] * W_MAX
    return aoi, rssi, queue, weights
