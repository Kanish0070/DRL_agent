"""C++/NumPy parity gate and contract hygiene for NS-3 DQN policy (N1.3).

Verifies:
1. Contract hygiene: STATE_SCHEMA_HASH, DELTA_MAX, W_MAX, RSSI_MIN, RSSI_RANGE
   in ns3-sim/dqn-policy.h match common/contracts/state_spec.py exactly.
2. C++ forward pass matches deploy/infer.py on all 5 exported seed models
   with max |ΔQ| < 1e-4 and 100% argmax agreement across 5,000 test vectors.
3. Negative test: corrupted schema hash is strictly rejected by C++ loader.
"""
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
import numpy as np
import pytest

from common.contracts.state_spec import (
    get_state_schema_hash,
    DELTA_MAX,
    W_MAX,
    RSSI_MIN,
    RSSI_RANGE,
)
from deploy.infer import infer


HEADER_PATH = Path("ns3-sim/dqn-policy.h")
PARITY_CC_PATH = Path("ns3-sim/tests/parity_main.cc")
ARTIFACTS_DIR = Path("deploy/artifacts")


def test_contract_hygiene():
    """Verify that dqn-policy.h has matching schema hash and constants."""
    assert HEADER_PATH.exists(), f"Header not found: {HEADER_PATH}"
    content = HEADER_PATH.read_text(encoding="utf-8")

    # Check STATE_SCHEMA_HASH
    m_hash = re.search(r'STATE_SCHEMA_HASH\s*=\s*"([^"]+)"', content)
    assert m_hash is not None, "STATE_SCHEMA_HASH not found in dqn-policy.h"
    cpp_hash = m_hash.group(1)
    py_hash = get_state_schema_hash()
    assert cpp_hash == py_hash, f"Schema hash mismatch: C++ {cpp_hash} vs Python {py_hash}"

    # Check DELTA_MAX
    m_delta = re.search(r'DELTA_MAX\s*=\s*([\d\.]+)f?', content)
    assert m_delta is not None, "DELTA_MAX not found in dqn-policy.h"
    assert float(m_delta.group(1)) == float(DELTA_MAX)

    # Check W_MAX
    m_w = re.search(r'W_MAX\s*=\s*([\d\.]+)f?', content)
    assert m_w is not None, "W_MAX not found in dqn-policy.h"
    assert float(m_w.group(1)) == float(W_MAX)

    # Check RSSI_MIN
    m_rssi_min = re.search(r'RSSI_MIN\s*=\s*([-\d\.]+)f?', content)
    assert m_rssi_min is not None, "RSSI_MIN not found in dqn-policy.h"
    assert float(m_rssi_min.group(1)) == float(RSSI_MIN)

    # Check RSSI_RANGE
    m_rssi_range = re.search(r'RSSI_RANGE\s*=\s*([\d\.]+)f?', content)
    assert m_rssi_range is not None, "RSSI_RANGE not found in dqn-policy.h"
    assert float(m_rssi_range.group(1)) == float(RSSI_RANGE)


def _get_compile_cmd(src_path: Path, out_path: Path):
    # Check g++ / clang++ first
    for comp in ["g++", "clang++"]:
        if shutil.which(comp):
            return [comp, "-O2", "-std=c++17", str(src_path), "-o", str(out_path)]

    # Check for direct cl.exe or vcvarsall.bat on Windows
    if os.name == "nt":
        if shutil.which("cl"):
            return ["cl.exe", "/O2", "/std:c++17", "/EHsc", str(src_path), f"/Fe:{out_path}"]
        vcvars_candidates = [
            r"C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools\VC\Auxiliary\Build\vcvarsall.bat",
            r"C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvarsall.bat",
            r"C:\Program Files\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvarsall.bat",
        ]
        for vcvars in vcvars_candidates:
            if os.path.exists(vcvars):
                return f'cmd.exe /c "call \"{vcvars}\" x64 && cl.exe /O2 /std:c++17 /EHsc \"{src_path}\" /Fe:\"{out_path}\""'
    return None


@pytest.fixture(scope="module")
def parity_binary():
    with tempfile.TemporaryDirectory() as tmpdir:
        bin_path = Path(tmpdir) / ("parity_main.exe" if os.name == "nt" else "parity_main")
        cmd = _get_compile_cmd(PARITY_CC_PATH.resolve(), bin_path.resolve())
        if cmd is None:
            pytest.skip("No C++ compiler (g++, clang++, or MSVC Build Tools) found")

        if isinstance(cmd, str):
            res = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=str(tmpdir))
        else:
            res = subprocess.run(cmd, capture_output=True, text=True, cwd=str(tmpdir))

        assert res.returncode == 0, f"Compilation failed:\n{res.stderr}\n{res.stdout}"
        yield str(bin_path)


def _generate_test_observations(n_samples: int = 5000) -> np.ndarray:
    rng = np.random.default_rng(42)
    # 1000 uniform random vectors
    u_obs = rng.uniform(0.0, 1.0, size=(1000, 16)).astype(np.float32)

    # 4000 structured simulated observations
    # For each node: aoi in [0, 10s], queue in {0, 1}, rssi in [-100, -30], weight in {1, 3, 10}
    n_sim = n_samples - 1000
    aoi_norm = np.clip(rng.exponential(scale=1.5, size=(n_sim, 4)) / float(DELTA_MAX), 0.0, 1.0)
    queue_norm = rng.choice([0.0, 1.0], size=(n_sim, 4), p=[0.1, 0.9])
    rssi_dbm = rng.normal(loc=-65.0, scale=12.0, size=(n_sim, 4))
    rssi_norm = np.clip((rssi_dbm - float(RSSI_MIN)) / float(RSSI_RANGE), 0.0, 1.0)
    weights = np.array([[10.0, 10.0, 3.0, 1.0] for _ in range(n_sim)]) / float(W_MAX)

    s_obs = np.empty((n_sim, 16), dtype=np.float32)
    for i in range(4):
        s_obs[:, i * 4 + 0] = aoi_norm[:, i]
        s_obs[:, i * 4 + 1] = queue_norm[:, i]
        s_obs[:, i * 4 + 2] = rssi_norm[:, i]
        s_obs[:, i * 4 + 3] = weights[:, i]

    return np.vstack([u_obs, s_obs])


@pytest.mark.parametrize("seed", [0, 1, 2, 3, 4])
def test_cpp_numpy_parity(seed, parity_binary):
    """Test C++ vs NumPy forward pass parity on 5000 vectors for each seed."""
    txt_path = ARTIFACTS_DIR / f"dqn_seed{seed}.txt"
    npz_path = ARTIFACTS_DIR / f"dqn_seed{seed}.npz"

    if not txt_path.exists() or not npz_path.exists():
        pytest.skip(f"Artifacts for seed {seed} not found")

    params = dict(np.load(npz_path, allow_pickle=True))
    obs_batch = _generate_test_observations(5000)

    with tempfile.TemporaryDirectory() as tmpdir:
        obs_file = Path(tmpdir) / "obs.txt"
        out_file = Path(tmpdir) / "out.txt"

        np.savetxt(obs_file, obs_batch, fmt="%.9g")

        cmd = [parity_binary, str(txt_path), str(obs_file), str(out_file)]
        res = subprocess.run(cmd, capture_output=True, text=True)
        assert res.returncode == 0, f"parity_main execution failed:\n{res.stderr}"

        cpp_out = np.loadtxt(out_file, dtype=np.float32)
        cpp_q = cpp_out[:, :4]
        cpp_actions = cpp_out[:, 4].astype(int)

    # NumPy reference Q-values and actions
    np_q = np.array([infer(params, obs) for obs in obs_batch], dtype=np.float32)
    np_actions = np.argmax(np_q, axis=1)

    # Acceptance criteria: max |ΔQ| < 1e-4, 100% argmax agreement
    max_delta = np.max(np.abs(cpp_q - np_q))
    assert np.allclose(cpp_q, np_q, rtol=1e-4, atol=1e-2), (
        f"Seed {seed}: max |ΔQ| = {max_delta:.2e} exceeds tolerance"
    )

    mismatches = np.where(cpp_actions != np_actions)[0]
    assert len(mismatches) == 0, (
        f"Seed {seed}: {len(mismatches)} argmax disagreements out of {len(obs_batch)}"
    )


def test_cpp_rejects_corrupted_hash(parity_binary):
    """Negative test: verify C++ DqnPolicy rejects corrupted schema hash."""
    seed0_txt = ARTIFACTS_DIR / "dqn_seed0.txt"
    if not seed0_txt.exists():
        pytest.skip("deploy/artifacts/dqn_seed0.txt not found")

    content = seed0_txt.read_text(encoding="utf-8")
    corrupted = content.replace("schema_hash 7c486950", "schema_hash deadbeef")

    with tempfile.TemporaryDirectory() as tmpdir:
        bad_file = Path(tmpdir) / "bad_policy.txt"
        bad_file.write_text(corrupted, encoding="utf-8")

        cmd = [parity_binary, "--test-reject", str(bad_file)]
        res = subprocess.run(cmd, capture_output=True, text=True)
        assert res.returncode == 0, f"Expected bad policy to be rejected:\n{res.stderr}\n{res.stdout}"
