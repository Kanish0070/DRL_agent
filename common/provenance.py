import subprocess
import hashlib
import json
import socket
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

from .config import load_system_config, load_measured_params
from .contracts.state_spec import get_state_schema_hash

def get_params_source() -> str:
    """
    Returns the provenance.source tag of config/measured_params.yaml (e.g.
    "hardware" once T1.1-T1.7 lands, or "ns3_derived_placeholder" for the
    no-hardware substitute), so every run is traceable to which channel/
    timing parameter set produced it. This is what makes the eventual
    D11.1 sim-to-real gap comparison a filter over existing runs rather
    than a rerun.
    """
    try:
        params = load_measured_params()
    except FileNotFoundError:
        return "unknown"
    return params.get("provenance", {}).get("source", "unknown")

def get_git_provenance() -> dict:
    """Returns the current git commit SHA and dirty state."""
    try:
        sha = subprocess.check_output(["git", "rev-parse", "HEAD"]).decode("utf-8").strip()
        dirty = subprocess.call(["git", "diff", "--quiet"]) != 0
        return {"git_sha": sha, "is_dirty": dirty}
    except subprocess.SubprocessError:
        return {"git_sha": "unknown", "is_dirty": True}

def get_config_hash() -> str:
    """Returns a hash of the loaded system config."""
    config = load_system_config()
    encoded = json.dumps(config, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:8]

def generate_run_meta(policy_id: str, seed: int) -> Dict[str, Any]:
    """
    Generates the provenance metadata for a run, saving it to run_meta.json.
    Ensures every recorded experiment is traceable.
    """
    git_prov = get_git_provenance()
    return {
        "timestamp_utc": datetime.utcnow().isoformat() + "Z",
        "host": socket.gethostname(),
        "git_sha": git_prov["git_sha"],
        "is_dirty": git_prov["is_dirty"],
        "config_hash": get_config_hash(),
        "state_schema_hash": get_state_schema_hash(),
        "params_source": get_params_source(),
        "policy_id": policy_id,
        "seed": seed
    }

def write_run_meta(run_dir: Path, policy_id: str, seed: int):
    """Writes the metadata to the specified run directory."""
    meta = generate_run_meta(policy_id, seed)
    run_dir.mkdir(parents=True, exist_ok=True)
    with open(run_dir / "run_meta.json", "w") as f:
        json.dump(meta, f, indent=2)
