"""Plot the per-node AoI sawtooth waveform for a single NS-3 scheduler run.

Usage:
    python plot_aoi_sawtooth.py results/rr_seed0.csv [--out-dir results] [--window 30]
"""

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

# Node index -> (color, legend label, shield ceiling in seconds).
# Matches config/system.yaml: node_classes=[urgent, urgent, important, routine],
# shield_ceilings_s={urgent: 2.0, important: 6.0, routine: 20.0}.
NODE_STYLE = {
    0: {"color": "#E63946", "label": "STA-1 (Urgent w=10)", "ceiling": 2.0},
    1: {"color": "#F4845F", "label": "STA-2 (Urgent w=10)", "ceiling": 2.0},
    2: {"color": "#F4A261", "label": "STA-3 (Important w=3)", "ceiling": 6.0},
    3: {"color": "#457B9D", "label": "STA-4 (Routine w=1)", "ceiling": 20.0},
}
CEILING_COLORS = {2.0: "red", 6.0: "orange", 20.0: "blue"}


def plot_aoi_sawtooth(csv_path: Path, out_dir: Path, window_s: float) -> Path:
    df = pd.read_csv(csv_path)
    scheduler_name = df["policy_id"].iloc[0]

    fig, ax = plt.subplots(figsize=(14, 6))
    time = df["timestamp_pi"].values

    for node_idx, style in NODE_STYLE.items():
        col = f"aoi_n{node_idx + 1}"
        ax.plot(time, df[col].values, color=style["color"], label=style["label"],
                linewidth=0.8, alpha=0.9)

    drawn_ceilings = set()
    for style in NODE_STYLE.values():
        ceiling = style["ceiling"]
        if ceiling in drawn_ceilings:
            continue
        drawn_ceilings.add(ceiling)
        ax.axhline(y=ceiling, color=CEILING_COLORS[ceiling], linestyle="--", alpha=0.4,
                   label=f"Ceiling {ceiling:g}s")

    shield_rows = df[df["shield_fired"] == 1]
    for _, row in shield_rows.iterrows():
        granted = int(row["action_granted_node"])
        aoi_col = f"aoi_n{granted + 1}"
        ax.plot(row["timestamp_pi"], row[aoi_col], "rv", markersize=5, alpha=0.7)

    ax.set_xlabel("Time (seconds)", fontsize=12)
    ax.set_ylabel("Age of Information (seconds)", fontsize=12)
    ax.set_title(f"AoI Sawtooth Waveform - {str(scheduler_name).upper()} Scheduler", fontsize=14)
    ax.legend(loc="upper right", fontsize=9)
    if len(time) > 0:
        ax.set_xlim(time[0], min(time[-1], time[0] + window_s))
    ax.grid(True, alpha=0.3)
    plt.tight_layout()

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"aoi_sawtooth_{scheduler_name}.png"
    plt.savefig(out_path, dpi=200)
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_path", type=Path, help="Per-slot telemetry CSV from a single run")
    parser.add_argument("--out-dir", type=Path, default=None,
                         help="Directory for the output PNG (default: alongside the CSV)")
    parser.add_argument("--window", type=float, default=30.0,
                         help="Seconds of trace to display for readability (default: 30)")
    parser.add_argument("--show", action="store_true", help="Also open an interactive window")
    args = parser.parse_args()

    out_dir = args.out_dir or args.csv_path.parent
    out_path = plot_aoi_sawtooth(args.csv_path, out_dir, args.window)
    print(f"Saved: {out_path}")

    if args.show:
        plt.show()


if __name__ == "__main__":
    main()
