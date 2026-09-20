"""Replay a per-slot hardware log through the simulator's own metric code
(T2.5), so P11 can score hardware runs and simulated runs with exactly
the same AoI/energy accounting -- removing an entire class of "the two
numbers aren't measuring the same thing" bugs.

The log must have the frozen columns from common/contracts/log_schema.py
(the same schema ns3-sim/aoi-scheduler-sim.cc emits).
"""

import csv
from pathlib import Path

from common.contracts.log_schema import SLOT_LOG_COLUMNS
from sim.metrics import MetricsTracker


def replay_log(csv_path: str | Path, t_slot: float, n_nodes: int = 4) -> dict:
    """Replays `csv_path` slot-by-slot and returns a summary dict:
    final per-node AoI, mean per-node AoI, delivered counts, wasted
    slots, and total energy -- all computed via sim/metrics.py, not by
    trusting whatever the log itself claims.
    """
    tracker = MetricsTracker(n_nodes=n_nodes)
    aoi_history = [[] for _ in range(n_nodes)]
    n_rows = 0

    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != SLOT_LOG_COLUMNS:
            raise ValueError(
                f"{csv_path} columns do not match SLOT_LOG_COLUMNS: "
                f"got {reader.fieldnames}"
            )

        for row in reader:
            n_rows += 1
            granted_node = int(row["action_granted_node"])
            uplink_ok = int(row["uplink_received"])
            delivered_age_s = float(row["delivered_age_us"]) / 1e6 if uplink_ok else 0.0

            tracker.step(granted_node, bool(uplink_ok), delivered_age_s, t_slot)
            for i in range(n_nodes):
                aoi_history[i].append(tracker.aoi[i])

    return {
        "n_rows": n_rows,
        "final_aoi": tracker.aoi.copy(),
        "mean_aoi": [sum(h) / len(h) if h else 0.0 for h in aoi_history],
        "delivered_count": tracker.delivered_count.copy(),
        "wasted_slots": tracker.wasted_slots,
        "total_energy": tracker.total_energy,
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_path", type=Path)
    parser.add_argument("--t-slot", type=float, default=0.1)
    args = parser.parse_args()

    summary = replay_log(args.csv_path, args.t_slot)
    for key, value in summary.items():
        print(f"{key}: {value}")
