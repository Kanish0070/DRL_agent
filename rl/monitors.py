"""Divergence monitor callback (T5.2).

Watches training loss and mean Q-value each target_update_interval steps.
Emits a warning (and optionally stops training) on NaN/Inf loss or Q-value
blowup beyond a derived bound from the DUI formula's maximum plausible value.
"""
import math
import warnings

import numpy as np
from stable_baselines3.common.callbacks import BaseCallback


def _max_plausible_q(sys_cfg: dict) -> float:
    """Derive a sanity-check upper bound on |Q| from config.

    The reward is based on DUI ∈ [0, 1], so a cumulative discounted reward
    over an infinite horizon is bounded by R_max / (1 - γ). We use the
    maximum possible reward magnitude (1.0) and the configured discount.
    """
    gamma = sys_cfg["rl"]["gamma"]
    # reward is in [-1, 1] roughly, so Q_max ≈ 1 / (1 - γ)
    return 1.0 / max(1e-6, 1.0 - gamma)


class DivergenceMonitor(BaseCallback):
    """Warns and optionally stops training on Q-value / loss divergence."""

    def __init__(self, sys_cfg: dict, stop_on_divergence: bool = False, verbose: int = 0):
        super().__init__(verbose)
        self._q_bound = _max_plausible_q(sys_cfg) * 10  # 10× safety margin
        self._stop = stop_on_divergence
        self._check_interval = sys_cfg["rl"]["target_update_interval"]

    def _on_step(self) -> bool:
        if self.n_calls % self._check_interval != 0:
            return True

        # Check loss from logger
        loss = self.logger.name_to_value.get("train/loss")
        if loss is not None:
            if math.isnan(loss) or math.isinf(loss):
                warnings.warn(f"[DivergenceMonitor] NaN/Inf training loss at step {self.num_timesteps}!")
                return not self._stop

        # Check Q-values from the policy's predict on a random batch of observations
        try:
            import torch
            obs_sample = np.random.default_rng(42).random((16, 16)).astype(np.float32)
            obs_tensor = torch.tensor(obs_sample)
            with torch.no_grad():
                q_vals = self.model.q_net(obs_tensor).numpy()
            max_q = np.abs(q_vals).max()
            if max_q > self._q_bound:
                warnings.warn(
                    f"[DivergenceMonitor] Q-value magnitude {max_q:.1f} exceeds bound "
                    f"{self._q_bound:.1f} at step {self.num_timesteps}!"
                )
                return not self._stop
        except Exception:
            pass  # Don't crash training if monitor errors

        return True
