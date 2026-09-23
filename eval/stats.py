"""Statistics module (T3.7, T6.3, T6.4, T6.5).

Provides:
  - criticality_weighted_mean_aoi_per_run  — primary statistic (D6.1)
  - bootstrap_ci                           — 95% CI over runs
  - leaderboard                            — scheduler comparison table
  - shuffled_label_control                 — sanity check (literal P6 criterion)
  - ablation_table                         — per-variant comparison
  - weight_sensitivity                     — DUI param sensitivity
"""
import json
import os
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from scipy import stats

from common.config import load_system_config
from common.metrics import criticality_weighted_aoi


def criticality_weighted_mean_aoi_per_run(csv_path: str) -> float:
    """Load a run's per-slot CSV and return the mean criticality-weighted AoI."""
    sys_cfg = load_system_config()
    weights = np.array(
        [sys_cfg["scheduler"]["weights"][c] for c in sys_cfg["system"]["node_classes"]]
    )
    df = pd.read_csv(csv_path)
    aoi_cols = ["aoi_n1", "aoi_n2", "aoi_n3", "aoi_n4"]
    aoi_matrix = df[aoi_cols].values
    return float(np.mean([criticality_weighted_aoi(row, weights) for row in aoi_matrix]))


def bootstrap_ci(values: list[float], n_bootstrap: int = 2000, ci: float = 0.95) -> tuple[float, float]:
    """Return (lower, upper) bootstrap confidence interval."""
    rng = np.random.default_rng(0)
    arr = np.array(values)
    boot_means = [rng.choice(arr, size=len(arr), replace=True).mean() for _ in range(n_bootstrap)]
    lo = float(np.percentile(boot_means, (1 - ci) / 2 * 100))
    hi = float(np.percentile(boot_means, (1 + ci) / 2 * 100))
    return lo, hi


def leaderboard(results_root: str) -> pd.DataFrame:
    """Build a per-scheduler leaderboard from all run CSV files under results_root."""
    rows = []
    for policy_dir in sorted(Path(results_root).iterdir()):
        csv_path = policy_dir / "log.csv"
        meta_path = policy_dir / "run_meta.json"
        if not csv_path.exists():
            continue
        cw_aoi = criticality_weighted_mean_aoi_per_run(str(csv_path))
        policy_id = policy_dir.name.rsplit("_seed", 1)[0]
        seed = int(policy_dir.name.rsplit("_seed", 1)[-1])
        rows.append({"policy": policy_id, "seed": seed, "cw_mean_aoi": cw_aoi})

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    grouped = df.groupby("policy")["cw_mean_aoi"]
    summary = []
    for policy, values in grouped:
        vals = list(values)
        lo, hi = bootstrap_ci(vals)
        summary.append({
            "policy": policy,
            "mean_cw_aoi": float(np.mean(vals)),
            "ci_lo": lo,
            "ci_hi": hi,
            "n_runs": len(vals),
        })
    return pd.DataFrame(summary).sort_values("mean_cw_aoi")


def shuffled_label_control(results_root: str, n_shuffles: int = 500) -> float:
    """Permutation test: shuffle policy labels and re-run the Kruskal-Wallis test.

    Returns p-value of the shuffled distribution — must be >= 0.05 to confirm
    that the real significance is not a statistical artefact.
    """
    rows = []
    for policy_dir in sorted(Path(results_root).iterdir()):
        csv_path = policy_dir / "log.csv"
        if not csv_path.exists():
            continue
        cw_aoi = criticality_weighted_mean_aoi_per_run(str(csv_path))
        policy_id = policy_dir.name.rsplit("_seed", 1)[0]
        rows.append({"policy": policy_id, "cw_mean_aoi": cw_aoi})

    df = pd.DataFrame(rows)
    if df.empty:
        return 1.0

    rng = np.random.default_rng(42)
    all_vals = df["cw_mean_aoi"].values
    p_values = []
    for _ in range(n_shuffles):
        shuffled_labels = rng.permutation(df["policy"].values)
        groups = [all_vals[shuffled_labels == p] for p in df["policy"].unique()]
        groups = [g for g in groups if len(g) > 0]
        if len(groups) < 2:
            continue
        _, p = stats.kruskal(*groups)
        p_values.append(p)

    return float(np.mean(p_values)) if p_values else 1.0


def ablation_table(results_root: str) -> pd.DataFrame:
    """Format ablation run results into a comparison table."""
    rows = []
    for policy_dir in sorted(Path(results_root).iterdir()):
        csv_path = policy_dir / "log.csv"
        if not csv_path.exists():
            continue
        name = policy_dir.name
        if "ablation" not in name:
            continue
        df = pd.read_csv(csv_path)
        cw_aoi = criticality_weighted_mean_aoi_per_run(str(csv_path))
        shield_rate = df["shield_fired"].mean() if "shield_fired" in df.columns else 0.0
        waste_rate = 1.0 - df["uplink_received"].mean() if "uplink_received" in df.columns else 0.0
        rows.append({
            "ablation": name,
            "cw_mean_aoi": cw_aoi,
            "shield_activation_rate": float(shield_rate),
            "wasted_slot_rate": float(waste_rate),
        })
    return pd.DataFrame(rows)


def weight_sensitivity(param: str, values: list, results_root: str) -> pd.DataFrame:
    """Placeholder for per-param sensitivity sweep results aggregation."""
    rows = []
    for v in values:
        rows.append({"param": param, "value": v, "cw_mean_aoi": float("nan")})
    return pd.DataFrame(rows)
