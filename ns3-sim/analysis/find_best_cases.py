#!/usr/bin/env python3
"""Find where the DQN does best against the baselines in the measured ns-3 campaign.

Reads results/ns3_campaign/summary/*.csv (no re-simulation) and writes best_cases.{json,csv,md} next to them.
The dashboard's Evidence tab reads best_cases.json. Selected cases are cherry-picked by construction, so every
output carries the full distribution (win rate, mean difference) beside them.
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
POL_NAME = {"dqn": "DQN (+shield)", "maxweight": "Max-Weight", "cag": "Channel-Aware Greedy",
            "rr": "Round Robin", "random": "Random", "fpq": "Fixed Priority"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--summary-dir", default=str(ROOT / "results" / "ns3_campaign" / "summary"))
    ap.add_argument("--top", type=int, default=5)
    a = ap.parse_args()
    sd = Path(a.summary_dir)
    runs = pd.read_csv(sd / "per_run_metrics.csv")
    by_sc = pd.read_csv(sd / "summary_by_scenario.csv")
    paired = pd.read_csv(sd / "paired_tests.csv")
    spread = pd.read_csv(sd / "dqn_seed_spread.csv")

    runs["urgent_max"] = runs[["aoi_max_n1", "aoi_max_n2"]].max(axis=1)
    key = ["scenario", "eval_seed"]

    # ---- per-run pairs: each single-seed DQN run vs each baseline family on the same (scenario, eval seed)
    dq = runs[runs.family == "dqn"].copy()
    rows = []
    for fam in ["rr", "random", "fpq", "maxweight", "cag"]:
        b = runs[runs.family == fam].set_index(key)
        m = dq.join(b[["cw_aoi", "cw_aoi_p95", "urgent_max"]].add_prefix("b_"), on=key)
        m["baseline"] = fam
        m["rel_cw_pct"] = (m.cw_aoi - m.b_cw_aoi) / m.b_cw_aoi * 100
        m["rel_p95_pct"] = (m.cw_aoi_p95 - m.b_cw_aoi_p95) / m.b_cw_aoi_p95 * 100
        m["rel_urgent_max_pct"] = (m.urgent_max - m.b_urgent_max) / m.b_urgent_max * 100
        rows.append(m[["scenario", "eval_seed", "dqn_seed", "baseline", "cw_aoi", "b_cw_aoi",
                       "rel_cw_pct", "rel_p95_pct", "rel_urgent_max_pct"]])
    pairs = pd.concat(rows).sort_values("rel_cw_pct")
    pairs.to_csv(sd / "best_cases.csv", index=False)

    # ---- DQN vs the better of Max-Weight / CAG (the strongest heuristics) per run
    heur = runs[runs.family.isin(["maxweight", "cag"])]
    best_h = heur.loc[heur.groupby(key).cw_aoi.idxmin(), key + ["family", "cw_aoi"]].rename(
        columns={"family": "best_heuristic", "cw_aoi": "best_heur_cw"}).set_index(key)
    vs = dq.join(best_h, on=key)
    vs["rel_pct"] = (vs.cw_aoi - vs.best_heur_cw) / vs.best_heur_cw * 100
    top = vs.sort_values("rel_pct").head(a.top)
    selected = [{
        "id": f"{r.scenario}_dqn{int(r.dqn_seed)}_seed{int(r.eval_seed)}",
        "scenario": r.scenario, "dqn_seed": int(r.dqn_seed), "eval_seed": int(r.eval_seed),
        "best_heuristic": r.best_heuristic, "dqn_cw_aoi": round(r.cw_aoi, 4),
        "heuristic_cw_aoi": round(r.best_heur_cw, 4), "rel_pct": round(r.rel_pct, 2)}
        for r in top.itertuples()]

    win = {
        "n_runs": int(len(vs)),
        "n_wins": int((vs.rel_pct < 0).sum()),
        "n_wins_over_3pct": int((vs.rel_pct < -3).sum()),
        "mean_rel_pct": round(float(vs.rel_pct.mean()), 2),
        "by_dqn_seed": {int(s): {"mean_rel_pct": round(float(g.rel_pct.mean()), 2),
                                 "wins": int((g.rel_pct < 0).sum()), "n": int(len(g))}
                        for s, g in vs.groupby("dqn_seed")},
    }

    tail = (runs[runs.family.isin(["dqn", "maxweight", "cag", "rr"])]
            .groupby(["scenario", "family"]).agg(urgent_max=("urgent_max", "mean"),
                                                 cw_p95=("cw_aoi_p95", "mean")).round(3).reset_index())

    out = {
        "provenance": "Measured ns-3.48 campaign: 5 scenarios x 10 policies x 20 eval seeds (results/ns3_campaign). "
                      "Selected cases are the best of 500 DQN runs and are NOT representative of the average.",
        "policies": POL_NAME,
        "by_scenario": by_sc.to_dict("records"),
        "paired": paired[["scenario", "baseline", "rel_diff_pct", "t_p_holm", "dqn_better", "significant_holm"]].to_dict("records"),
        "seed_spread": spread.to_dict("records"),
        "win_stats_vs_best_heuristic": win,
        "selected_cases": selected,
        "tail_safety": tail.to_dict("records"),
    }
    (sd / "best_cases.json").write_text(json.dumps(out, indent=1))

    # ---- markdown
    big = paired[paired.baseline.isin(["rr", "random", "fpq"]) & (paired.scenario != "S4")]
    L = ["# Where the DQN does best (measured ns-3 campaign)", "",
         "## Headline: large, consistent wins over the non-AoI-aware baselines (S0-S3, mean of 20 paired eval seeds)", "",
         "| scenario | vs Round Robin | vs Random | vs Fixed Priority |", "|---|---|---|---|"]
    for sc, g in big.groupby("scenario"):
        v = g.set_index("baseline").rel_diff_pct
        L.append(f"| {sc} | {v['rr']:+.1f}% | {v['random']:+.1f}% | {v['fpq']:+.1f}% |")
    L += ["", "(negative = DQN has lower criticality-weighted AoI)", "",
          "## Honest comparison with the strongest heuristics (Max-Weight, CAG)", "",
          f"Across {win['n_runs']} single-seed DQN runs, DQN beats the better of Max-Weight/CAG in {win['n_wins']} "
          f"({win['n_wins_over_3pct']} by more than 3%); mean difference {win['mean_rel_pct']:+.1f}%. "
          "On average it is worse than the better heuristic (pooled mean above); only DQN seed 1 is near parity, and seeds 0 and 4 are about 10% worse. "
          "It does reduce worst-case urgent AoI in S1 and S3 (tail table below), though Round Robin is lowest there.", "",
          "| DQN training seed | mean vs best heuristic | wins |", "|---|---|---|"]
    for s, d in win["by_dqn_seed"].items():
        L.append(f"| {s} | {d['mean_rel_pct']:+.1f}% | {d['wins']}/{d['n']} |")
    L += ["", f"## Best {len(selected)} single runs vs the better of Max-Weight/CAG (selected cases, not averages)", "",
          "| case | DQN cw-AoI | heuristic | heuristic cw-AoI | difference |", "|---|---|---|---|---|"]
    for c in selected:
        L.append(f"| {c['id']} | {c['dqn_cw_aoi']} | {c['best_heuristic']} | {c['heuristic_cw_aoi']} | {c['rel_pct']:+.1f}% |")
    L += ["", "## Tail safety (mean over 20 eval seeds of the worst urgent-node AoI, seconds)", "",
          "| scenario | DQN | Max-Weight | CAG | Round Robin |", "|---|---|---|---|---|"]
    for sc, g in tail.groupby("scenario"):
        v = g.set_index("family").urgent_max
        L.append(f"| {sc} | {v['dqn']:.2f} | {v['maxweight']:.2f} | {v['cag']:.2f} | {v['rr']:.2f} |")
    (sd / "best_cases.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
