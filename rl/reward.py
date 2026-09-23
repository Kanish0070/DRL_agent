import numpy as np
from common.metrics import compute_dui, calculate_reward

def shaped_reward(info: dict, weights: np.ndarray, thresholds_s: np.ndarray, config: dict) -> float:
    aoi = info["aoi"]
    queue = info["queue_status"] 
    sched = config["scheduler"]
    
    dui = compute_dui(aoi, queue, weights, thresholds_s,
                       alpha=sched["dui_alpha"], lambd=sched["dui_lambda"], beta=sched["dui_beta"])
    base = calculate_reward(dui)

    lambda_energy = config["rl"]["lambda_energy"]
    lambda_waste = config["rl"]["lambda_waste"]
    waste_penalty = 0.0 if info["packet_arrived"] else 1.0
    return float(base - lambda_energy * info.get("total_energy", 0.0) - lambda_waste * waste_penalty)
