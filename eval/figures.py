"""Figure generation pack (T6.6).

Every figure is regenerable with one command:
    python -m eval.figures --results-dir results --out-dir figures

Produces:
  - leaderboard.png      — bar chart with 95% CI
  - aoi_traces.png       — per-scheduler AoI-over-time traces
  - shield_rates.png     — shield activation rate per scheduler
  - ablation_table.png   — ablation comparison table as a figure
"""
import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from eval.stats import leaderboard, ablation_table, criticality_weighted_mean_aoi_per_run


def plot_leaderboard(board: pd.DataFrame, out_path: str):
    if board.empty:
        print("[figures] No data for leaderboard — skipping.")
        return
    fig, ax = plt.subplots(figsize=(8, 5))
    yerr_lo = board["mean_cw_aoi"] - board["ci_lo"]
    yerr_hi = board["ci_hi"] - board["mean_cw_aoi"]
    ax.barh(board["policy"], board["mean_cw_aoi"],
            xerr=[yerr_lo, yerr_hi], capsize=4, color="steelblue", alpha=0.8)
    ax.set_xlabel("Criticality-Weighted Mean AoI (s)")
    ax.set_title("Scheduler Leaderboard — PLACEHOLDER parameters")
    ax.invert_yaxis()
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"[figures] Saved {out_path}")


def plot_aoi_traces(results_root: str, out_path: str, max_schedulers: int = 6):
    fig, ax = plt.subplots(figsize=(10, 5))
    plotted = 0
    for policy_dir in sorted(Path(results_root).iterdir()):
        csv_path = policy_dir / "log.csv"
        if not csv_path.exists() or plotted >= max_schedulers:
            continue
        df = pd.read_csv(csv_path)
        policy_id = policy_dir.name.rsplit("_seed", 1)[0]
        mean_aoi = df[["aoi_n1", "aoi_n2", "aoi_n3", "aoi_n4"]].mean(axis=1)
        ax.plot(mean_aoi.values[:500], label=policy_id, alpha=0.7)
        plotted += 1
    ax.set_xlabel("Slot")
    ax.set_ylabel("Mean AoI across nodes (s)")
    ax.set_title("AoI Traces — first 500 slots — PLACEHOLDER parameters")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"[figures] Saved {out_path}")


def plot_shield_rates(results_root: str, out_path: str):
    rows = []
    for policy_dir in sorted(Path(results_root).iterdir()):
        csv_path = policy_dir / "log.csv"
        if not csv_path.exists():
            continue
        df = pd.read_csv(csv_path)
        if "shield_fired" not in df.columns:
            continue
        rate = float(df["shield_fired"].mean())
        policy_id = policy_dir.name.rsplit("_seed", 1)[0]
        rows.append({"policy": policy_id, "shield_rate": rate})

    if not rows:
        print("[figures] No shield data — skipping shield_rates.png")
        return

    df_s = pd.DataFrame(rows).groupby("policy")["shield_rate"].mean().reset_index()
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(df_s["policy"], df_s["shield_rate"], color="tomato", alpha=0.8)
    ax.set_ylabel("Shield Activation Rate")
    ax.set_title("Shield Activation Rate per Scheduler")
    ax.axhline(0.05, color="black", linestyle="--", label="5% target")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"[figures] Saved {out_path}")


def plot_ablation_table(results_root: str, out_path: str):
    df = ablation_table(results_root)
    if df.empty:
        print("[figures] No ablation data — skipping.")
        return
    fig, ax = plt.subplots(figsize=(8, max(3, len(df) * 0.6)))
    ax.axis("off")
    tbl = ax.table(
        cellText=df.round(4).values,
        colLabels=df.columns.tolist(),
        loc="center",
        cellLoc="center",
    )
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(9)
    ax.set_title("Ablation Study Results")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"[figures] Saved {out_path}")


def main():
    parser = argparse.ArgumentParser(description="Generate P6 figure pack.")
    parser.add_argument("--results-dir", default="results")
    parser.add_argument("--out-dir", default="figures")
    args = parser.parse_args()

    Path(args.out_dir).mkdir(exist_ok=True)
    board = leaderboard(args.results_dir)

    plot_leaderboard(board, f"{args.out_dir}/leaderboard.png")
    plot_aoi_traces(args.results_dir, f"{args.out_dir}/aoi_traces.png")
    plot_shield_rates(args.results_dir, f"{args.out_dir}/shield_rates.png")
    plot_ablation_table(args.results_dir, f"{args.out_dir}/ablation_table.png")
    print("[figures] Done.")


if __name__ == "__main__":
    main()
