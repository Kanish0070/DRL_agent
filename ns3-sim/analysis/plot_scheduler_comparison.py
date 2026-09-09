"""Compare all baseline schedulers across seeds using grouped bar charts.

Reads every {scheduler}_seed{N}.csv in a results directory, groups by the
`policy_id` column, and plots four review-panel metrics with mean +/- std
error bars across seeds:
    - Criticality-Weighted Mean AoI (D6.1's primary statistic)
    - Urgent P99 AoI
    - Shield Activation Rate
    - Packet Delivery Ratio

Usage:
    python plot_scheduler_comparison.py results/ [--out results/scheduler_comparison.png]
"""

import argparse
import glob
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# scheduler.weights from config/system.yaml, node_classes=[urgent, urgent, important, routine]
WEIGHTS = np.array([10.0, 10.0, 3.0, 1.0])
WEIGHT_SUM = WEIGHTS.sum()

SCHEDULER_ORDER = ["rr", "fpq", "maxweight", "cag", "random"]
SCHEDULER_COLORS = {
    "rr": "#8D99AE",
    "fpq": "#F4A261",
    "maxweight": "#2A9D8F",
    "cag": "#1D3557",
    "random": "#E63946",
}
SCHEDULER_LABELS = {
    "rr": "Round Robin",
    "fpq": "Fixed Priority",
    "maxweight": "Max-Weight",
    "cag": "Channel-Aware Greedy",
    "random": "Random",
}


def _criticality_weighted_mean_aoi(df: pd.DataFrame) -> float:
    aoi_cols = ["aoi_n1", "aoi_n2", "aoi_n3", "aoi_n4"]
    weighted = (df[aoi_cols].values * WEIGHTS).sum(axis=1) / WEIGHT_SUM
    return float(weighted.mean())


def _urgent_p99_aoi(df: pd.DataFrame) -> float:
    urgent_max = df[["aoi_n1", "aoi_n2"]].max(axis=1)
    return float(np.percentile(urgent_max, 99))


def _shield_activation_rate_pct(df: pd.DataFrame) -> float:
    return 100.0 * df["shield_fired"].sum() / len(df)


def _pdr_pct(df: pd.DataFrame) -> float:
    return 100.0 * df["uplink_received"].sum() / len(df)


METRICS = [
    ("Criticality-Weighted Mean AoI (ms)", lambda df: _criticality_weighted_mean_aoi(df) * 1000.0),
    ("Urgent P99 AoI (ms)", lambda df: _urgent_p99_aoi(df) * 1000.0),
    ("Shield Activation Rate (%)", _shield_activation_rate_pct),
    ("Packet Delivery Ratio (%)", _pdr_pct),
]


def load_runs_by_scheduler(results_dir: Path) -> dict[str, list[pd.DataFrame]]:
    runs: dict[str, list[pd.DataFrame]] = {}
    for csv_path in sorted(glob.glob(str(results_dir / "*.csv"))):
        df = pd.read_csv(csv_path)
        if df.empty or "policy_id" not in df.columns:
            continue
        scheduler = str(df["policy_id"].iloc[0])
        runs.setdefault(scheduler, []).append(df)
    return runs


def plot_comparison(results_dir: Path, out_path: Path) -> Path:
    runs = load_runs_by_scheduler(results_dir)
    if not runs:
        raise SystemExit(f"No scheduler CSVs found under {results_dir}")

    schedulers = [s for s in SCHEDULER_ORDER if s in runs] + \
        [s for s in runs if s not in SCHEDULER_ORDER]

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    axes = axes.flatten()

    for ax, (title, metric_fn) in zip(axes, METRICS):
        means, stds, labels, colors = [], [], [], []
        for sched in schedulers:
            values = [metric_fn(df) for df in runs[sched]]
            means.append(np.mean(values))
            stds.append(np.std(values))
            labels.append(SCHEDULER_LABELS.get(sched, sched))
            colors.append(SCHEDULER_COLORS.get(sched, "#999999"))

        x = np.arange(len(schedulers))
        ax.bar(x, means, yerr=stds, capsize=4, color=colors)
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=20, ha="right")
        ax.set_title(title, fontsize=11)
        ax.grid(True, axis="y", alpha=0.3)

    fig.suptitle("Baseline Scheduler Comparison (mean ± std across seeds)", fontsize=14)
    plt.tight_layout()

    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=200)
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results_dir", type=Path, help="Directory containing *_seed*.csv files")
    parser.add_argument("--out", type=Path, default=None,
                         help="Output PNG path (default: <results_dir>/scheduler_comparison.png)")
    args = parser.parse_args()

    out_path = args.out or (args.results_dir / "scheduler_comparison.png")
    saved = plot_comparison(args.results_dir, out_path)
    print(f"Saved: {saved}")


if __name__ == "__main__":
    main()
