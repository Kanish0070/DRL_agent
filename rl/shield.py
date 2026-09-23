import numpy as np

def apply_safety_shield(proposed_action: int, aoi: np.ndarray, weights: np.ndarray, shield_ceilings_s: np.ndarray) -> tuple[int, bool]:
    """Force-grants the highest-urgency ceiling violator, if any. Mirrors
    ns3-sim/aoi-scheduler-sim.cc's SlotTick shield block (lines 432-448)."""
    violations = aoi >= shield_ceilings_s
    if not np.any(violations):
        return proposed_action, False
    urgency = weights * aoi
    urgency_masked = np.where(violations, urgency, -np.inf)
    return int(np.argmax(urgency_masked)), True
