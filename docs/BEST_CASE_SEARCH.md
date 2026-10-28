# Best-case regime search

Written **before the sweep was run**. Purpose: find the network conditions where the deployed DQN does best against the strongest baselines, and report them with the selection stated.
This is a selected best case, not an unbiased average. It is presented as such.

## Protocol
- Separate results folder `results/ns3_best_case_search/`. Main campaign results and seeds are untouched.
- Schedulers: DQN (5 training seeds, pooled; deployed seed 1 reported separately), CAG, Fixed Priority, Round Robin. No retraining.
- **Candidate conditions:** the 19 configurations in `ns3-sim/scripts/best_case_grid.tsv` (TX power x distance scale, channel-formula mismatch in both directions, path-loss exponent, mobility), fixed now.
  A configuration is dropped only if Round Robin leaves a node that never delivers (association failure); that is not a scheduler comparison.
- **Candidate metrics (4, fixed now):** (1) criticality-weighted mean AoI, (2) overall deadline miss: mean over the four nodes of the share of time past the soft deadline (equal node weights),
  (3) important + routine deadline miss: mean of the two lower-priority nodes' shares, (4) criticality-weighted AoI, 95th percentile.
- **Selection stage:** seeds 300-304. For each configuration x metric, score = DQN's relative improvement over the **best** of CAG / Fixed Priority / Round Robin on that metric (so a win means beating all three).
  Both pooled DQN and the deployed seed must be ahead. Number of configurations x metrics examined is reported.
- **Confirmation stage:** the top configurations (at most 3) are re-run on fresh seeds 400-419 (20 seeds) for all schedulers. Only these confirmed numbers are quoted, with paired 95% CI and seeds won.
  The selection-stage numbers are not quoted as results.
- **Disclosure:** every figure from this search is labelled "selected from N configurations x 4 metrics; confirmed on fresh seeds".
- If no configuration shows DQN ahead of the best baseline by a meaningful margin on confirmation, that is the result and it is reported as such. Targets such as "15%" are goals, not criteria.

## Association check (Round Robin only, seed 300, 120 s)
Dropped (a node never delivers): G07, G08, G10, G11, G17. Valid: G01-G06, G09, G12-G16, G18, G19 (14 configurations). Wasted slots under Round Robin range from 3% (G01, G05) to 24% (G14).

## Results
(to be filled in)
