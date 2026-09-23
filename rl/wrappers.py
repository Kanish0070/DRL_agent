from rl.obs import decode_observation

class SchedulerPolicyWrapper:
    """Adapts a schedulers.base.BaseScheduler to look like an SB3-style policy
    (.predict(obs) -> (action, state)) so eval/run.py and P6's sweeps can drive
    baselines and the trained DQN through identical code paths."""
    def __init__(self, scheduler):
        self._scheduler = scheduler

    def predict(self, obs, deterministic=True):
        aoi, rssi, queue, weights = decode_observation(obs)
        return self._scheduler.select(aoi, rssi, queue, weights), None
