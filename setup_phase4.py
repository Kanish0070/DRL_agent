import re

filepath = "eval/run.py"
with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

# Add arguments
if "--r50" not in content:
    args_replacement = """    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--out-dir", default="results")
    parser.add_argument("--distances", type=float, nargs=4, help="Override node distances")
    parser.add_argument("--r50", type=float, help="Override logistic_r50_dbm")
    parser.add_argument("--slope", type=float, help="Override logistic_slope_db")
    parser.add_argument("--burst", type=float, help="Override ge_prob_good_to_bad")
    parser.add_argument("--arrival", type=float, help="Override arrival_prob")
"""
    content = content.replace('    parser.add_argument("--seed", type=int, required=True)\n    parser.add_argument("--out-dir", default="results")', args_replacement)

# Apply overrides to measured_params and pass distances and arrival
if "if args.r50 is not None:" not in content:
    override_logic = """
    if args.r50 is not None:
        meas_cfg["channel"]["logistic_r50_dbm"] = args.r50
    if args.slope is not None:
        meas_cfg["channel"]["logistic_slope_db"] = args.slope
    if args.burst is not None:
        meas_cfg["channel"]["ge_prob_good_to_bad"] = args.burst
        
    arr_prob = args.arrival if args.arrival is not None else 1.0
    sim_config = SimConfig.from_configs(sys_cfg, meas_cfg, episode_length=ep_len, arrival_prob=arr_prob)
    
    if args.distances is not None:
        sim = NetworkSim(sim_config, distances_m=args.distances)
    else:
        sim = NetworkSim(sim_config)
"""
    content = re.sub(r"    sim_config = SimConfig\.from_configs\(.*?episode_length=ep_len\)\n    sim = NetworkSim\(sim_config\)", override_logic, content, flags=re.DOTALL)
    
with open(filepath, "w", encoding="utf-8") as f:
    f.write(content)
print("Updated eval/run.py for Phase 4 overrides")
