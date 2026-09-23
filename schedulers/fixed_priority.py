import numpy as np
from schedulers.base import BaseScheduler

class FixedPriorityScheduler(BaseScheduler):
    def __init__(self, node_classes: list[str]):
        priority_map = {"urgent": 2, "important": 1, "routine": 0}
        self.priorities = np.array([priority_map[c.lower()] for c in node_classes])

    def select(self, aoi: np.ndarray, rssi: np.ndarray, queue: np.ndarray, weights: np.ndarray) -> int:
        best = 0
        for i in range(1, len(aoi)):
            if self.priorities[i] > self.priorities[best] or \
               (self.priorities[i] == self.priorities[best] and aoi[i] > aoi[best]):
                best = i
        return int(best)
