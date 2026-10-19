import os
import hashlib
from pathlib import Path

filepath = "common/provenance.py"
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

if "model_path: str = None" not in content:
    content = content.replace("def generate_run_meta(policy_id: str, seed: int) -> Dict[str, Any]:", "def generate_run_meta(policy_id: str, seed: int, model_path: str = None) -> Dict[str, Any]:")
    
    body_insert = """
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
"""
    # Replace the return dict with this
    import re
    content = re.sub(r"return \{(.*?)\}", body_insert.strip(), content, flags=re.DOTALL)
    
    content = content.replace("def write_run_meta(run_dir: Path, policy_id: str, seed: int):", "def write_run_meta(run_dir: Path, policy_id: str, seed: int, model_path: str = None):")
    content = content.replace("meta = generate_run_meta(policy_id, seed)", "meta = generate_run_meta(policy_id, seed, model_path)")
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Updated provenance.py for model hashing")

trainpath = "rl/train.py"
with open(trainpath, 'r', encoding='utf-8') as f:
    tcontent = f.read()
    
tcontent = tcontent.replace(
    'write_run_meta(f"models/dqn_seed{seed}", policy_id="dqn", seed=seed)',
    'write_run_meta(f"models/dqn_seed{seed}_meta", policy_id="dqn", seed=seed, model_path=f"models/dqn_seed{seed}.zip")'
)
with open(trainpath, 'w', encoding='utf-8') as f:
    f.write(tcontent)
print("Updated rl/train.py to pass model_path")
