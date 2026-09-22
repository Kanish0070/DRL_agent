"""Fast pure-Python/NumPy slot simulator (T2.4).

Mirrors the exact grant-reply protocol already validated in
ns3-sim/aoi-scheduler-sim.cc (same shield logic, same generation-time AoI
reset, same LCFS-1 queues) but without ns-3's PHY/MAC simulation overhead,
so it can sustain the >=1e4 slots/sec throughput RL training needs.

The caller supplies the granted-node decision each slot (any P3 baseline
scheduler or a P4 RL policy) -- this module owns only the physics/AoI/queue
state, never scheduling policy, so it has no circular dependency on either.
"""

from dataclasses import dataclass

import numpy as np

from common.contracts.aoi import update_aoi_for_slot
from common.metrics import compute_dui, calculate_reward
from sim.channel import ChannelModel
from sim.queue import LcfsAlarmQueue


@dataclass
class SlotResult:
    slot_id: int
    granted_node: int
    shield_fired: bool
    uplink_received: bool
    delivered_node: int | None
    delivered_age_s: float | None
    aoi: np.ndarray
    rssi: np.ndarray
    queue_status: np.ndarray
    energy_proxy_cost: float
    dui: np.ndarray


class NetworkSimulator:
    """
    Steps one fixed-duration slot at a time. Each step(action):
      1. samples this slot's RSSI (channel fading),
      2. applies the safety shield to the caller's proposed action, exactly
         as ns3-sim's SlotTick does,
      3. resolves delivery via the channel model,
      4. ages/resets AoI via the single frozen update rule
         (common.contracts.aoi.update_aoi_for_slot),
      5. advances every node's LCFS-1 queue to the new time,
      6. returns a SlotResult carrying the per-slot DUI for reward shaping.
    """

    def __init__(self, config: dict, measured_params: dict, seed: int):
        sched = config["scheduler"]
        sysconf = config["system"]
        classes = sysconf["node_classes"]

        self.n_nodes = sysconf["n_nodes"]
        self.node_classes = classes
        self.weights = np.array([sched["weights"][c] for c in classes], dtype=np.float64)
        # thresholds/config are in ms; AoI/DUI math operates in seconds.
        self.thresholds_s = np.array([sched["thresholds"][c] / 1000.0 for c in classes],
                                      dtype=np.float64)
        self.shield_ceilings_s = np.array([sched["shield_ceilings_s"][c] for c in classes],
                                           dtype=np.float64)
        self.dui_alpha = sched["dui_alpha"]
        self.dui_lambda = sched["dui_lambda"]
        self.dui_beta = sched["dui_beta"]

        ch = measured_params["channel"]
        self.t_slot = ch["t_slot_s"]
        self.sample_interval_s = ch["sample_interval_s"]

        self.rng = np.random.default_rng(seed)
        self.channel = ChannelModel.from_measured_params(measured_params, self.rng)
        self.queues = [LcfsAlarmQueue(sample_interval_s=self.sample_interval_s)
                       for _ in range(self.n_nodes)]

        self.aoi = np.zeros(self.n_nodes, dtype=np.float64)
        self.now_s = 0.0
        self.slot_id = 0

        for q in self.queues:
            q.advance_to(0.0)

    def _apply_shield(self, proposed_action: int) -> tuple[int, bool]:
        """Force-grants the highest-urgency ceiling violator, if any (mirrors
        ns3-sim's SlotTick shield block and criticality_metric_plan.md's
        apply_safety_shield)."""
        violations = self.aoi >= self.shield_ceilings_s
        if not np.any(violations):
            return proposed_action, False
        urgency = self.weights * self.aoi
        urgency_masked = np.where(violations, urgency, -np.inf)
        return int(np.argmax(urgency_masked)), True

    def step(self, action: int) -> SlotResult:
        if not 0 <= action < self.n_nodes:
            raise ValueError(f"action must be a node index in [0, {self.n_nodes}), got {action}")

        self.slot_id += 1
        self.now_s += self.t_slot

        rssi = self.channel.sample_rssi()
        granted_node, shield_fired = self._apply_shield(action)

        queue_status = np.array([q.occupied for q in self.queues], dtype=np.int64)

        uplink_received = False
        delivered_node = None
        delivered_age_s = None
        if self.queues[granted_node].occupied and self.channel.try_deliver(granted_node):
            gen_time = self.queues[granted_node].take()
            delivered_age_s = self.now_s - gen_time
            uplink_received = True
            delivered_node = granted_node

        for i in range(self.n_nodes):
            arrived = uplink_received and i == delivered_node
            self.aoi[i] = update_aoi_for_slot(
                current_aoi=self.aoi[i],
                packet_arrived=arrived,
                delivered_age=delivered_age_s if arrived else 0.0,
                t_slot=self.t_slot,
            )

        for q in self.queues:
            q.advance_to(self.now_s)

        dui = compute_dui(
            aoi=self.aoi, queue=queue_status.astype(np.float64),
            weights=self.weights, thresholds=self.thresholds_s,
            alpha=self.dui_alpha, lambd=self.dui_lambda, beta=self.dui_beta,
        )

        return SlotResult(
            slot_id=self.slot_id,
            granted_node=granted_node,
            shield_fired=shield_fired,
            uplink_received=uplink_received,
            delivered_node=delivered_node,
            delivered_age_s=delivered_age_s,
            aoi=self.aoi.copy(),
            rssi=rssi.copy(),
            queue_status=queue_status,
            energy_proxy_cost=1.0,  # D1.3: WIFI_PS_NONE -> constant TX-energy proxy
            dui=dui,
        )

    def reward(self, result: SlotResult) -> float:
        return calculate_reward(result.dui)
