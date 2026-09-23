from abc import ABC, abstractmethod
import numpy as np

class BaseScheduler(ABC):
    """A scheduler observes per-node AoI/RSSI/queue-occupancy/criticality-weight
    and returns the node index to grant this slot."""

    @abstractmethod
    def select(self, aoi: np.ndarray, rssi: np.ndarray, queue: np.ndarray,
               weights: np.ndarray) -> int:
        ...
