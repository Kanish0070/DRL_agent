"""Periodic evaluation callback (T5.3).

Every `eval_freq` training steps, evaluates the current policy across all
eval_seeds (disjoint from train_seeds) and logs criticality-weighted mean AoI
to TensorBoard.
"""
import numpy as np
from stable_baselines3.common.callbacks import BaseCallback

from common.metrics import criticality_weighted_aoi
from rl.env import AoiSchedulerEnv


class PeriodicEvalCallback(BaseCallback):
    """Runs eval_seeds episodes and logs criticality-weighted mean AoI."""

    def __init__(self, sys_cfg: dict, meas_cfg: dict, eval_freq: int = 10_000, verbose: int = 0):
        super().__init__(verbose)
        self._sys_cfg = sys_cfg
        self._meas_cfg = meas_cfg
        self._eval_seeds = sys_cfg["rl"]["eval_seeds"]
        self._eval_freq = eval_freq
        self._weights = np.array(
            [sys_cfg["scheduler"]["weights"][c] for c in sys_cfg["system"]["node_classes"]]
        )

    def _on_step(self) -> bool:
        if self.n_calls % self._eval_freq != 0:
            return True

        all_aoi = []
        for seed in self._eval_seeds[:5]:  # use first 5 for speed during training
            env = AoiSchedulerEnv(self._sys_cfg, self._meas_cfg)
            obs, _ = env.reset(seed=seed)
            ep_len = self._sys_cfg["rl"]["episode_length"]
            slot_aois = []
            for _ in range(ep_len):
                action, _ = self.model.predict(obs, deterministic=True)
                obs, _, terminated, truncated, info = env.step(int(action))
                slot_aois.append(criticality_weighted_aoi(info["aoi"], self._weights))
                if terminated or truncated:
                    break
            all_aoi.append(float(np.mean(slot_aois)))

        mean_cw_aoi = float(np.mean(all_aoi))
        self.logger.record("eval/criticality_weighted_mean_aoi", mean_cw_aoi)
        if self.verbose:
            print(f"  [EvalCallback] step={self.num_timesteps} cw_mean_aoi={mean_cw_aoi:.4f}")
        return True
