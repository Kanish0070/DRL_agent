import numpy as np
import gymnasium
from gymnasium.utils.env_checker import check_env
from common.config import load_system_config, load_measured_params
from rl.env import AoiSchedulerEnv
from rl.shield import apply_safety_shield
from rl.wrappers import SchedulerPolicyWrapper
from rl.obs import decode_observation
from schedulers.round_robin import RoundRobinScheduler

def test_shield_activation():
    # Simple check that the shield overrides when there is a violation
    weights = np.array([1.0, 1.0, 1.0, 1.0])
    ceilings = np.array([2.0, 6.0, 20.0, 20.0])
    aoi = np.array([1.0, 7.0, 10.0, 10.0]) # node 1 violates
    action, fired = apply_safety_shield(0, aoi, weights, ceilings)
    assert fired is True
    assert action == 1

def test_env_checker():
    # Load default configs
    sys_cfg = load_system_config()
    meas_cfg = load_measured_params()
    env = AoiSchedulerEnv(sys_cfg, meas_cfg)
    # env_checker asserts all sorts of gymnasium contract guarantees
    check_env(env)

def test_no_oracle_leakage():
    # Assert rl/env.py does not import true_success_probabilities
    with open("rl/env.py", "r") as f:
        content = f.read()
    assert "true_success_probabilities" not in content
    
def test_decode_observation():
    sys_cfg = load_system_config()
    meas_cfg = load_measured_params()
    env = AoiSchedulerEnv(sys_cfg, meas_cfg)
    obs, _ = env.reset(seed=42)
    aoi, rssi, queue, weights = decode_observation(obs)
    
    assert aoi.shape == (4,)
    assert rssi.shape == (4,)
    assert queue.shape == (4,)
    assert weights.shape == (4,)

def test_wrapper_parity():
    # ensure wrappers don't throw errors
    rr = RoundRobinScheduler()
    wrapper = SchedulerPolicyWrapper(rr)
    sys_cfg = load_system_config()
    meas_cfg = load_measured_params()
    env = AoiSchedulerEnv(sys_cfg, meas_cfg)
    obs, _ = env.reset(seed=42)
    action, state = wrapper.predict(obs)
    assert action == 0
    assert state is None
