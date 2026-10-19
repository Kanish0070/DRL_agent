import os
import json
import numpy as np
import pandas as pd
from pathlib import Path
from scipy import stats
from eval.stats import criticality_weighted_mean_aoi_per_run

def main():
    res_dir = Path("sensitivity_results")
    if not res_dir.exists():
        print("No sensitivity results found.")
        return

    with open(res_dir / "grid_meta.json", "r") as f:
        grid_meta = json.load(f)

    results = []
    
    # Iterate through cells
    for cell_id, params in grid_meta.items():
        cell_dir = res_dir / cell_id
        if not cell_dir.exists():
            continue
            
        # Group by policy
        policy_scores = {}
        for run_dir in cell_dir.iterdir():
            if not run_dir.is_dir():
                continue
            csv_path = run_dir / "log.csv"
            if not csv_path.exists():
                continue
                
            cw_aoi = criticality_weighted_mean_aoi_per_run(str(csv_path))
            
            # Extract policy name (e.g. maxweight, dqn_t0)
            parts = run_dir.name.rsplit("_seed", 1)
            policy = parts[0]
            
            # We will aggregate all dqn_t* into 'dqn'
            if policy.startswith("dqn_t"):
                policy = "dqn"
                
            if policy not in policy_scores:
                policy_scores[policy] = []
            policy_scores[policy].append(cw_aoi)
            
        if "maxweight" not in policy_scores or "dqn" not in policy_scores:
            continue
            
        mw_mean = np.mean(policy_scores["maxweight"])
        dqn_mean = np.mean(policy_scores["dqn"])
        cag_mean = np.mean(policy_scores.get("cag", [0]))
        
        diff = dqn_mean - mw_mean
        
        # t-test between DQN and MaxWeight
        # DQN is better if diff < 0 (lower AoI is better)
        t_stat, p_val = stats.ttest_ind(policy_scores["dqn"], policy_scores["maxweight"], equal_var=False)
        
        # Equivalence margin: say 5% of maxweight mean
        margin = 0.05 * mw_mean
        
        if diff < -margin and p_val < 0.05:
            outcome = "DQN Wins"
        elif diff > margin and p_val < 0.05:
            outcome = "MaxWeight Wins"
        else:
            outcome = "Tie"
            
        row = {
            "cell": cell_id,
            "r50": params["r50"],
            "slope": params["slope"],
            "dist_type": "Steep" if params["distances"][0] == 30.0 else "Easy",
            "burst": params["burst"],
            "arrival": params["arrival"],
            "mw_aoi": mw_mean,
            "dqn_aoi": dqn_mean,
            "cag_aoi": cag_mean,
            "diff": diff,
            "p_val": p_val,
            "outcome": outcome
        }
        results.append(row)

    if not results:
        print("No valid results parsed.")
        return

    df = pd.DataFrame(results)
    df.to_csv("sensitivity_results/summary.csv", index=False)
    
    print("\n--- Sensitivity Sweep Summary ---")
    print(df["outcome"].value_counts())
    print("\nDetailed summary saved to sensitivity_results/summary.csv")

if __name__ == "__main__":
    main()
