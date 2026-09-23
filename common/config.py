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

def load_measured_params(path: str | Path = "config/measured_params.yaml") -> dict:
    """
    Loads and validates the channel/timing parameters produced by the real P1
    hardware campaign (task.md T1.1-T1.7, currently blocked) -- see
    docs/P1_NS3_ESP32_DELAY_CHARACTERISATION.md for the approved hybrid
    NS3+ESP32 methodology, and this file's own header for which values are
    still PLACEHOLDER in the meantime. Every consumer (sim/channel.py) reads
    this file rather
    than the campaign that produced it, so swapping a real fit in later
    needs no code changes.
    """
    path = Path(path)
    if not path.exists():
        project_root = Path(__file__).parent.parent
        path = project_root / "config" / "measured_params.yaml"
        if not path.exists():
            raise FileNotFoundError(f"Measured params file not found at {path}")

    with open(path, "r") as f:
        params = yaml.safe_load(f)

    _validate_measured_params(params)
    return params

def _validate_measured_params(params: dict):
    """Validates the measured_params.yaml schema against what
    sim.channel.ChannelParams.from_measured_params() and NetworkSim's
    SimConfig.from_configs() actually read."""
    if "channel" not in params:
        raise ConfigValidationError("measured_params.yaml missing 'channel' section")
    if "timing" not in params:
        raise ConfigValidationError("measured_params.yaml missing 'timing' section")

    ch = params["channel"]
    required_channel = {"path_loss_exponent", "reference_distance_m", "reference_loss_db",
                         "shadowing_sigma_db", "shadowing_correlation_rho",
                         "logistic_r50_dbm", "logistic_slope_db",
                         "ge_prob_good_to_bad", "ge_prob_bad_to_good",
                         "ge_bad_state_success_multiplier"}
    missing_channel = required_channel - set(ch.keys())
    if missing_channel:
        raise ConfigValidationError(f"measured_params.yaml 'channel' section missing: {missing_channel}")

    timing = params["timing"]
    required_timing = {"slot_duration_s", "uplink_delay_median_s", "late_arrival_probability"}
    missing_timing = required_timing - set(timing.keys())
    if missing_timing:
        raise ConfigValidationError(f"measured_params.yaml 'timing' section missing: {missing_timing}")

if __name__ == "__main__":
    # Test loading
    cfg = load_system_config()
    print("Config loaded and validated successfully.")
