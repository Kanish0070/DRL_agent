"""Per-slot AoI and energy accounting (T2.3).

This module owns no AoI math of its own -- it is a thin bookkeeping layer
around common/contracts/aoi.py::update_aoi_for_slot, the single
authoritative implementation (F2.9). Its only job is to apply that rule
to all four nodes each slot and track the energy/wasted-slot side effects
the AoI contract doesn't cover.
"""

import numpy as np

from common.contracts.aoi import update_aoi_for_slot


class MetricsTracker:
    def __init__(self, n_nodes: int, tx_power_proxy: float = 1.0):
        self.n_nodes = n_nodes
        self.tx_power_proxy = tx_power_proxy

        self.aoi = np.zeros(n_nodes)
        self.total_energy = 0.0
        self.wasted_slots = 0  # grants that produced no delivery
        self.delivered_count = np.zeros(n_nodes, dtype=int)

    def step(self, granted_node: int, packet_arrived: bool, delivered_age: float, t_slot: float) -> None:
        """Applies one slot's outcome. `packet_arrived`/`delivered_age`
        describe only the granted node -- every other node simply ages by
        `t_slot`, exactly as update_aoi_for_slot defines.
        """
        for i in range(self.n_nodes):
            arrived_here = packet_arrived and i == granted_node
            self.aoi[i] = update_aoi_for_slot(
                current_aoi=self.aoi[i],
                packet_arrived=arrived_here,
                delivered_age=delivered_age if arrived_here else 0.0,
                t_slot=t_slot,
            )

        # D1.3: WifiPsMode is NONE, so a grant is issued -- and its
        # airtime spent -- every slot regardless of outcome (F2.8: a
        # wasted grant still costs energy; it just resets no AoI).
        self.total_energy += self.tx_power_proxy * t_slot

        if packet_arrived:
            self.delivered_count[granted_node] += 1
        else:
            self.wasted_slots += 1
