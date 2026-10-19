import os
import itertools
import subprocess
import yaml
from concurrent.futures import ProcessPoolExecutor, as_completed

def load_sys():
    with open("config/system.yaml", "r") as f:
        return yaml.safe_load(f)

def run_cmd(cmd):
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        return (False, " ".join(cmd), result.stderr.decode('utf-8'))
    return (True, " ".join(cmd), None)

def main():
    cfg = load_sys()
    eval_seeds = cfg["rl"]["eval_seeds"]
    train_seeds = cfg["rl"]["train_seeds"]
    schedulers = ["maxweight", "cag", "rr", "fpq", "random", "oracle"]
    
    r50s = [-90.0, -82.0, -75.0]
    slopes = [2.0, 4.0, 8.0]
    dists = [[5.0, 8.0, 12.0, 18.0], [30.0, 36.0, 42.0, 50.0]]
    bursts = [0.02, 0.04]
    arrivals = [1.0, 0.5, 0.2]

    grid = list(itertools.product(r50s, slopes, dists, bursts, arrivals))
    os.makedirs("sensitivity_results", exist_ok=True)
    
    commands = []
    
    py_exec = r"D:\dev_env\Final_year\DRL_agent\.venv\Scripts\python.exe"
    
    for idx, (r50, slope, dist, burst, arr) in enumerate(grid):
        cell_id = f"cell_{idx:03d}"
        out_dir = f"sensitivity_results/{cell_id}"
        
        dist_args = [str(d) for d in dist]
        base_args = ["--r50", str(r50), "--slope", str(slope), "--burst", str(burst), "--arrival", str(arr), "--distances"] + dist_args + ["--out-dir", out_dir]
        
        for seed in eval_seeds:
            for sched in schedulers:
                expected_file = f"{out_dir}/{sched}_seed{seed}/log.csv"
                if not os.path.exists(expected_file):
                    cmd = [py_exec, "-m", "eval.run", "--scheduler", sched, "--seed", str(seed)] + base_args
                    commands.append(cmd)
                
            for t_seed in train_seeds:
                model_path = f"models/dqn_seed{t_seed}.zip"
                expected_file = f"{out_dir}/dqn_t{t_seed}_seed{seed}/log.csv"
                if os.path.exists(model_path) and not os.path.exists(expected_file):
                    cmd = [py_exec, "-m", "eval.run", "--scheduler", "dqn", "--model-path", model_path, "--train-seed", str(t_seed), "--seed", str(seed)] + base_args
                    commands.append(cmd)
                    
    import json
    grid_meta = {f"cell_{idx:03d}": {"r50": r50, "slope": slope, "distances": dist, "burst": burst, "arrival": arr} for idx, (r50, slope, dist, burst, arr) in enumerate(grid)}
    with open("sensitivity_results/grid_meta.json", "w") as f:
        json.dump(grid_meta, f, indent=2)

    print(f"Total remaining commands to execute: {len(commands)}")
    if len(commands) == 0:
        print("Sweep complete!")
        return
        
    max_workers = 6
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(run_cmd, cmd) for cmd in commands]
        completed = 0
        for f in as_completed(futures):
            completed += 1
            if completed % 500 == 0:
                print(f"Progress: {completed} / {len(commands)}")
            success, cmd_str, stderr = f.result()
            if not success:
                print(f"Failed cmd: {cmd_str}\nError: {stderr}")

    print("Sweep complete!")

if __name__ == "__main__":
    main()
