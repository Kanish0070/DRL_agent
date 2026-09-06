import subprocess
import hashlib
import json
import socket
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

from .config import load_system_config
from .contracts.state_spec import get_state_schema_hash

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
        "policy_id": policy_id,
        "seed": seed
    }

def write_run_meta(run_dir: Path, policy_id: str, seed: int):
    """Writes the metadata to the specified run directory."""
    meta = generate_run_meta(policy_id, seed)
    run_dir.mkdir(parents=True, exist_ok=True)
    with open(run_dir / "run_meta.json", "w") as f:
        json.dump(meta, f, indent=2)
