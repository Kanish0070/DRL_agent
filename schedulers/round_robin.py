import numpy as np
from schedulers.base import BaseScheduler

class RoundRobinScheduler(BaseScheduler):
    def __init__(self):
        self._slot = 0

    def select(self, aoi: np.ndarray, rssi: np.ndarray, queue: np.ndarray, weights: np.ndarray) -> int:
        n_nodes = len(aoi)
        action = self._slot % n_nodes
        self._slot += 1
        return action
