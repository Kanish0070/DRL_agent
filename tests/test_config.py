"""Tests for the system config loader/validator (D1.3: WifiPsMode must be
NONE; queue must be a single-slot LCFS buffer; unknown keys are rejected)."""

import textwrap

import pytest

from common.config import ConfigValidationError, load_system_config

VALID_CONFIG = textwrap.dedent("""\
    system:
      n_nodes: 4
      node_classes: ["urgent", "urgent", "important", "routine"]
    scheduler:
      weights: {urgent: 10, important: 3, routine: 1}
      dui_alpha: 2.0
      dui_lambda: 1.5
      dui_beta: 0.5
      thresholds: {urgent: 200, important: 500, routine: 1000}
      queue_discipline: "lcfs"
      queue_size: 1
      heartbeat_period_s: 2.0
      n_degraded: 3
      n_fail: 5
      shield_ceilings_s: {urgent: 2.0, important: 6.0, routine: 20.0}
      run_duration_s: 300
      runs_per_condition: 10
    rl:
      gamma: 0.95
    network:
      wifi_ps_mode: "NONE"
      udp_port_uplink: 5005
      udp_port_grant: 5006
""")


def _write_config(tmp_path, text: str):
    path = tmp_path / "system.yaml"
    path.write_text(text)
    return path


def test_loads_the_real_project_config():
    # This is the config actually shipped in config/system.yaml.
    config = load_system_config("config/system.yaml")
    assert config["system"]["n_nodes"] == 4
    assert config["network"]["wifi_ps_mode"] == "NONE"


def test_valid_config_loads(tmp_path):
    path = _write_config(tmp_path, VALID_CONFIG)
    config = load_system_config(path)
    assert config["scheduler"]["queue_size"] == 1


def test_rejects_unknown_top_level_section(tmp_path):
    bad = VALID_CONFIG + "rogue_section:\n  key: 1\n"
    path = _write_config(tmp_path, bad)
    with pytest.raises(ConfigValidationError, match="Unknown config sections"):
        load_system_config(path)


def test_rejects_wrong_node_count(tmp_path):
    bad = VALID_CONFIG.replace("n_nodes: 4", "n_nodes: 5")
    path = _write_config(tmp_path, bad)
    with pytest.raises(ConfigValidationError, match="n_nodes must be exactly 4"):
        load_system_config(path)


def test_rejects_queue_size_other_than_one(tmp_path):
    bad = VALID_CONFIG.replace("queue_size: 1", "queue_size: 2")
    path = _write_config(tmp_path, bad)
    with pytest.raises(ConfigValidationError, match="queue_size must be 1"):
        load_system_config(path)


def test_rejects_wifi_power_save_enabled(tmp_path):
    # D1.3: power-save must stay off, or radios sleeping mid-slot would
    # introduce latency spikes that corrupt the AoI/timing measurements.
    bad = VALID_CONFIG.replace('wifi_ps_mode: "NONE"', 'wifi_ps_mode: "MIN_MODEM"')
    path = _write_config(tmp_path, bad)
    with pytest.raises(ConfigValidationError, match="wifi_ps_mode MUST be 'NONE'"):
        load_system_config(path)


def test_rejects_invalid_queue_discipline(tmp_path):
    bad = VALID_CONFIG.replace('queue_discipline: "lcfs"', 'queue_discipline: "priority"')
    path = _write_config(tmp_path, bad)
    with pytest.raises(ConfigValidationError, match="queue_discipline"):
        load_system_config(path)
