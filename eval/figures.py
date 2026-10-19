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

POLICY_NAMES = {
    'rr': 'Round Robin',
    'fpq': 'Fixed Priority Queue',
    'maxweight': 'Max-Weight',
    'cag': 'Channel-Aware Greedy',
    'random': 'Random',
    'oracle': 'Oracle',
    'dqn': 'Deep Q-Network'
}

def plot_leaderboard(board: pd.DataFrame, out_path: str):
    # Remove the oracle baseline from the graph
    board = board[board["policy"].str.lower() != "oracle"]

    if board.empty:
        print("[figures] No data for leaderboard — skipping.")
        return
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Map to lookup table names
    board["policy_name"] = board["policy"].apply(lambda p: POLICY_NAMES.get(p.lower(), p.upper()))
    
    yerr_lo = board["mean_cw_aoi"] - board["ci_lo"]
    yerr_hi = board["ci_hi"] - board["mean_cw_aoi"]
    
    bars = ax.barh(board["policy_name"], board["mean_cw_aoi"],
            xerr=[yerr_lo, yerr_hi], capsize=4, color="steelblue", alpha=0.8)
            
    # Add exact values to each bar
    for bar in bars:
        width = bar.get_width()
        ax.annotate(f'{width:.4f}',
                    xy=(width, bar.get_y() + bar.get_height() / 2),
                    xytext=(35, 0),  # Offset to clear error bars
                    textcoords="offset points",
                    ha='left', va='center', fontsize=9, fontweight='bold')
                    
    # Extend x-axis slightly so labels fit
    max_val = board["ci_hi"].max()
    ax.set_xlim(0, max_val * 1.2)
    
    ax.set_xlabel("Criticality-Weighted Mean AoI (s)")
    ax.set_title("Scheduler Leaderboard (Lower is Better)")
    ax.invert_yaxis()
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"[figures] Saved {out_path}")


import plotly.graph_objects as go

def plot_aoi_traces(results_root: str, out_path_png: str, out_path_html: str, max_schedulers: int = 10):
    fig_mpl, ax = plt.subplots(figsize=(12, 6))
    fig_plotly = go.Figure()
    
    plotted = 0
    seen_policies = set()
    
    for policy_dir in sorted(Path(results_root).iterdir()):
        csv_path = policy_dir / "log.csv"
        if not csv_path.exists():
            continue
            
        policy_id = policy_dir.name.rsplit("_seed", 1)[0]
        if policy_id in seen_policies or policy_id.lower() == "oracle":
            continue
            
        df = pd.read_csv(csv_path)
        mean_aoi = df[["aoi_n1", "aoi_n2", "aoi_n3", "aoi_n4"]].mean(axis=1)
        display_name = POLICY_NAMES.get(policy_id.lower(), policy_id.upper())
        
        y_vals = mean_aoi.values[:500]
        x_vals = np.arange(len(y_vals))
        
        # Plotly Trace
        fig_plotly.add_trace(go.Scatter(x=x_vals, y=y_vals, mode='lines', name=display_name, opacity=0.8))
        # Matplotlib Trace
        ax.plot(y_vals, label=display_name, alpha=0.7)
        
        seen_policies.add(policy_id)
        plotted += 1
        if plotted >= max_schedulers:
            break
            
    # Matplotlib styling
    ax.set_xlabel("Slot")
    ax.set_ylabel("Mean AoI across nodes (s)")
    ax.set_title("AoI Traces (First 500 Slots)")
    ax.legend(fontsize=9, bbox_to_anchor=(1.05, 1), loc='upper left')
    fig_mpl.tight_layout()
    fig_mpl.savefig(out_path_png, dpi=150)
    plt.close(fig_mpl)
    
    # Plotly styling
    fig_plotly.update_layout(
        title="Interactive AoI Traces (Click legend to toggle schedulers)",
        xaxis_title="Slot",
        yaxis_title="Mean AoI across nodes (s)",
        template="plotly_white"
    )
    fig_plotly.write_html(out_path_html)
    
    print(f"[figures] Saved {out_path_png} and {out_path_html}")


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
        if policy_id.lower() == "oracle":
            continue
        rows.append({"policy": policy_id, "shield_rate": rate})

    if not rows:
        print("[figures] No shield data — skipping shield_rates.png")
        return

    df_s = pd.DataFrame(rows).groupby("policy")["shield_rate"].mean().reset_index()
    df_s["policy_name"] = df_s["policy"].apply(lambda p: POLICY_NAMES.get(p.lower(), p.upper()))
    
    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.bar(df_s["policy_name"], df_s["shield_rate"], color="tomato", alpha=0.8)
    
    ax.set_ylabel("Shield Activation Rate")
    ax.set_title("Shield Activation Rate per Scheduler")
    
    # 2% line per user request
    ax.axhline(0.02, color="black", linestyle="--", label="2% target")
    
    # Zoom Y axis to see small peaks
    max_rate = df_s["shield_rate"].max()
    zoom_max = max(0.025, max_rate * 1.2)
    ax.set_ylim(0, zoom_max)
    
    # Annotate bars
    for bar in bars:
        height = bar.get_height()
        ax.annotate(f'{height:.4f}',
                    xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3),
                    textcoords="offset points",
                    ha='center', va='bottom', fontsize=9, fontweight='bold')
                    
    plt.xticks(rotation=45, ha='right')
    ax.legend()
    fig.tight_layout()
    fig.savefig(str(Path(out_path).parent / "shield_rates_zoomed.png"), dpi=150)
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

    out_dir = Path(args.out_dir)
    out_dir.mkdir(exist_ok=True)
    board = leaderboard(args.results_dir)

    plot_leaderboard(board, str(out_dir / "leaderboard_updated.png"))
    plot_aoi_traces(args.results_dir, str(out_dir / "aoi_traces_updated.png"), str(out_dir / "aoi_traces_interactive.html"))
    plot_shield_rates(args.results_dir, str(out_dir / "shield_rates_zoomed.png"))
    plot_ablation_table(args.results_dir, str(out_dir / "ablation_table.png"))
    print("[figures] Done.")


if __name__ == "__main__":
    main()
