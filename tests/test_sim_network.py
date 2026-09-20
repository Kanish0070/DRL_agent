"""Tests for sim/network.py (T2.4)."""

import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
import yaml

from common.config import load_system_config
from sim.network import NetworkSim, SimConfig

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def sim_config() -> SimConfig:
    system_config = load_system_config("config/system.yaml")
    with open("config/measured_params.yaml") as f:
        measured_params = yaml.safe_load(f)
    return SimConfig.from_configs(system_config, measured_params, episode_length=50)


def test_reset_returns_16d_observation(sim_config):
    sim = NetworkSim(sim_config)
    obs = sim.reset(seed=0)
    assert obs.shape == (16,)
    assert obs.dtype == np.float32


def test_step_rejects_out_of_range_action(sim_config):
    sim = NetworkSim(sim_config)
    sim.reset(seed=0)
    with pytest.raises(ValueError):
        sim.step(4)


def test_same_seed_reproduces_identical_trajectory_bitwise(sim_config):
    def run_trajectory(seed: int) -> list[np.ndarray]:
        sim = NetworkSim(sim_config)
        obs = sim.reset(seed=seed)
        trace = [obs.copy()]
        for slot in range(30):
            action = slot % sim_config.n_nodes
            obs, _ = sim.step(action)
            trace.append(obs.copy())
        return trace

    trace_a = run_trajectory(seed=123)
    trace_b = run_trajectory(seed=123)
    for a, b in zip(trace_a, trace_b):
        assert np.array_equal(a, b)


def test_different_seeds_diverge(sim_config):
    def final_obs(seed: int) -> np.ndarray:
        sim = NetworkSim(sim_config)
        sim.reset(seed=seed)
        obs = None
        for slot in range(30):
            obs, _ = sim.step(slot % sim_config.n_nodes)
        return obs

    assert not np.array_equal(final_obs(1), final_obs(2))


def test_episode_truncates_at_configured_length(sim_config):
    sim = NetworkSim(sim_config)
    sim.reset(seed=0)
    truncated = False
    for slot in range(sim_config.episode_length):
        _, info = sim.step(slot % sim_config.n_nodes)
        truncated = info["truncated"]
    assert truncated
    assert info["terminated"] is False  # continuing task, per F2.7


def test_empty_grant_and_channel_failure_are_tracked_separately(sim_config):
    # Force zero arrivals so every grant is provably an empty-queue grant.
    sim_config.arrival_prob = np.zeros(sim_config.n_nodes)
    sim = NetworkSim(sim_config)
    sim.reset(seed=0)
    for _ in range(20):
        sim.step(0)
    assert sim.empty_grants == 20
    assert sim.channel_failures == 0


def test_no_global_numpy_random_use_in_sim_package():
    result = subprocess.run(
        [sys.executable, "-c", (
            "import re, pathlib, sys\n"
            "hits = []\n"
            "for f in pathlib.Path('sim').rglob('*.py'):\n"
            "    for i, line in enumerate(f.read_text().splitlines(), 1):\n"
            "        if re.search(r'(?<!Generator\\()np\\.random\\.(?!Generator|PCG64)', line):\n"
            "            hits.append(f'{f}:{i}: {line.strip()}')\n"
            "print('\\n'.join(hits))\n"
            "sys.exit(1 if hits else 0)\n"
        )],
        cwd=PROJECT_ROOT, capture_output=True, text=True,
    )
    assert result.returncode == 0, f"Global np.random usage found:\n{result.stdout}"
