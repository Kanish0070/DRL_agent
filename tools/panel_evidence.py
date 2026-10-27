"""Panel evidence: which DQN gains over each baseline are significant, robust and practically meaningful.

Reads <results_root>/summary/per_run_metrics.csv (from tools/ns3_summarize.py) and writes
<results_root>/summary/panel_evidence.csv with one row per scenario x metric x baseline.

A row `passes` only if all three hold (rules fixed in advance, see docs/PANEL_EVIDENCE.md):
  statistical  paired over eval seeds: p_holm < 0.05, 95% bootstrap CI excludes 0, DQN wins >= 75% of seeds
  robust       the statistical test holds for BOTH the pooled 5-seed DQN and the deployed seed
  practical    pooled gain >= 10% relative AND >= 50 ms of age / 2 percentage points of time / 0.02 Jain

The deployed seed is the DQN training seed with the lowest mean cw_aoi on S0 (nominal); no other scenario
is used to choose it.

Usage:  python3 tools/panel_evidence.py --results-root results/ns3_campaign
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ns3_summarize import BASELINES, bootstrap_ci, holm  # noqa: E402

# metric -> (kind, higher_is_better); kind sets the unit and the practical-significance floor
METRICS = {
    "cw_aoi": ("age", False),
    "cw_aoi_p95": ("age", False),
    "cw_aoi_p99": ("age", False),
    "aoi_mean_n3": ("age", False),
    "aoi_mean_n4": ("age", False),
    "aoi_p99_urgent": ("age", False),
    "aoi_p99_n3": ("age", False),
    "soft_exc_urgent": ("rate", False),
    "soft_exc_important": ("rate", False),
    "soft_exc_routine": ("rate", False),
    "jain_norm_aoi": ("index", True),
}
ABS_FLOOR = {"age": 0.05, "rate": 0.02, "index": 0.02}
REL_FLOOR, ALPHA, WIN_FRAC = 0.10, 0.05, 0.75


def paired(dqn, base):
    """Improvement = base - dqn for lower-is-better metrics; sign flipped by the caller otherwise."""
    common = dqn.index.intersection(base.index)
    return dqn.loc[common].to_numpy(), base.loc[common].to_numpy()


def compare(a, c, hib):
    gain = (a - c) if hib else (c - a)           # positive = DQN better
    p = stats.ttest_rel(a, c).pvalue if gain.std(ddof=1) > 0 else 1.0
    lo, hi = bootstrap_ci(gain)
    return dict(dqn=a.mean(), base=c.mean(), gain=gain.mean(), gain_pct=100 * gain.mean() / abs(c.mean()),
                ci_lo=lo, ci_hi=hi, wins=int((gain > 0).sum()), n=len(gain), p=p)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results-root", required=True)
    args = ap.parse_args()
    out = Path(args.results_root) / "summary"
    runs = pd.read_csv(out / "per_run_metrics.csv")

    s0 = runs[(runs.scenario == "S0") & (runs.family == "dqn")].groupby("dqn_seed")["cw_aoi"].mean()
    deployed = int(s0.idxmin())
    print(f"deployed DQN training seed (best on S0): {deployed}  S0 cw_aoi by seed: {s0.round(4).to_dict()}")

    rows = []
    for sc, g in runs.groupby("scenario"):
        for metric, (kind, hib) in METRICS.items():
            pooled = g[g.family == "dqn"].groupby("eval_seed")[metric].mean()
            dep = g[g.policy_dir == f"dqn_seed{deployed}"].set_index("eval_seed")[metric]
            for b in BASELINES:
                base = g[g.family == b].set_index("eval_seed")[metric]
                if base.empty:
                    continue
                rp = compare(*paired(pooled, base), hib)
                rd = compare(*paired(dep, base), hib)
                rows.append(dict(scenario=sc, metric=metric, kind=kind, baseline=b,
                                 **{f"pool_{k}": v for k, v in rp.items()},
                                 **{f"dep_{k}": v for k, v in rd.items()}))
    df = pd.DataFrame(rows)
    for v in ("pool", "dep"):
        df[f"{v}_p_holm"] = holm(df[f"{v}_p"])            # one family across all scenario x metric x baseline
    df["stat_pool"] = (df.pool_p_holm < ALPHA) & (df.pool_ci_lo > 0) & (df.pool_wins >= WIN_FRAC * df.pool_n)
    df["stat_dep"] = (df.dep_p_holm < ALPHA) & (df.dep_ci_lo > 0) & (df.dep_wins >= WIN_FRAC * df.dep_n)
    df["practical"] = (df.pool_gain_pct >= 100 * REL_FLOOR) & (df.pool_gain >= df.kind.map(ABS_FLOOR))
    df["passes"] = df.stat_pool & df.stat_dep & df.practical
    # significant losses (DQN worse), same statistical bar, for the costs section
    df["sig_loss"] = (df.pool_p_holm < ALPHA) & (df.pool_ci_hi < 0) & (df.pool_wins <= (1 - WIN_FRAC) * df.pool_n)
    df["deployed_seed"] = deployed
    df["minutes_per_hour"] = np.where(df.kind == "rate", df.pool_gain * 60, np.nan)
    df.to_csv(out / "panel_evidence.csv", index=False, float_format="%.6g")

    cols = ["scenario", "metric", "baseline", "pool_dqn", "pool_base", "pool_gain", "pool_gain_pct",
            "pool_ci_lo", "pool_ci_hi", "pool_wins", "dep_gain_pct", "dep_wins", "pool_p_holm"]
    pd.set_option("display.width", 250, "display.max_columns", 30, "display.float_format", "{:.4g}".format)
    print(f"\n{int(df.passes.sum())} of {len(df)} comparisons pass all tests")
    strong = df[df.baseline.isin(["maxweight", "cag"])]
    print("\n== PASS vs Max-Weight / CAG ==")
    print(strong[strong.passes].sort_values("pool_gain_pct", ascending=False)[cols].to_string(index=False))
    print("\n== PASS vs RR / Random / FPQ (top 15 by %) ==")
    weak = df[df.baseline.isin(["rr", "random", "fpq"]) & df.passes]
    print(weak.sort_values("pool_gain_pct", ascending=False)[cols].head(15).to_string(index=False))
    print("\n== SIGNIFICANT LOSSES vs Max-Weight / CAG / RR on pre-registered metrics ==")
    print(df[df.sig_loss & df.baseline.isin(["maxweight", "cag", "rr"])].sort_values("pool_gain_pct")[cols].head(25).to_string(index=False))


if __name__ == "__main__":
    main()
