"""Hyperparameter sweep (T5.4).

Runs a small grid search over learning_rate × net_arch and reports
criticality-weighted mean AoI for each combination using a single eval seed.
Results are printed and saved to sweep_results.csv.

Usage:
    python -m rl.sweep
"""
import csv
import itertools

import numpy as np
from stable_baselines3 import DQN

from common.config import load_measured_params, load_system_config
from common.metrics import criticality_weighted_aoi
from rl.env import AoiSchedulerEnv


SWEEP_GRID = {
    "learning_rate": [1e-3, 5e-4, 1e-4],
    "net_arch": [[64, 64], [128, 64], [64, 64, 64]],
}

SWEEP_TIMESTEPS = 50_000   # short run per config; final runs use full 500k
SWEEP_SEED = 0
EVAL_SEED = 100


def eval_policy(model, sys_cfg, meas_cfg) -> float:
    weights = np.array(
        [sys_cfg["scheduler"]["weights"][c] for c in sys_cfg["system"]["node_classes"]]
    )
    env = AoiSchedulerEnv(sys_cfg, meas_cfg)
    obs, _ = env.reset(seed=EVAL_SEED)
    ep_aois = []
    for _ in range(sys_cfg["rl"]["episode_length"]):
        action, _ = model.predict(obs, deterministic=True)
        obs, _, term, trunc, info = env.step(int(action))
        ep_aois.append(criticality_weighted_aoi(info["aoi"], weights))
        if term or trunc:
            break
    return float(np.mean(ep_aois))


def main():
    sys_cfg = load_system_config()
    meas_cfg = load_measured_params()
    rl_cfg = sys_cfg["rl"]

    keys = list(SWEEP_GRID.keys())
    combos = list(itertools.product(*SWEEP_GRID.values()))

    results = []
    for combo in combos:
        params = dict(zip(keys, combo))
        print(f"  Sweeping {params} ...")
        env = AoiSchedulerEnv(sys_cfg, meas_cfg, seed=SWEEP_SEED)
        model = DQN(
            "MlpPolicy", env,
            gamma=rl_cfg["gamma"],
            learning_rate=params["learning_rate"],
            buffer_size=rl_cfg["buffer_size"],
            batch_size=rl_cfg["batch_size"],
            target_update_interval=rl_cfg["target_update_interval"],
            exploration_initial_eps=rl_cfg["eps_start"],
            exploration_final_eps=rl_cfg["eps_end"],
            exploration_fraction=rl_cfg["eps_fraction"],
            policy_kwargs={"net_arch": params["net_arch"]},
            seed=SWEEP_SEED,
            verbose=0,
        )
        model.learn(total_timesteps=SWEEP_TIMESTEPS)
        cw_aoi = eval_policy(model, sys_cfg, meas_cfg)
        row = {**params, "net_arch": str(params["net_arch"]), "cw_mean_aoi": cw_aoi}
        results.append(row)
        print(f"    -> cw_mean_aoi = {cw_aoi:.4f}")

    # Save results
    with open("sweep_results.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=results[0].keys())
        writer.writeheader()
        writer.writerows(results)

    best = min(results, key=lambda r: r["cw_mean_aoi"])
    print(f"\nBest config: {best}")
    print("Results saved to sweep_results.csv")


if __name__ == "__main__":
    main()
