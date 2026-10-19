import os
import subprocess
import yaml

def load_sys():
    with open("config/system.yaml", "r") as f:
        return yaml.safe_load(f)

def main():
    cfg = load_sys()
    eval_seeds = cfg["rl"]["eval_seeds"]
    schedulers = ["rr", "fpq", "maxweight", "cag", "random", "oracle"]
    
    os.makedirs("results", exist_ok=True)

    # 1. Run baselines
    for sched in schedulers:
        print(f"--- Running baseline: {sched} ---")
        for seed in eval_seeds:
            cmd = ["python", "-m", "eval.run", "--scheduler", sched, "--seed", str(seed), "--out-dir", "results"]
            subprocess.run(cmd, check=True)

    # 2. Run DQN models (evaluate all 5 trained models)
    train_seeds = cfg["rl"]["train_seeds"]
    for t_seed in train_seeds:
        model_path = f"models/dqn_seed{t_seed}.zip"
        if not os.path.exists(model_path):
            print(f"Skipping {model_path} - not found.")
            continue
        print(f"--- Running DQN model from train seed {t_seed} ---")
        for e_seed in eval_seeds:
            cmd = [
                "python", "-m", "eval.run", 
                "--scheduler", "dqn", 
                "--model-path", model_path,
                "--train-seed", str(t_seed),
                "--seed", str(e_seed), 
                "--out-dir", "results"
            ]
            subprocess.run(cmd, check=True)
            
    print("All evaluation sweeps completed successfully!")

if __name__ == "__main__":
    main()
