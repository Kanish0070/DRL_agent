"""Export trained SB3 DQN models to compact PyTorch (.pt) and NumPy (.npz) formats."""
import argparse
import os
from pathlib import Path
import torch
from stable_baselines3 import DQN
from deploy.export import export_model

def export_all(models_dir: str = "models", out_dir: str = "deploy/artifacts"):
    os.makedirs(out_dir, exist_ok=True)
    seeds = [0, 1, 2, 3, 4]
    
    for seed in seeds:
        zip_path = Path(models_dir) / f"dqn_seed{seed}.zip"
        if not zip_path.exists():
            print(f"[skip] {zip_path} not found")
            continue
            
        print(f"[export] Loading {zip_path}...")
        model = DQN.load(str(zip_path), device="cpu")
        q_net = model.policy.q_net
        q_net.eval()
        
        # 1. TorchScript Traced Module (.pt) - standalone, callable in Python & C++ without SB3
        dummy_obs = torch.zeros((1, 16), dtype=torch.float32)
        traced = torch.jit.trace(q_net, dummy_obs)
        pt_path = Path(out_dir) / f"dqn_seed{seed}.pt"
        traced.save(str(pt_path))
        
        # 2. PyTorch State Dict (.pt)
        sd_path = Path(out_dir) / f"dqn_seed{seed}_state_dict.pt"
        torch.save(q_net.state_dict(), str(sd_path))
        
        # 3. NumPy format (.npz) for parity gate and C++ raw array export
        npz_path = Path(out_dir) / f"dqn_seed{seed}"
        export_model(model, str(npz_path))
        
        pt_size = pt_path.stat().st_size / 1024
        sd_size = sd_path.stat().st_size / 1024
        print(f"[exported] seed {seed} -> {pt_path.name} ({pt_size:.1f} KB), {sd_path.name} ({sd_size:.1f} KB), {npz_path.name}.npz")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export DQN models to PyTorch .pt and NumPy formats.")
    parser.add_argument("--models-dir", default="models", help="Directory containing SB3 model zips")
    parser.add_argument("--out-dir", default="deploy/artifacts", help="Target output directory")
    args = parser.parse_args()
    export_all(args.models_dir, args.out_dir)
