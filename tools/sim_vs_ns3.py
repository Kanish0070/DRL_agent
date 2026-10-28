"""Sim-to-ns3 gap analysis: compare the Python simulator's evaluation logs with the NS-3 campaign.

Inputs
  results/<policy>_seed<N>/log.csv            Python-sim runs (eval seeds 100-119, 1000 slots)
  results/ns3_campaign/summary/per_run_metrics.csv   NS-3 runs (5 scenarios x 10 policies x 20 seeds, 3000 slots)

Outputs (results/sim_vs_ns3/)
  policy_comparison.csv   per-policy mean criticality-weighted AoI in each simulator and the gap
  rank_agreement.csv      Kendall tau between the Python ranking and each NS-3 scenario's ranking
  dqn_outcomes.csv        paired DQN vs CAG / Max-Weight / RR outcome in each simulator and scenario
  sim_vs_ns3.md           paste-ready tables

Usage: python3 tools/sim_vs_ns3.py
Caveats are written into sim_vs_ns3.md and must be quoted with the numbers.
"""
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from common.config import load_system_config

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "results" / "sim_vs_ns3"
PY_POLICIES = ["rr", "fpq", "random", "maxweight", "cag", "oracle", "dqn"]
COMMON = ["rr", "fpq", "random", "maxweight", "cag", "dqn"]   # oracle exists only in the Python sim


def python_runs():
    cfg = load_system_config()
    w = np.array([cfg["scheduler"]["weights"][c] for c in cfg["system"]["node_classes"]], float)
    rows = []
    for d in sorted((ROOT / "results").glob("*_seed1[0-9][0-9]")):
        pol, seed = d.name.rsplit("_seed", 1)
        if pol not in PY_POLICIES or not (d / "log.csv").exists():
            continue
        df = pd.read_csv(d / "log.csv")
        a = df[["aoi_n1", "aoi_n2", "aoi_n3", "aoi_n4"]].to_numpy()
        meta = json.loads((d / "run_meta.json").read_text()) if (d / "run_meta.json").exists() else {}
        rows.append(dict(policy=pol, eval_seed=int(seed), cw_aoi=((a * w).sum(1) / w.sum()).mean(),
                         wasted=1 - df["uplink_received"].mean(), slots=len(df),
                         git_sha=meta.get("git_sha", "")[:7], params_source=meta.get("params_source", "")))
    return pd.DataFrame(rows)


def boot(v, n=4000):
    rng = np.random.default_rng(0)
    v = np.asarray(v, float)
    b = rng.choice(v, size=(n, len(v)), replace=True).mean(axis=1)
    return float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5))


def paired(a, b):
    """a, b: Series indexed by eval_seed. Returns (rel_diff_pct of a vs b, t p-value)."""
    idx = a.index.intersection(b.index)
    x, y = a.loc[idx].to_numpy(), b.loc[idx].to_numpy()
    return 100 * (x - y).mean() / y.mean(), stats.ttest_rel(x, y).pvalue, len(idx)


def md(df, fmt="{:.4f}"):
    cols = [str(c) for c in df.columns]
    out = ["| " + " | ".join(cols) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
    for _, r in df.iterrows():
        out.append("| " + " | ".join(fmt.format(v) if isinstance(v, (float, np.floating)) else str(v) for v in r) + " |")
    return "\n".join(out)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    py = python_runs()
    ns = pd.read_csv(ROOT / "results/ns3_campaign/summary/per_run_metrics.csv")
    ns["policy"] = ns["family"]

    # ---- per-policy comparison ----
    rows = []
    for pol in PY_POLICIES:
        g = py[py.policy == pol]
        lo, hi = boot(g.cw_aoi)
        row = dict(policy=pol, py_cw=g.cw_aoi.mean(), py_lo=lo, py_hi=hi, py_wasted_pct=100 * g.wasted.mean())
        for sc in sorted(ns.scenario.unique()):
            gs = ns[(ns.scenario == sc) & (ns.policy == pol)]
            row[f"ns3_{sc}"] = gs.cw_aoi.mean() if len(gs) else np.nan
        rows.append(row)
    comp = pd.DataFrame(rows)
    comp.to_csv(OUT / "policy_comparison.csv", index=False, float_format="%.6g")

    # ---- rank agreement ----
    rk = []
    py_rank = comp.set_index("policy").loc[COMMON, "py_cw"]
    for sc in sorted(ns.scenario.unique()):
        n_rank = comp.set_index("policy").loc[COMMON, f"ns3_{sc}"]
        tau, p = stats.kendalltau(py_rank, n_rank)
        rk.append(dict(scenario=sc, kendall_tau=tau, p_value=p, n_policies=len(COMMON),
                       python_order=" < ".join(py_rank.sort_values().index),
                       ns3_order=" < ".join(n_rank.sort_values().index)))
    rk = pd.DataFrame(rk)
    rk.to_csv(OUT / "rank_agreement.csv", index=False, float_format="%.6g")

    # ---- DQN outcomes (paired by eval seed) ----
    outs = []
    pyd = py[py.policy == "dqn"].set_index("eval_seed").cw_aoi
    for base in ["cag", "maxweight", "rr", "random", "fpq"]:
        rel, p, n = paired(pyd, py[py.policy == base].set_index("eval_seed").cw_aoi)
        outs.append(dict(simulator="python", scenario="-", baseline=base, dqn_rel_diff_pct=rel, t_p=p, n_pairs=n))
    for sc in sorted(ns.scenario.unique()):
        g = ns[ns.scenario == sc]
        dq = g[g.policy == "dqn"].groupby("eval_seed").cw_aoi.mean()
        for base in ["cag", "maxweight", "rr", "random", "fpq"]:
            rel, p, n = paired(dq, g[g.policy == base].set_index("eval_seed").cw_aoi)
            outs.append(dict(simulator="ns3", scenario=sc, baseline=base, dqn_rel_diff_pct=rel, t_p=p, n_pairs=n))
    outs = pd.DataFrame(outs)
    outs.to_csv(OUT / "dqn_outcomes.csv", index=False, float_format="%.6g")

    # ---- markdown ----
    meta = py.groupby("policy").agg(git_sha=("git_sha", "first"), params=("params_source", "first"),
                                    slots=("slots", "first"), n=("eval_seed", "size")).reset_index()
    text = ["# Sim-to-ns3 gap", "",
            "Python simulator vs NS-3 evaluation of the same policies (criticality-weighted mean AoI, seconds, lower is better).",
            "NS-3 S0 is the nominal scenario; S1-S4 are stress scenarios (see `results/ns3_campaign/README.md`).", "",
            "## Per-policy means", "", md(comp), "",
            "## Rank agreement (Kendall tau over rr, fpq, random, maxweight, cag, dqn)", "", md(rk), "",
            "## DQN vs baseline, paired by eval seed (negative = DQN has lower AoI)", "", md(outs, "{:.4g}"), "",
            "## Caveats (quote these with the numbers)", "",
            "- The Python runs are 1000 slots (100 s); NS-3 runs are 3000 slots (300 s). Absolute AoI values are not comparable; compare rankings and relative differences.",
            "- Loss regimes differ: Python wasted-slot rate is about 25% (placeholder channel parameters), NS-3 S0 is about 6%.",
            "- The Python logs were produced on placeholder parameters (`params_source=placeholder_pending_p1`) from the commits listed below, with a dirty working tree.",
            "- The Python `dqn` runs carry only `policy_id=dqn`; which of the 5 training seeds produced them is not recorded. NS-3 pools all 5 training seeds.",
            "- The Python simulator includes an `oracle` policy that NS-3 does not; it is excluded from the rank comparison.",
            "- All numbers are simulation results; none come from hardware.", "",
            "## Python run provenance", "", md(meta, "{}"), ""]
    (OUT / "sim_vs_ns3.md").write_text("\n".join(text))
    print("\n".join(text))


if __name__ == "__main__":
    main()
