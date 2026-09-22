"""Validation harness (T2.6): checks the simulator's empirical channel
statistics against config/measured_params.yaml.

IMPORTANT CAVEAT: measured_params.yaml currently holds PLACEHOLDER values
(P1 is blocked pending hardware). Until P1 delivers a real fit, this is a
*self-consistency* check -- does ChannelModel's Monte Carlo behavior match
its own configured analytic curve? -- not yet a hardware validation. The
function signatures and report shape are designed so that swapping in a
real measured_params.yaml turns this into the genuine hardware-vs-sim gate
T2.6 specifies, with no code changes required.
"""

from pathlib import Path

import numpy as np
import yaml

from sim.channel import ChannelModel, ChannelParams, path_loss_db, success_probability_from_rssi


def gilbert_elliott_stationary_bad_fraction(p_good_to_bad: float, p_bad_to_good: float) -> float:
    return p_good_to_bad / (p_good_to_bad + p_bad_to_good)


def expected_success_probability(distance_m: float, params: ChannelParams) -> float:
    """Analytic success probability at zero shadowing, averaged over the
    Gilbert-Elliott chain's stationary distribution."""
    loss = path_loss_db(np.array([distance_m]), params)[0]
    rssi = params.tx_power_dbm - loss
    p_good = success_probability_from_rssi(np.array([rssi]), params)[0]
    bad_fraction = gilbert_elliott_stationary_bad_fraction(
        params.ge_prob_good_to_bad, params.ge_prob_bad_to_good
    )
    p_bad = p_good * params.ge_bad_state_success_multiplier
    return float((1 - bad_fraction) * p_good + bad_fraction * p_bad)


def validate_channel_success_curve(
    measured_params: dict,
    distances_m=(5.0, 8.0, 12.0, 18.0),
    n_trials: int = 20_000,
    seed: int = 0,
    tolerance: float = 0.05,
) -> dict:
    """Runs a Monte Carlo simulation at each distance and compares the
    empirical delivery rate to the analytic curve derived from the same
    config. Mirrors the acceptance criterion "simulated PDR-vs-RSSI within
    0.05 of the fit" -- against the fit *this file currently holds*.
    """
    params = ChannelParams.from_measured_params(measured_params)
    rng = np.random.Generator(np.random.PCG64(seed))

    report = {"tolerance": tolerance, "rows": [], "passed": True}
    for distance in distances_m:
        channel = ChannelModel(np.array([distance]), params)
        successes = 0
        for _ in range(n_trials):
            channel.step(rng)
            successes += channel.draw_success(0, rng)
        empirical = successes / n_trials
        expected = expected_success_probability(distance, params)
        abs_error = abs(empirical - expected)

        report["rows"].append({
            "distance_m": distance,
            "expected": expected,
            "empirical": empirical,
            "abs_error": abs_error,
            "passed": abs_error <= tolerance,
        })
        if abs_error > tolerance:
            report["passed"] = False

    return report


if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--measured-params", type=Path, default=Path("config/measured_params.yaml"))
    parser.add_argument("--n-trials", type=int, default=20_000)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    with open(args.measured_params) as f:
        measured_params = yaml.safe_load(f)

    result = validate_channel_success_curve(measured_params, n_trials=args.n_trials, seed=args.seed)
    for row in result["rows"]:
        status = "PASS" if row["passed"] else "FAIL"
        print(f"{status}  d={row['distance_m']:.1f}m  expected={row['expected']:.4f}  "
              f"empirical={row['empirical']:.4f}  abs_error={row['abs_error']:.4f}")

    print("\nALL PASSED" if result["passed"] else "\nFAILED")
    sys.exit(0 if result["passed"] else 1)
