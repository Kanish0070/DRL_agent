"""Discrete-slot network simulator core (T2.4).

`NetworkSim` is the seeded, deterministic engine every scheduler (baseline
or learned) is driven through: `reset(seed)` starts a fresh episode,
`step(action)` grants one node for the slot and returns the resulting
16-D StateSpec observation plus a diagnostics dict.

It deliberately does NOT know about schedulers, rewards, or the safety
shield -- those are P3/P4 concerns layered on top. Its only job is to
advance the physical/queueing state correctly:

  - the channel (sim/channel.py) evolves for every node every slot,
    independent of who is granted;
  - each node's sample queue (sim/queue.py) receives arrivals and ages;
  - the granted node's transmission is resolved against the channel,
    with a small probability of landing a slot late (F2.6) rather than
    being silently delivered within the same slot;
  - AoI/energy accounting (sim/metrics.py) applies the one true AoI rule;
  - RSSI is only ever refreshed for a node when it is actually heard from
    (a delivery or a heartbeat) -- observed RSSI staleness is tracked
    explicitly (F2.5/D3.2), so the agent cannot see channel information
    hardware could not supply.

No function here reads or writes the global `np.random` state (F2.10):
all randomness is drawn from the `np.random.Generator` created in
`reset(seed)`.
"""

from dataclasses import dataclass

import numpy as np

from common.contracts.state_spec import NetworkState, NodeState
from sim.channel import ChannelModel, ChannelParams
from sim.metrics import MetricsTracker
from sim.queue import NodeQueue

# Radial placement matching ns3-sim/aoi-scheduler-sim.cc, used as the
# default distance set until P1/T2.7 freeze real calibrated load points.
DEFAULT_DISTANCES_M = np.array([5.0, 8.0, 12.0, 18.0])


@dataclass
class SimConfig:
    n_nodes: int
    node_classes: list[str]
    weights_by_class: dict[str, float]
    thresholds_by_class_s: dict[str, float]
    queue_discipline: str
    queue_capacity: int
    heartbeat_period_s: float
    t_slot: float
    late_arrival_probability: float
    episode_length: int
    arrival_prob: np.ndarray  # per-node Bernoulli arrival probability
    channel_params: ChannelParams

    @classmethod
    def from_configs(cls, system_config: dict, measured_params: dict,
                      episode_length: int, arrival_prob: np.ndarray | float = 1.0) -> "SimConfig":
        n_nodes = system_config["system"]["n_nodes"]
        node_classes = system_config["system"]["node_classes"]
        sched = system_config["scheduler"]
        # scheduler.thresholds is in milliseconds; the sim/AoI contract works in seconds.
        thresholds_s = {cls_name: ms / 1000.0 for cls_name, ms in sched["thresholds"].items()}

        arrival = np.asarray(arrival_prob, dtype=np.float64)
        if arrival.ndim == 0:
            arrival = np.full(n_nodes, float(arrival))

        return cls(
            n_nodes=n_nodes,
            node_classes=node_classes,
            weights_by_class=sched["weights"],
            thresholds_by_class_s=thresholds_s,
            queue_discipline=sched["queue_discipline"],
            queue_capacity=sched["queue_size"],
            heartbeat_period_s=sched["heartbeat_period_s"],
            t_slot=measured_params["timing"]["slot_duration_s"],
            late_arrival_probability=measured_params["timing"]["late_arrival_probability"],
            episode_length=episode_length,
            arrival_prob=arrival,
            channel_params=ChannelParams.from_measured_params(measured_params),
        )


class NetworkSim:
    def __init__(self, sim_config: SimConfig, distances_m: np.ndarray = DEFAULT_DISTANCES_M):
        self.cfg = sim_config
        n = sim_config.n_nodes
        self.weights = np.array([sim_config.weights_by_class[c] for c in sim_config.node_classes])
        self.thresholds_s = np.array(
            [sim_config.thresholds_by_class_s[c] for c in sim_config.node_classes]
        )
        self.distances_m = np.asarray(distances_m, dtype=np.float64)
        self.channel_params = sim_config.channel_params

        self.rng: np.random.Generator | None = None
        self.channel: ChannelModel | None = None
        self.queues: list[NodeQueue] = []
        self.metrics: MetricsTracker | None = None
        self.rssi_observed = np.zeros(n)
        self.rssi_age_s = np.zeros(n)
        self._heartbeat_countdown = np.zeros(n)
        self._pending_late_delivery: dict[int, float] = {}
        self.slot_idx = 0

        self.empty_grants = 0
        self.channel_failures = 0

    def reset(self, seed: int) -> np.ndarray:
        n = self.cfg.n_nodes
        self.rng = np.random.Generator(np.random.PCG64(seed))
        self.channel = ChannelModel(self.distances_m, self.channel_params)
        self.queues = [NodeQueue(self.cfg.queue_discipline, self.cfg.queue_capacity) for _ in range(n)]
        self.metrics = MetricsTracker(n_nodes=n)
        self.rssi_observed = self.channel.rssi_all().copy()
        self.rssi_age_s = np.zeros(n)
        self._heartbeat_countdown = np.full(n, self.cfg.heartbeat_period_s)
        self._pending_late_delivery = {}
        self.slot_idx = 0
        self.empty_grants = 0
        self.channel_failures = 0

        return self._build_observation()

    def step(self, action: int) -> tuple[np.ndarray, dict]:
        self.advance_slot()
        return self.resolve(action)

    def advance_slot(self) -> None:
        t_slot = self.cfg.t_slot
        self.channel.step(self.rng)

        # Arrivals, then ageing of whatever is left unsent.
        for i in range(self.cfg.n_nodes):
            if self.rng.random() < self.cfg.arrival_prob[i]:
                self.queues[i].push()
            self.queues[i].age_all(t_slot)

        # Heartbeat-rate RSSI refresh for every node (D3.2): independent
        # of grants, each node reports its RSSI on its own 2s cadence.
        self.rssi_age_s += t_slot
        self._heartbeat_countdown -= t_slot
        for i in range(self.cfg.n_nodes):
            if self._heartbeat_countdown[i] <= 0.0:
                self._refresh_rssi(i)
                self._heartbeat_countdown[i] += self.cfg.heartbeat_period_s

    def resolve(self, action: int) -> tuple[np.ndarray, dict]:
        if not (0 <= action < self.cfg.n_nodes):
            raise ValueError(f"action {action} out of range for {self.cfg.n_nodes} nodes")

        t_slot = self.cfg.t_slot

        # A late delivery scheduled by a previous slot resolves now,
        # taking priority over this slot's own grant outcome for that node.
        packet_arrived = False
        delivered_age = 0.0
        if action in self._pending_late_delivery:
            delivered_age = self._pending_late_delivery.pop(action)
            packet_arrived = True
            self._refresh_rssi(action)
        elif self.queues[action].has_data():
            success = self.channel.draw_success(action, self.rng)
            if success:
                age = self.queues[action].pop_for_delivery()
                if self.rng.random() < self.cfg.late_arrival_probability:
                    # F2.6: delivery physically succeeds but lands next
                    # slot rather than this one.
                    self._pending_late_delivery[action] = age + t_slot
                else:
                    packet_arrived = True
                    delivered_age = age
                    self._refresh_rssi(action)
            else:
                self.channel_failures += 1
        else:
            self.empty_grants += 1

        self.metrics.step(action, packet_arrived, delivered_age, t_slot)

        self.slot_idx += 1
        truncated = self.slot_idx >= self.cfg.episode_length

        obs = self._build_observation()
        info = {
            "terminated": False,  # continuing task (F2.7): only ever truncated
            "truncated": truncated,
            "packet_arrived": packet_arrived,
            "delivered_age_s": delivered_age,
            "empty_grants": self.empty_grants,
            "channel_failures": self.channel_failures,
            "wasted_slots": self.metrics.wasted_slots,
            "total_energy": self.metrics.total_energy,
            "aoi": self.metrics.aoi.copy(),
            "rssi_age_s": self.rssi_age_s.copy(),
            "queue_status": np.array([q.has_data() for q in self.queues]),
        }
        return obs, info

    def true_success_probabilities(self) -> np.ndarray:
        """Returns ground-truth channel delivery probabilities for all nodes.
        Only valid to call after `advance_slot()` and before `advance_slot()` is called again.
        Used exclusively for Oracle scheduler baselines.
        """
        return np.array([self.channel.success_probability(i) for i in range(self.cfg.n_nodes)])

    def _refresh_rssi(self, node_idx: int) -> None:
        self.rssi_observed[node_idx] = self.channel.rssi(node_idx)
        self.rssi_age_s[node_idx] = 0.0

    def _build_observation(self) -> np.ndarray:
        nodes = [
            NodeState(
                aoi=float(self.metrics.aoi[i]) if self.metrics else 0.0,
                queue=int(self.queues[i].has_data()) if self.queues else 0,
                rssi=float(self.rssi_observed[i]),
                weight=float(self.weights[i]),
            )
            for i in range(self.cfg.n_nodes)
        ]
        return NetworkState(nodes=nodes).to_vector()
