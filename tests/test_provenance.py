"""Tests for run provenance: every recorded run must be traceable to a
git commit, a config hash, and a state schema hash (T0.7)."""

import json

from common.provenance import generate_run_meta, get_config_hash, write_run_meta


def test_config_hash_is_deterministic():
    assert get_config_hash() == get_config_hash()


def test_run_meta_has_all_required_fields():
    meta = generate_run_meta(policy_id="rr", seed=0)
    for key in ("timestamp_utc", "host", "git_sha", "is_dirty",
                "config_hash", "state_schema_hash", "policy_id", "seed"):
        assert key in meta

    assert meta["policy_id"] == "rr"
    assert meta["seed"] == 0


def test_write_run_meta_produces_valid_json(tmp_path):
    write_run_meta(tmp_path, policy_id="cag", seed=7)
    meta_path = tmp_path / "run_meta.json"
    assert meta_path.exists()

    with open(meta_path) as f:
        meta = json.load(f)
    assert meta["policy_id"] == "cag"
    assert meta["seed"] == 7
