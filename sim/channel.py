"""Per-node wireless channel model (T2.1, audit findings F2.4/F2.5).

Three layers, each addressing a specific audit finding:
  1. Log-distance path loss -> a baseline RSSI per node from its distance.
  2. Gauss-Markov shadowing (F2.4) -- i.i.d. per-slot shadowing would let
     the agent "see" a channel state hardware never actually presents;
     real shadowing is temporally correlated, so RSSI is generated as an
     AR(1) process instead of independent draws.
  3. A logistic delivery-success model layered with a Gilbert-Elliott
     2-state Markov chain (D1.2) for bursty loss on top of the smooth
     RSSI-vs-PDR curve.

All parameters come from config/measured_params.yaml (currently
PLACEHOLDER values pending the P1 hardware campaign -- see that file's
header). No function here touches the global `np.random` state; every
stochastic step takes an explicit `np.random.Generator` (F2.10).
"""

from dataclasses import dataclass

import numpy as np

GOOD, BAD = 0, 1


@dataclass
class ChannelParams:
    path_loss_exponent: float
    reference_distance_m: float
    reference_loss_db: float
    shadowing_sigma_db: float
    shadowing_correlation_rho: float
    logistic_r50_dbm: float
    logistic_slope_db: float
    ge_prob_good_to_bad: float
    ge_prob_bad_to_good: float
    ge_bad_state_success_multiplier: float

    # Nominal AP transmit power used only to place RSSI in a realistic
    # dBm range; it cancels out of every relative comparison the project
    # makes (PDR-vs-RSSI, weighted-AoI, ...), so an assumed constant here
    # does not bias any result.
    tx_power_dbm: float = 20.0

    @classmethod
    def from_measured_params(cls, measured_params: dict) -> "ChannelParams":
        c = measured_params["channel"]
        return cls(
            path_loss_exponent=c["path_loss_exponent"],
            reference_distance_m=c["reference_distance_m"],
            reference_loss_db=c["reference_loss_db"],
            shadowing_sigma_db=c["shadowing_sigma_db"],
            shadowing_correlation_rho=c["shadowing_correlation_rho"],
            logistic_r50_dbm=c["logistic_r50_dbm"],
            logistic_slope_db=c["logistic_slope_db"],
            ge_prob_good_to_bad=c["ge_prob_good_to_bad"],
            ge_prob_bad_to_good=c["ge_prob_bad_to_good"],
            ge_bad_state_success_multiplier=c["ge_bad_state_success_multiplier"],
        )


def path_loss_db(distance_m: np.ndarray, params: ChannelParams) -> np.ndarray:
    """Log-distance path loss: PL(d) = PL(d0) + 10*n*log10(d/d0)."""
    return params.reference_loss_db + 10.0 * params.path_loss_exponent * np.log10(
        distance_m / params.reference_distance_m
    )


def success_probability_from_rssi(rssi_dbm: np.ndarray, params: ChannelParams) -> np.ndarray:
    """Logistic delivery-success curve, independent of burst state."""
    return 1.0 / (1.0 + np.exp(-(rssi_dbm - params.logistic_r50_dbm) / params.logistic_slope_db))


class ChannelModel:
    """Stateful per-node channel: correlated shadowing + a Gilbert-Elliott
    burst overlay. One instance covers all nodes; call `step(rng)` once
    per simulated slot before reading `rssi()` / `success_probability()`.
    """

    def __init__(self, distances_m: np.ndarray, params: ChannelParams):
        self.distances_m = np.asarray(distances_m, dtype=np.float64)
        self.params = params
        self.n_nodes = len(self.distances_m)
        self._base_loss_db = path_loss_db(self.distances_m, params)
        self.shadow_db = np.zeros(self.n_nodes)
        self.ge_state = np.full(self.n_nodes, GOOD, dtype=np.int8)

    def step(self, rng: np.random.Generator) -> None:
        """Advances the shadowing AR(1) process and the GE chain by one slot."""
        rho = self.params.shadowing_correlation_rho
        noise = rng.normal(loc=0.0, scale=self.params.shadowing_sigma_db, size=self.n_nodes)
        self.shadow_db = rho * self.shadow_db + np.sqrt(max(1.0 - rho**2, 0.0)) * noise

        draws = rng.random(self.n_nodes)
        for i in range(self.n_nodes):
            if self.ge_state[i] == GOOD:
                if draws[i] < self.params.ge_prob_good_to_bad:
                    self.ge_state[i] = BAD
            else:
                if draws[i] < self.params.ge_prob_bad_to_good:
                    self.ge_state[i] = GOOD

    def rssi(self, node_idx: int) -> float:
        return self.params.tx_power_dbm - self._base_loss_db[node_idx] + self.shadow_db[node_idx]

    def rssi_all(self) -> np.ndarray:
        return self.params.tx_power_dbm - self._base_loss_db + self.shadow_db

    def success_probability(self, node_idx: int) -> float:
        p = success_probability_from_rssi(self.rssi(node_idx), self.params)
        if self.ge_state[node_idx] == BAD:
            p *= self.params.ge_bad_state_success_multiplier
        return float(p)

    def draw_success(self, node_idx: int, rng: np.random.Generator) -> bool:
        return bool(rng.random() < self.success_probability(node_idx))
