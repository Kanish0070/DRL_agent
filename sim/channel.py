"""Channel model: logistic delivery-probability vs RSSI (D1.2) and per-node
RSSI sampling, calibrated from config/measured_params.yaml (see
docs/PARAM_PROVENANCE.md for where those numbers currently come from).
"""

import numpy as np


def delivery_probability(rssi_dbm: np.ndarray | float, r50_dbm: float, beta_db: float):
    """Logistic p_s(RSSI): probability 0.5 at rssi_dbm == r50_dbm (D1.2)."""
    return 1.0 / (1.0 + np.exp(-(rssi_dbm - r50_dbm) / beta_db))


class ChannelModel:
    """
    Per-node RSSI sampling (mean + Gaussian shadow-fading jitter) and
    Bernoulli delivery outcomes drawn from the logistic p_s(RSSI) curve.

    Deterministic per seed: takes an explicit np.random.Generator and never
    touches global numpy RNG state (P2 acceptance criteria).
    """

    def __init__(self, node_mean_rssi_dbm, r50_dbm: float, beta_db: float,
                 fading_std_db: float, rng: np.random.Generator):
        self.node_mean_rssi_dbm = np.asarray(node_mean_rssi_dbm, dtype=np.float64)
        self.r50_dbm = r50_dbm
        self.beta_db = beta_db
        self.fading_std_db = fading_std_db
        self.rng = rng
        self.current_rssi = self.node_mean_rssi_dbm.copy()

    @classmethod
    def from_measured_params(cls, params: dict, rng: np.random.Generator) -> "ChannelModel":
        ch = params["channel"]
        return cls(
            node_mean_rssi_dbm=ch["node_mean_rssi_dbm"],
            r50_dbm=ch["r50_dbm"],
            beta_db=ch["beta_db"],
            fading_std_db=ch["fading_std_db"],
            rng=rng,
        )

    def sample_rssi(self) -> np.ndarray:
        """Draws this slot's RSSI per node (mean + shadow-fading jitter)."""
        jitter = self.rng.normal(0.0, self.fading_std_db, size=self.node_mean_rssi_dbm.shape)
        self.current_rssi = self.node_mean_rssi_dbm + jitter
        return self.current_rssi

    def try_deliver(self, node_id: int) -> bool:
        """Bernoulli delivery outcome for node_id using the last sampled RSSI."""
        ps = delivery_probability(self.current_rssi[node_id], self.r50_dbm, self.beta_db)
        return bool(self.rng.random() < ps)
