import numpy as np

class OracleScheduler:
    """Evaluation-only baseline that knows the true instantaneous channel state.
    Not deployable; measures the performance penalty of RSSI staleness.
    Does not match BaseScheduler's select() signature."""
    
    def select_with_oracle(self, aoi: np.ndarray, queue: np.ndarray, weights: np.ndarray, true_success_probs: np.ndarray) -> int:
        best = -1
        best_metric = -1.0
        
        # Try finding the best among those with buffered data
        for i in range(len(aoi)):
            if queue[i]:
                metric = weights[i] * aoi[i] * true_success_probs[i]
                if metric > best_metric:
                    best_metric = metric
                    best = i
                    
        # Fallback if no node has data buffered
        if best == -1:
            best_metric = -1.0
            for i in range(len(aoi)):
                metric = weights[i] * aoi[i]
                if metric > best_metric:
                    best_metric = metric
                    best = i
                    
        return int(best)
