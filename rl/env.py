import gymnasium as gym
import numpy as np
from gymnasium import spaces

from rl.shield import apply_safety_shield
from rl.reward import shaped_reward
from sim.network import NetworkSim, SimConfig

class AoiSchedulerEnv(gym.Env):
    """Gymnasium wrapper around sim.network.NetworkSim. Action = which node
    to grant this slot (the shield may override it); Observation = the
    frozen 16-D state vector NetworkSim already builds internally."""

    def __init__(self, system_config: dict, measured_params: dict, seed: int = None):
        n_nodes = system_config["system"]["n_nodes"]
        self.action_space = spaces.Discrete(n_nodes)
        self.observation_space = spaces.Box(low=0.0, high=1.0, shape=(16,), dtype=np.float32)

        self._sim_config = SimConfig.from_configs(
            system_config, measured_params, episode_length=system_config["rl"]["episode_length"])
        self._sim = NetworkSim(self._sim_config)
        self._shield_ceilings_s = np.array(
            [system_config["scheduler"]["shield_ceilings_s"][c]
             for c in system_config["system"]["node_classes"]])
        self._config = system_config
        self._seed = seed

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        eff_seed = seed if seed is not None else (self._seed if self._seed is not None else int(np.random.SeedSequence().entropy))
        obs = self._sim.reset(eff_seed)
        return obs.astype(np.float32), {}

    def step(self, action):
        shielded_action, shield_fired = apply_safety_shield(
            action, self._sim.metrics.aoi, self._sim.weights, self._shield_ceilings_s)
        obs, info = self._sim.step(shielded_action)
        reward = shaped_reward(info, self._sim.weights, self._sim.thresholds_s, self._config)
        info["shield_fired"] = shield_fired
        info["action_before_shield"] = action
        return obs.astype(np.float32), reward, False, info.pop("truncated"), info
