import numpy as np
from schedulers.base import BaseScheduler

class MaxWeightScheduler(BaseScheduler):
    def select(self, aoi: np.ndarray, rssi: np.ndarray, queue: np.ndarray, weights: np.ndarray) -> int:
        best = 0
        for i in range(1, len(aoi)):
            if weights[i] * aoi[i] > weights[best] * aoi[best]:
                best = i
        return int(best)
