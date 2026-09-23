"""Inference benchmark — laptop P50/P99 latency (T7.4).

NOTE: The "<5ms on-Pi P99" acceptance criterion is explicitly deferred.
This script measures laptop software-only latency. Pi-specific numbers
require a physical Raspberry Pi Zero 2W and are NOT claimed here.

Usage:
    python -m tools.bench_infer --npz path/to/model.npz --n-reps 10000
"""
import argparse
import time

import numpy as np

from deploy.infer import infer


def benchmark(params: dict, n_reps: int, obs_dim: int = 16, n_actions: int = 4) -> dict:
    rng = np.random.default_rng(42)
    obs_batch = rng.random((n_reps, obs_dim)).astype(np.float32)

    # Warm-up
    for i in range(min(100, n_reps)):
        infer(params, obs_batch[i])

    latencies_us = []
    for i in range(n_reps):
        t0 = time.perf_counter()
        infer(params, obs_batch[i])
        t1 = time.perf_counter()
        latencies_us.append((t1 - t0) * 1_000_000)

    return {
        "n_reps": n_reps,
        "p50_us": float(np.percentile(latencies_us, 50)),
        "p99_us": float(np.percentile(latencies_us, 99)),
        "mean_us": float(np.mean(latencies_us)),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--npz", required=True, help="Path to exported .npz model")
    parser.add_argument("--n-reps", type=int, default=10_000)
    args = parser.parse_args()

    params = dict(np.load(args.npz, allow_pickle=True))
    results = benchmark(params, args.n_reps)

    print(f"\nInference latency (laptop, NOT Raspberry Pi):")
    print(f"  n_reps : {results['n_reps']}")
    print(f"  P50    : {results['p50_us']:.2f} µs")
    print(f"  P99    : {results['p99_us']:.2f} µs")
    print(f"  Mean   : {results['mean_us']:.2f} µs")
    print(f"\n⚠ NOTE: Pi-specific <5ms P99 claim requires physical hardware and is NOT verified here.")


if __name__ == "__main__":
    main()
