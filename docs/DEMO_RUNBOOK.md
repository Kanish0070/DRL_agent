# Demo runbook (about 8 minutes)

## Before the panel (once, about 15 s)
```bash
bash tools/rehearse.sh
```
Records S0-S4 + the 120 s demo timeline for RR / Max-Weight / CAG / DQN (seed 1) and the selected best-case runs into
`ns3-sim/results/` (git-ignored, regenerable), and rebuilds `results/ns3_campaign/summary/best_cases.json`.
Each recording takes 1-8 s; the live demo is real time (120 s). Do one dry run of the live command before the panel.

## Run order (fallback: live -> recorded replay -> screen recording)
Start once: `python3 tools/demo_server.py --open-browser --live` (the page controls everything; it only listens on localhost).
1. **Live (about 2 min):** Source = *Live ns-3*, scenario = *Demo timeline*, Run = *All 4 schedulers*, press **&#9654; Run live**.
   Point at the timeline events: 20 s interferer, 45 s STA-4 walks out, 70 s STA-2 fails, 100 s recovers.
   If the panel asks to re-run or change the policy: pick another scenario / scheduler / DQN seed and press **&#9654; Run live**
   (or **Restart** to repeat the same settings); **Stop** ends a run. The *Policy* menu chooses which run fills the main view.
2. **Scenario tour (about 3 min):** Source = *Recorded ns-3 run* (instant, no waiting); pick S1-S4 and use Side-by-Side.
3. **Evidence (about 3 min):** click *Evidence*: campaign bars with CIs, the paired table, tail safety, seed spread, then
   "Replay this run" on the best cases. Say that these are selected best cases, then show the average table.

## Showing that the scheduler works (main page, below the topology)
- **Freshness lanes:** one lane per node; green = fresh, red = at its safety ceiling, white tick = new update delivered. The
  caption above them narrates the latest event ("STA-4 delivered a fresh update, age dropped 1.10 s -> 0.00 s"). Press
  *Classic sawtooth* for the standard plot.
- **Where do grants go:** grant share per node over 30 s vs the 25% fair share (urgent nodes should get more; a failed node less).
- **Why that node:** the latest decision with its priority (weight x age) and signal. The "matches Max-Weight" percentage is a
  derived yardstick (a real Max-Weight run scores about 99% on it): a lower score means a different learned strategy, not a bug.
- **Safety / winning:** % of time every live node is under its ceiling, worst urgent wait, and the running gap vs Round Robin.
- **Grant timeline:** a tick per grant per node. Compare RR (regular rhythm) with DQN/Max-Weight (adaptive) using the
  *Policy* menu in a compare run; watch it react at the failure at 70 s.

## What to say (and not say)
- The DQN beats Round Robin by 8-13%, Random by about 50% and Fixed Priority by about 80%.
- Versus Max-Weight/CAG it is on average about 5% worse (tie with CAG in S1); seeds 1-3 are close, 0 and 4 about 10% worse.
- Demo seed 1 was picked after seeing ns-3 results. Do not call it the validation-chosen seed.
- It runs as C++ in ns-3, not through gym. Everything on screen is ns-3 output.

## If something fails
- No ns-3 found: `export NS3_DIR=/path/to/ns-3.xx` (built, with `scratch/aoi-scheduler` linked).
- Evidence/Replay empty: run `bash tools/rehearse.sh`.
- Different DQN seed: pick it in the live controls; for the recordings use `DQN_SEED=2 bash tools/rehearse.sh`.
