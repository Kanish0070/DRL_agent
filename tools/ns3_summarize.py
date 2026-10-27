"""Aggregate an NS-3 evaluation campaign (scenarios S0-S4) into report-ready tables and figures.

Input layout (written by ns3-sim/scripts/run_campaign.sh):
    <results_root>/<scenario>/<policy>/seed<N>/log.csv

Outputs (under <results_root>/summary/):
    per_run_metrics.csv   one row per run
    summary_by_scenario.csv, paired_tests.csv, fault_recovery.csv
    figures/*.png
    summary.md            tables in Markdown, ready to paste into the report

Usage:  python3 tools/ns3_summarize.py --results-root results/ns3_campaign
"""
import argparse
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

from common.config import load_system_config

BASELINES = ["rr", "fpq", "random", "maxweight", "cag"]
LABEL = {"rr": "Round Robin", "fpq": "Fixed Priority", "random": "Random",
         "maxweight": "Max-Weight", "cag": "Channel-Aware Greedy", "dqn": "DQN (+shield)"}
SCENARIO_NAME = {"S0": "Nominal", "S1": "Weak links", "S2": "Co-channel interferer",
                 "S3": "Mobility (STA-4 walks out)", "S4": "Fault (STA-2 down 60-90 s)",
                 "S5": "Training-regime loss (-7 dBm)"}
FAULT_NODE, FAULT_START, FAULT_END = 1, 60.0, 90.0   # S4, matches run_campaign.sh


def load_cfg():
    cfg = load_system_config()
    classes = cfg["system"]["node_classes"]
    w = np.array([cfg["scheduler"]["weights"][c] for c in classes], float)
    ceil = np.array([cfg["scheduler"]["shield_ceilings_s"][c] for c in classes], float)
    tau = np.array([cfg["scheduler"]["thresholds"][c] for c in classes], float) / 1000.0
    return w, ceil, tau


def longest_run(mask):
    """Length (in samples) of the longest contiguous True stretch."""
    best = cur = 0
    for v in mask:
        cur = cur + 1 if v else 0
        best = max(best, cur)
    return best


def run_metrics(csv_path, w, ceil, tau=None):
    df = pd.read_csv(csv_path)
    aoi = df[["aoi_n1", "aoi_n2", "aoi_n3", "aoi_n4"]].to_numpy()
    cw = (aoi * w).sum(axis=1) / w.sum()
    m = {
        "cw_aoi": cw.mean(),
        "cw_aoi_p95": np.percentile(cw, 95),
        "wasted_rate": 1.0 - df["uplink_received"].mean(),
        "shield_rate": df["shield_fired"].mean(),
        "slots": len(df),
    }
    for i in range(4):
        m[f"aoi_mean_n{i+1}"] = aoi[:, i].mean()
        m[f"aoi_max_n{i+1}"] = aoi[:, i].max()
        m[f"viol_n{i+1}"] = (aoi[:, i] >= ceil[i]).mean()
    m["urgent_viol"] = max(m["viol_n1"], m["viol_n2"])
    if tau is not None:
        # pre-registered metrics (docs/EVAL_PROTOCOL.md): soft-deadline exceedance, tail AoI, fairness.
        slot_s = float(np.median(np.diff(df["timestamp_pi"].to_numpy())))
        m["cw_aoi_p99"] = np.percentile(cw, 99)
        for i in range(4):
            over = aoi[:, i] > tau[i]
            m[f"soft_exc_n{i+1}"] = over.mean()
            m[f"aoi_p95_n{i+1}"] = np.percentile(aoi[:, i], 95)
            m[f"aoi_p99_n{i+1}"] = np.percentile(aoi[:, i], 99)
            m[f"stale_run_max_n{i+1}"] = longest_run(over) * slot_s
        m["soft_exc_urgent"] = (m["soft_exc_n1"] + m["soft_exc_n2"]) / 2
        m["soft_exc_important"] = m["soft_exc_n3"]
        m["soft_exc_routine"] = m["soft_exc_n4"]
        urgent_age = np.maximum(aoi[:, 0], aoi[:, 1])
        m["aoi_p99_urgent"] = np.percentile(urgent_age, 99)
        x = aoi.mean(axis=0) / tau
        m["jain_norm_aoi"] = x.sum() ** 2 / (len(x) * (x ** 2).sum())
    return m, df


def bootstrap_ci(vals, n=4000, seed=0):
    rng = np.random.default_rng(seed)
    v = np.asarray(vals, float)
    boots = rng.choice(v, size=(n, len(v)), replace=True).mean(axis=1)
    return float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))


def holm(pvals):
    p = np.asarray(pvals, float)
    order = np.argsort(p)
    adj = np.empty_like(p)
    running = 0.0
    for rank, idx in enumerate(order):
        running = max(running, (len(p) - rank) * p[idx])
        adj[idx] = min(1.0, running)
    return adj


def fault_recovery(df):
    """Seconds from fault clearing until STA-2's first successful delivery; peak AoI of others in-window."""
    t = df["timestamp_pi"].to_numpy()
    after = df[(t >= FAULT_END) & (df["delivered_node"] == FAULT_NODE)]
    rec = float(after["timestamp_pi"].iloc[0] - FAULT_END) if len(after) else np.nan
    win = df[(t >= FAULT_START) & (t < FAULT_END)]
    others = win[["aoi_n1", "aoi_n3", "aoi_n4"]]
    granted_dead = (win["action_granted_node"] == FAULT_NODE).mean()
    return rec, float(others.max().max()), float(granted_dead)


def md_table(df, floatfmt="{:.3f}"):
    cols = [str(c) for c in df.columns]
    out = ["| " + " | ".join(cols) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
    for _, r in df.iterrows():
        out.append("| " + " | ".join(floatfmt.format(v) if isinstance(v, (float, np.floating)) else str(v)
                                      for v in r) + " |")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results-root", required=True)
    args = ap.parse_args()
    root = Path(args.results_root)
    out = root / "summary"
    (out / "figures").mkdir(parents=True, exist_ok=True)
    w, ceil, tau = load_cfg()

    rows, fault_rows = [], []
    for csv in sorted(root.glob("S*/*/seed*/log.csv")):
        sc, pol, seed_dir = csv.parts[-4], csv.parts[-3], csv.parts[-2]
        seed = int(re.sub(r"\D", "", seed_dir))
        m, df = run_metrics(csv, w, ceil, tau)
        is_dqn = pol.startswith("dqn_seed")
        m.update(scenario=sc, policy_dir=pol, family="dqn" if is_dqn else pol,
                 dqn_seed=int(pol.split("seed")[-1]) if is_dqn else -1, eval_seed=seed)
        rows.append(m)
        if sc == "S4":
            rec, peak, gd = fault_recovery(df)
            fault_rows.append(dict(scenario=sc, family=m["family"], policy_dir=pol, eval_seed=seed,
                                   recovery_s=rec, others_peak_aoi_s=peak, grants_to_dead_node=gd))
    runs = pd.DataFrame(rows)
    if runs.empty:
        raise SystemExit(f"no runs found under {root}")
    runs.to_csv(out / "per_run_metrics.csv", index=False, float_format="%.6g")

    # ---- per-scenario summary (DQN pooled over its 5 training seeds) ----
    summ = []
    for sc, g in runs.groupby("scenario"):
        for fam, gf in g.groupby("family"):
            lo, hi = bootstrap_ci(gf["cw_aoi"])
            summ.append(dict(scenario=sc, policy=fam, n_runs=len(gf),
                             cw_aoi=gf["cw_aoi"].mean(), ci_lo=lo, ci_hi=hi, sd=gf["cw_aoi"].std(),
                             cw_aoi_p95=gf["cw_aoi_p95"].mean(),
                             wasted_pct=100 * gf["wasted_rate"].mean(),
                             shield_pct=100 * gf["shield_rate"].mean(),
                             urgent_viol_pct=100 * gf["urgent_viol"].mean(),
                             max_urgent_aoi=max(gf["aoi_max_n1"].max(), gf["aoi_max_n2"].max())))
    summ = pd.DataFrame(summ)
    summ["policy"] = pd.Categorical(summ["policy"], BASELINES + ["dqn"], ordered=True)
    summ = summ.sort_values(["scenario", "cw_aoi"]).reset_index(drop=True)
    summ.to_csv(out / "summary_by_scenario.csv", index=False, float_format="%.6g")

    # per-DQN-training-seed spread
    dq = runs[runs.family == "dqn"].groupby(["scenario", "dqn_seed"])["cw_aoi"].mean().unstack()
    dq.to_csv(out / "dqn_seed_spread.csv", float_format="%.6g")

    # ---- paired tests: DQN (mean over its 5 seeds, per eval seed) vs each baseline ----
    tests = []
    for sc, g in runs.groupby("scenario"):
        dqn = g[g.family == "dqn"].groupby("eval_seed")["cw_aoi"].mean()
        for b in BASELINES:
            base = g[g.family == b].set_index("eval_seed")["cw_aoi"]
            common = dqn.index.intersection(base.index)
            if len(common) < 3:
                continue
            a, c = dqn.loc[common].to_numpy(), base.loc[common].to_numpy()
            d = a - c
            t_p = stats.ttest_rel(a, c).pvalue
            try:
                w_p = stats.wilcoxon(a, c).pvalue
            except ValueError:
                w_p = 1.0
            dz = d.mean() / d.std(ddof=1) if d.std(ddof=1) > 0 else np.nan
            tests.append(dict(scenario=sc, baseline=b, n_pairs=len(common),
                              dqn_mean=a.mean(), base_mean=c.mean(),
                              diff=d.mean(), rel_diff_pct=100 * d.mean() / c.mean(),
                              t_p=t_p, wilcoxon_p=w_p, cohens_dz=dz))
    tests = pd.DataFrame(tests)
    tests["t_p_holm"] = holm(tests["t_p"])
    tests["dqn_better"] = tests["diff"] < 0
    tests["significant_holm"] = tests["t_p_holm"] < 0.05
    tests.to_csv(out / "paired_tests.csv", index=False, float_format="%.6g")

    # ---- fault recovery ----
    fr = pd.DataFrame(fault_rows)
    if not fr.empty:
        fr_s = fr.groupby("family").agg(recovery_s=("recovery_s", "mean"),
                                        recovery_max_s=("recovery_s", "max"),
                                        others_peak_aoi_s=("others_peak_aoi_s", "mean"),
                                        grants_to_dead_node_pct=("grants_to_dead_node", lambda x: 100 * x.mean()))
        fr_s.to_csv(out / "fault_recovery.csv", float_format="%.6g")

    # ---- figures ----
    order = BASELINES + ["dqn"]
    scs = sorted(runs.scenario.unique())
    fig, axes = plt.subplots(1, len(scs), figsize=(3.6 * len(scs), 4), sharey=False)
    axes = np.atleast_1d(axes)
    for ax, sc in zip(axes, scs):
        s = summ[summ.scenario == sc].set_index("policy").reindex(order)
        x = np.arange(len(order))
        ax.bar(x, s["cw_aoi"], yerr=[s["cw_aoi"] - s["ci_lo"], s["ci_hi"] - s["cw_aoi"]], capsize=3,
               color=["#94a3b8"] * 5 + ["#10b981"])
        ax.set_xticks(x)
        ax.set_xticklabels([LABEL[o].split(" ")[0] if o != "dqn" else "DQN" for o in order], rotation=45, ha="right")
        ax.set_title(f"{sc}: {SCENARIO_NAME.get(sc, '')}", fontsize=9)
    axes[0].set_ylabel("criticality-weighted mean AoI (s)")
    fig.suptitle("NS-3 evaluation: mean AoI per scenario (95% bootstrap CI over eval seeds)")
    fig.tight_layout()
    fig.savefig(out / "figures" / "cw_aoi_by_scenario.png", dpi=160)
    plt.close(fig)

    # S4 AoI trace for STA-2 and an other node, representative seed (first eval seed)
    first_seed = int(runs.eval_seed.min())
    fig, axes = plt.subplots(2, 1, figsize=(9, 6), sharex=True)
    for fam, col in [("rr", "#94a3b8"), ("maxweight", "#f59e0b"), ("cag", "#3b82f6"), ("dqn_seed0", "#10b981")]:
        p = root / "S4" / fam / f"seed{first_seed}" / "log.csv"
        if not p.exists():
            continue
        d = pd.read_csv(p)
        lab = "DQN (seed0)" if fam == "dqn_seed0" else LABEL[fam]
        axes[0].plot(d.timestamp_pi, d.aoi_n2, color=col, lw=1, label=lab)
        axes[1].plot(d.timestamp_pi, d.aoi_n1, color=col, lw=1, label=lab)
    for ax, t in zip(axes, ["STA-2 (failed 60-90 s)", "STA-1 (urgent, healthy)"]):
        ax.axvspan(FAULT_START, FAULT_END, color="red", alpha=0.08)
        ax.set_ylabel("AoI (s)")
        ax.set_title(t, fontsize=9)
    axes[0].legend(fontsize=8)
    axes[1].set_xlabel("time (s)")
    axes[1].set_xlim(50, 105)
    fig.tight_layout()
    fig.savefig(out / "figures" / "s4_fault_trace.png", dpi=160)
    plt.close(fig)

    # S3 mobility: STA-4 RSSI and AoI
    p_cag = root / "S3" / "cag" / f"seed{first_seed}" / "log.csv"
    p_dqn = root / "S3" / "dqn_seed0" / f"seed{first_seed}" / "log.csv"
    if p_cag.exists() and p_dqn.exists():
        fig, ax = plt.subplots(2, 1, figsize=(9, 5), sharex=True)
        for p, lab, col in [(p_cag, "CAG", "#3b82f6"), (p_dqn, "DQN (seed0)", "#10b981")]:
            d = pd.read_csv(p)
            ax[0].plot(d.timestamp_pi, d.aoi_n4, color=col, lw=1, label=lab)
        d = pd.read_csv(p_dqn)
        ax[1].plot(d.timestamp_pi, d.rssi_n4, color="#6b7280", lw=1)
        ax[0].set_ylabel("STA-4 AoI (s)"); ax[0].legend(fontsize=8)
        ax[1].set_ylabel("STA-4 RSSI (dBm)"); ax[1].set_xlabel("time (s)")
        fig.tight_layout()
        fig.savefig(out / "figures" / "s3_mobility_trace.png", dpi=160)
        plt.close(fig)

    # ---- markdown ----
    md = ["# NS-3 campaign summary", "",
          f"Runs: {len(runs)} ({runs.scenario.nunique()} scenarios x {runs.policy_dir.nunique()} policies "
          f"x {runs.eval_seed.nunique()} eval seeds). DQN rows pool its 5 training seeds.", ""]
    for sc in scs:
        md += [f"## {sc}: {SCENARIO_NAME.get(sc, '')}", ""]
        t = summ[summ.scenario == sc][["policy", "cw_aoi", "ci_lo", "ci_hi", "wasted_pct", "shield_pct",
                                       "urgent_viol_pct", "max_urgent_aoi"]].copy()
        t["policy"] = t["policy"].astype(str).map(lambda x: LABEL.get(x, x))
        md += [md_table(t), ""]
        tt = tests[tests.scenario == sc][["baseline", "dqn_mean", "base_mean", "rel_diff_pct", "t_p",
                                          "t_p_holm", "cohens_dz"]].copy()
        tt["baseline"] = tt["baseline"].map(LABEL)
        md += ["DQN vs baseline (paired by eval seed; negative rel_diff = DQN has lower AoI):", "", md_table(tt, "{:.4g}"), ""]
    if not fr.empty:
        md += ["## S4 fault recovery", "", md_table(fr_s.reset_index()), ""]
    md += ["## DQN spread across training seeds (mean cw-AoI)", "", md_table(dq.reset_index(), "{:.4f}"), ""]
    (out / "summary.md").write_text("\n".join(md))
    print((out / "summary.md").read_text())


if __name__ == "__main__":
    main()
