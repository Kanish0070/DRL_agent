import numpy as np
from schedulers.base import BaseScheduler
from sim.channel import success_probability_from_rssi, ChannelParams

class ChannelAwareGreedyScheduler(BaseScheduler):
    def __init__(self, measured_params: dict):
        self.channel_params = ChannelParams.from_measured_params(measured_params)

    def select(self, aoi: np.ndarray, rssi: np.ndarray, queue: np.ndarray, weights: np.ndarray) -> int:
        best = 0
        best_metric = -1.0
        
        for i in range(len(aoi)):
            p_s = success_probability_from_rssi(rssi[i], self.channel_params)
            metric = weights[i] * aoi[i] * p_s
            if metric > best_metric:
                best_metric = metric
                best = i
                
        return int(best)
