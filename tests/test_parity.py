"""Parity gate and negative tests (T7.3, T7.5).

T7.3: max|ΔQ| < 1e-5 and 100% argmax agreement between SB3 and NumPy.
T7.5: Mismatched / corrupted state_schema_hash is rejected with a clear error.
"""
import copy
import os
import tempfile

import numpy as np
import pytest

from deploy.infer import infer
from common.contracts.state_spec import get_state_schema_hash


# ── T7.5 — negative tests (run without a trained model) ──────────────────────

def test_infer_rejects_missing_schema_hash():
    """No state_schema_hash at all -> ValueError."""
    params = {"n_layers": 0}
    with pytest.raises(ValueError, match="Mismatched state schema hash"):
        infer(params, np.zeros(16, dtype=np.float32))


def test_infer_rejects_corrupted_schema_hash():
    """Wrong state_schema_hash -> ValueError."""
    params = {"n_layers": 0, "state_schema_hash": "definitely_wrong_hash"}
    with pytest.raises(ValueError, match="Mismatched state schema hash"):
        infer(params, np.zeros(16, dtype=np.float32))


# ── T7.3 — positive parity gate (requires a trained model) ───────────────────

def _make_obs_batch(rng: np.random.Generator) -> np.ndarray:
    """Representative + edge-case 16-D observations."""
    batch = []
    # random valid observations
    batch.extend(rng.random((20, 16)).astype(np.float32).tolist())
    # all-zero AoI
    z = np.zeros(16, dtype=np.float32)
    batch.append(z.tolist())
    # max AoI (1.0 normalized)
    m = np.ones(16, dtype=np.float32)
    batch.append(m.tolist())
    # one node at shield ceiling (aoi_norm = 1.0 for node 0)
    s = rng.random(16).astype(np.float32)
    s[0] = 1.0
    batch.append(s.tolist())
    return np.array(batch, dtype=np.float32)


@pytest.mark.skipif(
    not any(
        f.startswith("dqn_seed") and f.endswith(".zip")
        for f in (os.listdir("models") if os.path.isdir("models") else [])
    ),
    reason="No trained DQN model found in models/ — run `python -m rl.train --seed 0` first.",
)
def test_parity_gate():
    """max|ΔQ| < 1e-5 and 100% argmax agreement between SB3 and NumPy."""
    import torch
    from stable_baselines3 import DQN
    from deploy.export import export_model

    # Load first available model
    model_files = [f for f in os.listdir("models") if f.startswith("dqn_seed") and f.endswith(".zip")]
    model_path = os.path.join("models", model_files[0].replace(".zip", ""))
    model = DQN.load(model_path)

    rng = np.random.default_rng(99)
    obs_batch = _make_obs_batch(rng)

    # Export to npz and reload
    with tempfile.TemporaryDirectory() as tmpdir:
        npz_path = os.path.join(tmpdir, "model")
        export_model(model, npz_path)
        params = dict(np.load(npz_path + ".npz", allow_pickle=True))

    # SB3 Q-values
    obs_tensor = torch.tensor(obs_batch)
    with torch.no_grad():
        sb3_q = model.q_net(obs_tensor).numpy()

    # NumPy Q-values
    np_q = np.stack([infer(params, obs) for obs in obs_batch])

    delta = np.abs(sb3_q - np_q)
    assert delta.max() < 1e-5, f"max|ΔQ| = {delta.max():.2e} exceeds 1e-5"

    sb3_actions = np.argmax(sb3_q, axis=1)
    np_actions = np.argmax(np_q, axis=1)
    assert np.all(sb3_actions == np_actions), (
        f"Action disagreement at indices {np.where(sb3_actions != np_actions)[0].tolist()}"
    )
