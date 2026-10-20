import os

content = '''import subprocess
import hashlib
import json
import socket
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any

from .config import load_system_config, load_measured_params
from .contracts.state_spec import get_state_schema_hash

def get_params_source() -> str:
    """
    Reports whether config/measured_params.yaml is still the pre-P1
    PLACEHOLDER file (see its header comment and
    docs/P1_NS3_ESP32_DELAY_CHARACTERISATION.md) or a real fit, so every run
    is traceable to which channel/timing parameter set produced it. This is
    what will let the eventual D11.1 sim-to-real gap comparison filter
    existing runs rather than needing a rerun, once T1.1-T1.7 lands a real
    fit and this file is updated to say so.
    """
    try:
        params = load_measured_params()
    except FileNotFoundError:
        return "unknown"
    return params.get("provenance", {}).get("source", "placeholder_pending_p1")

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

def generate_run_meta(policy_id: str, seed: int, model_path: str = None) -> Dict[str, Any]:
    """
    Generates the provenance metadata for a run, saving it to run_meta.json.
    Ensures every recorded experiment is traceable.
    """
    git_prov = get_git_provenance()
    meta = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "host": socket.gethostname(),
        "git_sha": git_prov["git_sha"],
        "is_dirty": git_prov["is_dirty"],
        "config_hash": get_config_hash(),
        "state_schema_hash": get_state_schema_hash(),
        "params_source": get_params_source(),
        "policy_id": policy_id,
        "seed": seed
    }
    if model_path and os.path.exists(model_path):
        with open(model_path, "rb") as mf:
            meta["model_path"] = model_path
            meta["model_sha256"] = hashlib.sha256(mf.read()).hexdigest()
    return meta

def write_run_meta(run_dir: Path, policy_id: str, seed: int, model_path: str = None):
    """Writes the metadata to the specified run directory."""
    run_dir = Path(run_dir)
    meta = generate_run_meta(policy_id, seed, model_path)
    run_dir.mkdir(parents=True, exist_ok=True)
    with open(run_dir / "run_meta.json", "w") as f:
        json.dump(meta, f, indent=2)
'''

with open("common/provenance.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Restored and fixed common/provenance.py")
