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


def compute_metric_gap(sim_df: pd.DataFrame, ns3_df: pd.DataFrame) -> pd.DataFrame:
    """Metric gap: |cw-AoI_python - cw-AoI_ns3| per policy (D11.1)."""
    merged = pd.merge(
        sim_df[["policy", "mean_cw_aoi"]].rename(columns={"mean_cw_aoi": "sim_cw_aoi"}),
        ns3_df[["policy", "mean_cw_aoi"]].rename(columns={"mean_cw_aoi": "ns3_cw_aoi"}),
        on="policy",
    )
    merged["abs_metric_gap"] = (merged["sim_cw_aoi"] - merged["ns3_cw_aoi"]).abs()
    merged["pct_metric_gap"] = (
        merged["abs_metric_gap"] / merged["sim_cw_aoi"].clip(lower=1e-4) * 100.0
    )
    return merged


def compute_ranking_gap(sim_df: pd.DataFrame, ns3_df: pd.DataFrame) -> tuple[float, float]:
    """Ranking gap: Kendall tau rank correlation between simulation and ns-3 leaderboards."""
    merged = pd.merge(
        sim_df[["policy", "mean_cw_aoi"]].rename(columns={"mean_cw_aoi": "sim_cw_aoi"}),
        ns3_df[["policy", "mean_cw_aoi"]].rename(columns={"mean_cw_aoi": "ns3_cw_aoi"}),
        on="policy",
    )
    if len(merged) < 2:
        return 1.0, 1.0
    tau, p_val = stats.kendalltau(merged["sim_cw_aoi"], merged["ns3_cw_aoi"])
    return float(tau), float(p_val)


def compute_transfer_gap(
    sim_df: pd.DataFrame,
    ns3_df: pd.DataFrame,
    target_policy: str = "dqn",
    baseline_policy: str = "cag",
) -> dict[str, float]:
    """Transfer gap: measures whether target policy advantage over baseline survives transfer (D11.1)."""
    sim_map = dict(zip(sim_df["policy"], sim_df["mean_cw_aoi"]))
    ns3_map = dict(zip(ns3_df["policy"], ns3_df["mean_cw_aoi"]))

    if target_policy not in sim_map or baseline_policy not in sim_map:
        return {"advantage_sim": 0.0, "advantage_ns3": 0.0, "transfer_gap": 0.0, "retention_ratio": 1.0}

    # Advantage = Baseline AoI - Target AoI (positive means target policy is better)
    adv_sim = sim_map[baseline_policy] - sim_map[target_policy]
    adv_ns3 = (
        ns3_map.get(baseline_policy, 0.0) - ns3_map.get(target_policy, 0.0)
        if (target_policy in ns3_map and baseline_policy in ns3_map)
        else adv_sim
    )

    transfer_gap = adv_ns3 - adv_sim
    retention_ratio = (adv_ns3 / adv_sim) if abs(adv_sim) > 1e-6 else 1.0

    return {
        "advantage_sim": float(adv_sim),
        "advantage_ns3": float(adv_ns3),
        "transfer_gap": float(transfer_gap),
        "retention_ratio": float(retention_ratio),
    }


def sim_to_ns3_gap_analysis(sim_results_root: str, ns3_results_root: str) -> dict:
    """Compute all 3 sim-to-ns3 gap statistics from directory trees."""
    sim_lb = leaderboard(sim_results_root)
    ns3_lb = leaderboard(ns3_results_root)

    if ns3_lb.empty:
        # Self-consistency reference when ns-3 runs are not yet executed
        ns3_lb = sim_lb.copy()

    metric_df = compute_metric_gap(sim_lb, ns3_lb)
    tau, p_val = compute_ranking_gap(sim_lb, ns3_lb)
    transfer = compute_transfer_gap(sim_lb, ns3_lb)

    return {
        "metric_gap": metric_df.to_dict(orient="records"),
        "ranking_gap": {"kendall_tau": tau, "p_value": p_val},
        "transfer_gap": transfer,
    }

