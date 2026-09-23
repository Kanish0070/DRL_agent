import numpy as np
from schedulers.base import BaseScheduler

class RandomScheduler(BaseScheduler):
    def __init__(self, seed: int = None):
        self.rng = np.random.Generator(np.random.PCG64(seed))

    def select(self, aoi: np.ndarray, rssi: np.ndarray, queue: np.ndarray, weights: np.ndarray) -> int:
        n_nodes = len(aoi)
        return int(self.rng.integers(0, n_nodes))
