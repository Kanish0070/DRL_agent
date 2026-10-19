import os
import re

def replace_in_file(filepath, old, new):
    if not os.path.exists(filepath):
        print(f"Skipping {filepath}, does not exist.")
        return
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    if old in content:
        content = content.replace(old, new)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Updated {filepath}")
    else:
        print(f"Could not find target string in {filepath}")

# 1. eval/run.py
replace_in_file("eval/run.py",
    'def get_scheduler(name: str, sys_cfg: dict, meas_cfg: dict):',
    'def get_scheduler(name: str, sys_cfg: dict, meas_cfg: dict, seed: int = None):'
)
replace_in_file("eval/run.py",
    'if name == "random": return RandomScheduler()',
    'if name == "random": return RandomScheduler(seed=seed)'
)
replace_in_file("eval/run.py",
    'parser.add_argument("--scheduler", required=True, choices=["rr", "fpq", "maxweight", "cag", "random", "oracle", "dqn"])\n    parser.add_argument("--model-path"',
    'parser.add_argument("--scheduler", required=True, choices=["rr", "fpq", "maxweight", "cag", "random", "oracle", "dqn"])\n    parser.add_argument("--train-seed", type=int, help="Training seed for DQN models")\n    parser.add_argument("--model-path"'
)
replace_in_file("eval/run.py",
    'scheduler = get_scheduler(args.scheduler, sys_cfg, meas_cfg) if args.scheduler != "dqn" else None',
    'scheduler = get_scheduler(args.scheduler, sys_cfg, meas_cfg, args.seed) if args.scheduler != "dqn" else None'
)
replace_in_file("eval/run.py",
    'out_dir = Path(args.out_dir) / f"{args.scheduler}_seed{args.seed}"',
    'out_name = f"dqn_t{args.train_seed}_seed{args.seed}" if args.scheduler == "dqn" else f"{args.scheduler}_seed{args.seed}"\n    out_dir = Path(args.out_dir) / out_name'
)

# 2. tools/run_eval_sweep.py
replace_in_file("tools/run_eval_sweep.py",
    '"--model-path", model_path,\n                "--seed", str(e_seed),',
    '"--model-path", model_path,\n                "--train-seed", str(t_seed),\n                "--seed", str(e_seed),'
)

# 3. config/system.yaml
replace_in_file("config/system.yaml",
    'train_seeds: [0, 1, 2, 3, 4]',
    'train_seeds: [0, 1, 2, 3, 4]\n  validation_seeds: [200, 201, 202, 203, 204]'
)

# 4. rl/callbacks.py
replace_in_file("rl/callbacks.py",
    'self._eval_seeds = sys_cfg["rl"]["eval_seeds"]',
    'self._eval_seeds = sys_cfg["rl"].get("validation_seeds", sys_cfg["rl"]["eval_seeds"])'
)

# 5. rl/train.py
replace_in_file("rl/train.py",
    'from common.provenance import write_run_meta',
    'from common.provenance import write_run_meta, get_config_hash'
)
replace_in_file("rl/train.py",
    'train_set = set(rl_cfg["train_seeds"])\n    eval_set = set(rl_cfg["eval_seeds"])\n    assert train_set.isdisjoint(eval_set), "train_seeds and eval_seeds overlap!"',
    'train_set = set(rl_cfg["train_seeds"])\n    eval_set = set(rl_cfg["eval_seeds"])\n    val_set = set(rl_cfg.get("validation_seeds", []))\n    assert train_set.isdisjoint(eval_set), "train_seeds and eval_seeds overlap!"\n    assert train_set.isdisjoint(val_set), "train_seeds and validation_seeds overlap!"\n    assert val_set.isdisjoint(eval_set), "validation_seeds and eval_seeds overlap!"'
)
replace_in_file("rl/train.py",
    'tensorboard_log="runs/",',
    'tensorboard_log=f"runs/cfg_{get_config_hash()}",'
)
replace_in_file("rl/train.py",
    'DivergenceMonitor(sys_cfg),',
    'DivergenceMonitor(sys_cfg, stop_on_divergence=True),'
)

# 6. rl/monitors.py
replace_in_file("rl/monitors.py",
    'obs_sample = np.random.default_rng(42).random((16, 16)).astype(np.float32)\n            obs_tensor = torch.tensor(obs_sample)',
    'obs_sample = self.locals.get("new_obs")\n            if obs_sample is None:\n                obs_sample = np.random.default_rng(42).random((16, 16)).astype(np.float32)\n            obs_tensor = torch.tensor(obs_sample)'
)

# 7. common/provenance.py
replace_in_file("common/provenance.py",
    'from datetime import datetime',
    'from datetime import datetime, timezone'
)
replace_in_file("common/provenance.py",
    '"timestamp_utc": datetime.utcnow().isoformat() + "Z",',
    '"timestamp_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),'
)

# 8. docs/RESULTS_SIM.md
replace_in_file("docs/RESULTS_SIM.md",
    '- Shuffled-label control confirmed non-significant (p >= 0.05).',
    '- Shuffled-label control: Pending (evaluations not yet run).'
)

# 9. docs/FITTING_REPORT.md
replace_in_file("docs/FITTING_REPORT.md",
    'This document serves as the formal record of how the simulation environment (NetworkSim) was mathematically calibrated using external datasets before commencing Deep Reinforcement Learning (DRL) training.',
    'This document outlines the parameter ranges consistent with literature and external datasets.\n**Note:** The current parameters in config/measured_params.yaml are placeholders pending the real P1 hardware campaign. No automated fit script has been run against raw data yet.'
)

# 10. README.md
if os.path.exists("README.md"):
    with open("README.md", 'r', encoding='utf-8') as f:
        c = f.read()
    if "> **Note:** All results presented here reflect simulation under assumed channel parameters" not in c:
        c = "> **Note:** All results presented here reflect simulation under assumed channel parameters, pending a real hardware campaign.\n\n" + c
        with open("README.md", 'w', encoding='utf-8') as f:
            f.write(c)
        print("Updated README.md")

print("All edits applied.")
