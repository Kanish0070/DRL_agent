"""Demo driver for the P2 simulation core (sim/network.py).

Runs two simple policies over the same seeded episode and plots the
resulting AoI sawtooth waveforms side by side:

  - Round Robin: a_t = t mod 4 (fairness anchor, ignores urgency)
  - Greedy-DUI: a_t = argmax_i DUI_i(t) (the reward metric from
    common/metrics.py, i.e. "serve whoever is most urgent right now")

Neither is the frozen P3 scheduler interface (schedulers/ doesn't exist
yet) -- this is a standalone demonstration that the simulation core
produces sensible, contract-correct AoI dynamics, using the same math
that P3/P4 will build on.

Usage:
    python -m tools.demo_sim_run [--episode-length 300] [--seed 0] [--out-dir tools/demo_output]
"""

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import yaml

from common.config import load_system_config
from common.contracts.state_spec import DELTA_MAX, RSSI_MIN, RSSI_RANGE, W_MAX
from common.metrics import calculate_reward, compute_dui
from sim.network import NetworkSim, SimConfig

NODE_LABELS = ["STA-1 (Urgent w=10)", "STA-2 (Urgent w=10)",
               "STA-3 (Important w=3)", "STA-4 (Routine w=1)"]
NODE_COLORS = ["#E63946", "#F4845F", "#F4A261", "#457B9D"]


def _denormalize(obs: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """obs is the 16-D normalized StateSpec vector; recover raw aoi/queue/rssi
    per node for plotting (weight is constant per node, not needed here)."""
    obs = obs.reshape(4, 4)
    aoi = obs[:, 0] * DELTA_MAX
    queue = obs[:, 1]
    rssi = obs[:, 2] * RSSI_RANGE + RSSI_MIN
    return aoi, queue, rssi


def round_robin_action(slot_idx: int, obs: np.ndarray) -> int:
    return slot_idx % 4


def greedy_dui_action(slot_idx: int, obs: np.ndarray, thresholds_s: np.ndarray) -> int:
    aoi, queue, _ = _denormalize(obs)
    weights = obs.reshape(4, 4)[:, 3] * W_MAX
    dui = compute_dui(aoi, queue, weights, thresholds_s, alpha=2.0, lambd=1.5, beta=0.5)
    return int(np.argmax(dui))


def run_policy(sim_config: SimConfig, seed: int, policy_name: str) -> dict:
    sim = NetworkSim(sim_config)
    obs = sim.reset(seed=seed)
    thresholds_s = sim.thresholds_s
    weights = sim.weights

    history = {"aoi": [], "reward": [], "shield_would_fire": 0}
    for slot in range(sim_config.episode_length):
        if policy_name == "round_robin":
            action = round_robin_action(slot, obs)
        elif policy_name == "greedy_dui":
            action = greedy_dui_action(slot, obs, thresholds_s)
        else:
            raise ValueError(policy_name)

        obs, info = sim.step(action)
        aoi, queue, _ = _denormalize(obs)
        history["aoi"].append(aoi.copy())
        dui = compute_dui(aoi, queue, weights, thresholds_s, alpha=2.0, lambd=1.5, beta=0.5)
        history["reward"].append(calculate_reward(dui))

    history["aoi"] = np.array(history["aoi"])  # (episode_length, 4)
    history["mean_aoi_per_node"] = history["aoi"].mean(axis=0)
    history["weighted_mean_aoi"] = float(np.mean(history["aoi"] @ weights) / weights.sum())
    history["final_summary"] = {
        "empty_grants": sim.empty_grants,
        "channel_failures": sim.channel_failures,
        "wasted_slots": sim.metrics.wasted_slots,
        "total_energy": sim.metrics.total_energy,
    }
    return history


def plot_comparison(histories: dict[str, dict], t_slot: float, out_path: Path) -> Path:
    # Deliberately NOT sharing the y-axis: greedy-DUI's routine-node AoI
    # spikes far higher than anything round robin ever produces, and
    # squashing both onto one scale would hide round robin's own detail.
    fig, axes = plt.subplots(1, 2, figsize=(16, 6))
    titles = {
        "round_robin": "Round Robin",
        "greedy_dui": "Greedy-DUI, no shield yet (P4 not implemented)",
    }

    for ax, (policy_name, history) in zip(axes, histories.items()):
        time = np.arange(len(history["aoi"])) * t_slot
        for i in range(4):
            ax.plot(time, history["aoi"][:, i], color=NODE_COLORS[i],
                    label=NODE_LABELS[i], linewidth=0.9)
        ax.set_title(f"{titles[policy_name]}\nweighted-mean AoI = "
                     f"{history['weighted_mean_aoi'] * 1000:.1f} ms", fontsize=12)
        ax.set_xlabel("Time (s)")
        ax.set_ylabel("Age of Information (s)")
        ax.grid(True, alpha=0.3)
        ax.legend(loc="upper left", fontsize=9)

    fig.suptitle(
        "P2 Simulation Core -- AoI dynamics under two policies (same seed)\n"
        "Greedy-DUI cuts Urgent-node AoI ~30% but, with no shield yet, lets "
        "the Routine node's AoI run away -- motivating the P4 safety shield",
        fontsize=12,
    )
    plt.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=200)
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--episode-length", type=int, default=300)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--out-dir", type=Path, default=Path("tools/demo_output"))
    args = parser.parse_args()

    system_config = load_system_config("config/system.yaml")
    with open("config/measured_params.yaml") as f:
        measured_params = yaml.safe_load(f)
    sim_config = SimConfig.from_configs(system_config, measured_params,
                                         episode_length=args.episode_length)

    histories = {}
    for policy_name in ("round_robin", "greedy_dui"):
        histories[policy_name] = run_policy(sim_config, seed=args.seed, policy_name=policy_name)

    print(f"{'Policy':<14}{'Weighted-Mean AoI (ms)':<24}{'Per-node mean AoI, ms [urg/urg/imp/rout]'}")
    for policy_name, history in histories.items():
        per_node = ", ".join(f"{v * 1000:.0f}" for v in history["mean_aoi_per_node"])
        print(f"{policy_name:<14}{history['weighted_mean_aoi'] * 1000:<24.2f}[{per_node}]")

    print(
        "\nNote: greedy-DUI drives the two Urgent nodes' AoI far below Round Robin's, "
        "but with no safety shield in place yet (P4 is not implemented), it can starve "
        "the Routine node badly enough that its own AoI dominates the *weighted*-mean "
        "metric despite its small weight -- this is precisely the failure mode the "
        "upcoming Safety Shield exists to bound."
    )

    out_path = args.out_dir / "sim_core_demo.png"
    saved = plot_comparison(histories, t_slot=sim_config.t_slot, out_path=out_path)
    print(f"\nSaved: {saved}")


if __name__ == "__main__":
    main()
