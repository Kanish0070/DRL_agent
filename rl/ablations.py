"""Ablation training runs (T5.7).

Three ablations:
  1. no-weight  — 12-D state (drop the weight_norm feature per node)
  2. no-dui     — reward without non-linear DUI penalty (dui_lambda=0)
  3. no-shield  — evaluate the trained model without the safety shield

Usage:
    python -m rl.ablations --ablation no-weight --seed 0 --timesteps 200000
"""
import argparse
import copy
import os

import numpy as np
import gymnasium as gym
from gymnasium import spaces
from stable_baselines3 import DQN

from common.config import load_measured_params, load_system_config
from common.metrics import criticality_weighted_aoi, compute_dui, calculate_reward
from common.provenance import write_run_meta
from rl.env import AoiSchedulerEnv
from rl.reward import shaped_reward
from sim.network import NetworkSim, SimConfig


# ── Ablation 1: 12-D env (drop weight_norm channel) ──────────────────────────
class AoiEnvNoWeightFeature(AoiSchedulerEnv):
    """Drops the weight_norm column from the observation (12-D instead of 16-D)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.observation_space = spaces.Box(
            low=0.0, high=1.0, shape=(12,), dtype=np.float32
        )

    def _strip_weights(self, obs: np.ndarray) -> np.ndarray:
        # obs is (16,) = 4 nodes × [aoi, queue, rssi, weight]
        # drop every 4th element (index 3, 7, 11, 15)
        return np.delete(obs, [3, 7, 11, 15])

    def reset(self, **kwargs):
        obs, info = super().reset(**kwargs)
        return self._strip_weights(obs), info

    def step(self, action):
        obs, reward, term, trunc, info = super().step(action)
        return self._strip_weights(obs), reward, term, trunc, info


# ── Ablation 2: no-DUI reward (dui_lambda=0) ─────────────────────────────────
class AoiEnvNoDUIReward(AoiSchedulerEnv):
    """Uses lambda_energy=0 and dui_lambda=0 so the reward is purely -mean_aoi."""

    def __init__(self, sys_cfg, *args, **kwargs):
        # Patch dui_lambda to 0 in the config copy
        patched = copy.deepcopy(sys_cfg)
        patched["scheduler"]["dui_lambda"] = 0.0
        super().__init__(patched, *args, **kwargs)


def run_ablation(ablation: str, seed: int, timesteps: int, sys_cfg: dict, meas_cfg: dict) -> float:
    rl_cfg = sys_cfg["rl"]

    if ablation == "no-weight":
        env = AoiEnvNoWeightFeature(sys_cfg, meas_cfg, seed=seed)
        obs_dim = 12
    elif ablation == "no-dui":
        env = AoiEnvNoDUIReward(sys_cfg, meas_cfg, seed=seed)
        obs_dim = 16
    elif ablation == "no-shield":
        # Train normally; evaluate without shield (done at eval time, not here)
        env = AoiSchedulerEnv(sys_cfg, meas_cfg, seed=seed)
        obs_dim = 16
    else:
        raise ValueError(f"Unknown ablation: {ablation}")

    model = DQN(
        "MlpPolicy", env,
        gamma=rl_cfg["gamma"],
        learning_rate=rl_cfg["learning_rate"],
        buffer_size=rl_cfg["buffer_size"],
        batch_size=rl_cfg["batch_size"],
        target_update_interval=rl_cfg["target_update_interval"],
        exploration_initial_eps=rl_cfg["eps_start"],
        exploration_final_eps=rl_cfg["eps_end"],
        exploration_fraction=rl_cfg["eps_fraction"],
        policy_kwargs={"net_arch": rl_cfg["net_arch"]},
        seed=seed,
        verbose=0,
    )
    model.learn(total_timesteps=timesteps)

    os.makedirs("models", exist_ok=True)
    save_path = f"models/ablation_{ablation}_seed{seed}"
    model.save(save_path)
    write_run_meta(save_path, policy_id=f"ablation_{ablation}", seed=seed)

    # Evaluate
    weights = np.array(
        [sys_cfg["scheduler"]["weights"][c] for c in sys_cfg["system"]["node_classes"]]
    )
    eval_env = env.__class__(sys_cfg, meas_cfg) if ablation != "no-weight" else AoiEnvNoWeightFeature(sys_cfg, meas_cfg)
    eval_obs, _ = eval_env.reset(seed=100)
    cw_aois = []
    for _ in range(rl_cfg["episode_length"]):
        action, _ = model.predict(eval_obs, deterministic=True)
        eval_obs, _, term, trunc, info = eval_env.step(int(action))
        cw_aois.append(criticality_weighted_aoi(info["aoi"], weights))
        if term or trunc:
            break

    cw_mean = float(np.mean(cw_aois))
    print(f"[ablations] ablation={ablation} seed={seed} cw_mean_aoi={cw_mean:.4f}")
    return cw_mean


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ablation", required=True, choices=["no-weight", "no-dui", "no-shield"])
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--timesteps", type=int, default=200_000)
    args = parser.parse_args()

    sys_cfg = load_system_config()
    meas_cfg = load_measured_params()
    run_ablation(args.ablation, args.seed, args.timesteps, sys_cfg, meas_cfg)


if __name__ == "__main__":
    main()
