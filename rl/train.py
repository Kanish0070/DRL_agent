"""DQN training script (T5.1).

Usage:
    python -m rl.train --seed 0
    python -m rl.train --all-seeds        # runs all train_seeds from config
"""
import argparse
import os

from stable_baselines3 import DQN

from common.config import load_measured_params, load_system_config
from common.provenance import write_run_meta
from rl.callbacks import PeriodicEvalCallback
from rl.env import AoiSchedulerEnv
from rl.monitors import DivergenceMonitor


def train_one(seed: int, sys_cfg: dict, meas_cfg: dict) -> str:
    rl_cfg = sys_cfg["rl"]

    # Verify seed disjoint invariant at runtime (also asserted in tests).
    train_set = set(rl_cfg["train_seeds"])
    eval_set = set(rl_cfg["eval_seeds"])
    assert train_set.isdisjoint(eval_set), "train_seeds and eval_seeds overlap!"

    env = AoiSchedulerEnv(sys_cfg, meas_cfg, seed=seed)

    model = DQN(
        "MlpPolicy",
        env,
        gamma=rl_cfg["gamma"],
        learning_rate=rl_cfg["learning_rate"],
        buffer_size=rl_cfg["buffer_size"],
        batch_size=rl_cfg["batch_size"],
        target_update_interval=rl_cfg["target_update_interval"],
        exploration_initial_eps=rl_cfg["eps_start"],
        exploration_final_eps=rl_cfg["eps_end"],
        exploration_fraction=rl_cfg["eps_fraction"],
        policy_kwargs={"net_arch": rl_cfg["net_arch"]},
        tensorboard_log="runs/",
        seed=seed,
        verbose=0,
    )

    callbacks = [
        DivergenceMonitor(sys_cfg),
        PeriodicEvalCallback(sys_cfg, meas_cfg),
    ]

    model.learn(total_timesteps=rl_cfg["total_timesteps"], callback=callbacks)

    os.makedirs("models", exist_ok=True)
    model_path = f"models/dqn_seed{seed}"
    model.save(model_path)
    write_run_meta(f"models/dqn_seed{seed}", policy_id="dqn", seed=seed)
    print(f"[train] Saved model -> {model_path}.zip")
    return model_path


def main():
    parser = argparse.ArgumentParser(description="Train SB3 DQN on AoI scheduler environment.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--seed", type=int, help="Single training seed.")
    group.add_argument("--all-seeds", action="store_true", help="Run all train_seeds from config.")
    args = parser.parse_args()

    sys_cfg = load_system_config()
    meas_cfg = load_measured_params()

    if args.all_seeds:
        for seed in sys_cfg["rl"]["train_seeds"]:
            print(f"\n=== Training seed {seed} ===")
            train_one(seed, sys_cfg, meas_cfg)
    else:
        train_one(args.seed, sys_cfg, meas_cfg)


if __name__ == "__main__":
    main()
