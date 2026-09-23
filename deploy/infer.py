import numpy as np
from common.contracts.state_spec import get_state_schema_hash

def infer(params: dict, obs: np.ndarray) -> np.ndarray:
    if "state_schema_hash" not in params or str(params["state_schema_hash"]) != get_state_schema_hash():
        raise ValueError("Mismatched state schema hash in exported model artifact!")
        
    x = obs
    n_layers = int(params["n_layers"])
    for i in range(n_layers):
        x = x @ params[f"w{i}"].T + params[f"b{i}"]
        if i < n_layers - 1:
            x = np.maximum(x, 0.0)  # ReLU
    return x
