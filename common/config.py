import yaml
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Literal, Set

class ConfigValidationError(Exception):
    pass

def load_system_config(path: str | Path = "config/system.yaml") -> dict:
    """
    Loads and validates the system configuration.
    Rejects unknown keys and validates types/ranges.
    """
    path = Path(path)
    if not path.exists():
        # Fallback to looking relative to project root
        project_root = Path(__file__).parent.parent
        path = project_root / "config" / "system.yaml"
        if not path.exists():
            raise FileNotFoundError(f"Config file not found at {path}")
            
    with open(path, "r") as f:
        config = yaml.safe_load(f)
        
    _validate_schema(config)
    return config

def _validate_schema(config: dict):
    """Validates the config against the project schema."""
    expected_sections = {"system", "scheduler", "rl", "network"}
    actual_sections = set(config.keys())
    
    if not actual_sections.issubset(expected_sections):
        unknown = actual_sections - expected_sections
        raise ConfigValidationError(f"Unknown config sections found: {unknown}")

    # Validate System
    sys = config.get("system", {})
    if sys.get("n_nodes") != 4:
        raise ConfigValidationError("system.n_nodes must be exactly 4")
    if len(sys.get("node_classes", [])) != 4:
        raise ConfigValidationError("system.node_classes must have exactly 4 elements")

    # Validate Scheduler
    sched = config.get("scheduler", {})
    if sched.get("queue_discipline") not in ("lcfs", "fifo"):
        raise ConfigValidationError("scheduler.queue_discipline must be 'lcfs' or 'fifo'")
    if sched.get("queue_size") != 1:
        raise ConfigValidationError("scheduler.queue_size must be 1")
    if not isinstance(sched.get("dui_alpha"), (int, float)) or sched.get("dui_alpha") < 1.0:
        raise ConfigValidationError("scheduler.dui_alpha must be a number >= 1.0")

    # Validate Network
    net = config.get("network", {})
    if net.get("wifi_ps_mode") != "NONE":
        raise ConfigValidationError("network.wifi_ps_mode MUST be 'NONE' to avoid latency spikes")

if __name__ == "__main__":
    # Test loading
    cfg = load_system_config()
    print("Config loaded and validated successfully.")
