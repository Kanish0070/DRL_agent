import argparse
import csv
import json
import os
from pathlib import Path
import numpy as np

from common.config import load_system_config, load_measured_params
from common.contracts.log_schema import SLOT_LOG_COLUMNS, validate_slot_row
from common.provenance import write_run_meta
from sim.network import SimConfig, NetworkSim

from schedulers.round_robin import RoundRobinScheduler
from schedulers.fixed_priority import FixedPriorityScheduler
from schedulers.max_weight import MaxWeightScheduler
from schedulers.channel_aware_greedy import ChannelAwareGreedyScheduler
from schedulers.random_scheduler import RandomScheduler
from schedulers.oracle import OracleScheduler
from rl.shield import apply_safety_shield

def get_scheduler(name: str, sys_cfg: dict, meas_cfg: dict):
    if name == "rr": return RoundRobinScheduler()
    if name == "fpq": return FixedPriorityScheduler(sys_cfg["system"]["node_classes"])
    if name == "maxweight": return MaxWeightScheduler()
    if name == "cag": return ChannelAwareGreedyScheduler(meas_cfg)
    if name == "random": return RandomScheduler()
    if name == "oracle": return OracleScheduler()
    raise ValueError(f"Unknown scheduler {name}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scheduler", required=True, choices=["rr", "fpq", "maxweight", "cag", "random", "oracle", "dqn"])
    parser.add_argument("--model-path", help="Path to DQN model if scheduler is dqn")
    parser.add_argument("--n-slots", type=int, help="Override episode_length")
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--out-dir", default="results")
    args = parser.parse_args()

    sys_cfg = load_system_config()
    meas_cfg = load_measured_params()
    ep_len = args.n_slots if args.n_slots else sys_cfg["rl"]["episode_length"]
    
    sim_config = SimConfig.from_configs(sys_cfg, meas_cfg, episode_length=ep_len)
    sim = NetworkSim(sim_config)
    sim.reset(args.seed)

    scheduler = get_scheduler(args.scheduler, sys_cfg, meas_cfg) if args.scheduler != "dqn" else None
    if args.scheduler == "dqn":
        from stable_baselines3 import DQN
        model = DQN.load(args.model_path)
    
    shield_ceilings_s = np.array([sys_cfg["scheduler"]["shield_ceilings_s"][c] for c in sys_cfg["system"]["node_classes"]])
    
    out_dir = Path(args.out_dir) / f"{args.scheduler}_seed{args.seed}"
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "log.csv"
    
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=SLOT_LOG_COLUMNS)
        writer.writeheader()
        
        for slot in range(ep_len):
            aoi = sim.metrics.aoi.copy() if sim.metrics else np.zeros(sim.cfg.n_nodes)
            rssi = sim.rssi_observed.copy()
            queue = np.array([q.has_data() for q in sim.queues])
            weights = sim.weights
            
            # Special case for Oracle
            if args.scheduler == "oracle":
                sim.advance_slot()
                true_p = sim.true_success_probabilities()
                action = scheduler.select_with_oracle(aoi, queue, weights, true_p)
                obs, info = sim.resolve(action)
                shield_fired = False
            elif args.scheduler == "dqn":
                obs_vec = sim._build_observation().astype(np.float32)
                action, _ = model.predict(obs_vec, deterministic=True)
                action = int(action)
                action, shield_fired = apply_safety_shield(action, aoi, weights, shield_ceilings_s)
                obs, info = sim.step(action)
            else:
                proposed_action = scheduler.select(aoi, rssi, queue, weights)
                action, shield_fired = apply_safety_shield(proposed_action, aoi, weights, shield_ceilings_s)
                obs, info = sim.step(action)
            
            # Build CSV row
            row = {
                "slot_id": slot,
                "timestamp_pi": slot * sim.cfg.t_slot,
                "policy_id": args.scheduler,
                "action_granted_node": action,
                "shield_fired": shield_fired,
                "uplink_received": info.get("packet_arrived", False),
                "delivered_node": action if info.get("packet_arrived") else -1,
                "delivered_age_us": int(info.get("delivered_age_s", 0) * 1_000_000),
                "rssi_at_rx": rssi[action] if info.get("packet_arrived") else 0.0,
                "queue_status": sum(queue),
                "energy_proxy_cost": info.get("total_energy", 0.0),
                "malformed_dropped": 0,
                "stale_dropped": 0,
                "aoi_n1": aoi[0], "aoi_n2": aoi[1], "aoi_n3": aoi[2], "aoi_n4": aoi[3],
                "rssi_n1": rssi[0], "rssi_n2": rssi[1], "rssi_n3": rssi[2], "rssi_n4": rssi[3]
            }
            assert validate_slot_row(row)
            writer.writerow(row)
            
    write_run_meta(str(out_dir), policy_id=args.scheduler, seed=args.seed)

if __name__ == "__main__":
    main()
