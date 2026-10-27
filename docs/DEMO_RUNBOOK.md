# Demo runbook (about 8 minutes)

## Before the panel (once, about 15 s)
```bash
bash tools/rehearse.sh
```
Records S0-S4 + the 120 s demo timeline for RR / Max-Weight / CAG / DQN (seed 1) and the selected best-case runs into
`ns3-sim/results/` (git-ignored, regenerable), and rebuilds `results/ns3_campaign/summary/best_cases.json`.
Each recording takes 1-8 s; the live demo is real time (120 s). Do one dry run of the live command before the panel.

## Run order (fallback: live -> replay -> screen recording)
1. **Live (about 2 min):** `bash tools/run_live_demo.sh --compare` opens the dashboard with four real-time ns-3 runs on
   the same seed. Point at the timeline events: 20 s interferer, 45 s STA-4 walks out, 70 s STA-2 fails, 100 s recovers.
2. **Scenario tour (about 3 min, offline):** `python3 tools/demo_server.py --open-browser --live`, then pick S1-S4 in the
   Scenario menu; the caption and topology explain each stress. Use Side-by-Side.
3. **Evidence (about 3 min):** click *Evidence*: campaign bars with CIs, the paired table, tail safety, seed spread, then
   "Replay this run" on the best cases. Say that these are selected best cases, then show the average table.

## What to say (and not say)
- The DQN beats Round Robin by 8-13%, Random by about 50% and Fixed Priority by about 80%.
- Versus Max-Weight/CAG it is on average about 5% worse (tie with CAG in S1); seeds 1-3 are close, 0 and 4 about 10% worse.
- Demo seed 1 was picked after seeing ns-3 results. Do not call it the validation-chosen seed.
- It runs as C++ in ns-3, not through gym. Everything on screen is ns-3 output.

## If something fails
- No ns-3 found: `export NS3_DIR=/path/to/ns-3.xx` (built, with `scratch/aoi-scheduler` linked).
- Evidence/Replay empty: run `bash tools/rehearse.sh`.
- Different DQN seed: `DQN_SEED=2 bash tools/rehearse.sh` and `bash tools/run_live_demo.sh --compare 8000 9999 2`.
