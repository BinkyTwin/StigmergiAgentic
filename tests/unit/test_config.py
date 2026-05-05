"""Unit tests for configuration validation."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from core.config import ConfigError, load_config, validate_config


def test_validate_config_accepts_fixture(config_dict: dict) -> None:
    validate_config(config_dict)


def test_validate_config_requires_emergence_section(config_dict: dict) -> None:
    config = copy.deepcopy(config_dict)
    config.pop("emergence")
    with pytest.raises(ConfigError):
        validate_config(config)


def test_validate_config_rejects_non_boolean_emergence_enabled(config_dict: dict) -> None:
    config = copy.deepcopy(config_dict)
    config["emergence"]["enabled"] = "true"
    with pytest.raises(ConfigError):
        validate_config(config)


def test_validate_config_rejects_empty_emergence_metrics(config_dict: dict) -> None:
    config = copy.deepcopy(config_dict)
    config["emergence"]["metrics"] = []
    with pytest.raises(ConfigError):
        validate_config(config)


def test_validate_config_rejects_invalid_memory_capacity(config_dict: dict) -> None:
    config = copy.deepcopy(config_dict)
    config["agents"]["memory_capacity"] = 0
    with pytest.raises(ConfigError):
        validate_config(config)


def test_validate_config_rejects_invalid_memory_decay_rate(config_dict: dict) -> None:
    config = copy.deepcopy(config_dict)
    config["agents"]["memory_decay_rate"] = 1.5
    with pytest.raises(ConfigError):
        validate_config(config)


def test_validate_config_rejects_invalid_lesson_threshold(config_dict: dict) -> None:
    config = copy.deepcopy(config_dict)
    config["reinforcement"]["lesson_threshold"] = -0.1
    with pytest.raises(ConfigError):
        validate_config(config)


def test_validate_config_accepts_missing_memory_fields_with_defaults(
    config_dict: dict,
) -> None:
    config = copy.deepcopy(config_dict)
    config["agents"].pop("memory_capacity")
    config["agents"].pop("memory_decay_rate")
    validate_config(config)


def test_validate_config_rejects_invalid_local_sensing_exploration_rate(
    config_dict: dict,
) -> None:
    config = copy.deepcopy(config_dict)
    config["agents"]["local_sensing"]["affinity_exploration_rate"] = 1.5
    with pytest.raises(ConfigError):
        validate_config(config)


def test_validate_config_rejects_invalid_feedback_loop_interval(
    config_dict: dict,
) -> None:
    config = copy.deepcopy(config_dict)
    config["emergence"]["feedback_loop"]["interval_ticks"] = 0
    with pytest.raises(ConfigError):
        validate_config(config)


def test_validate_config_rejects_invalid_recovery_threshold(
    config_dict: dict,
) -> None:
    config = copy.deepcopy(config_dict)
    config["orchestrator"]["recovery_controller"]["contention_threshold"] = 1.5
    with pytest.raises(ConfigError):
        validate_config(config)


def test_load_config_accepts_travelplanner_v4_only_preset() -> None:
    config = load_config(Path("config/travelplanner_v4_only.yaml"))

    assert config["agents"]["local_sensing"]["enabled"] is True
    assert config["markers"]["time_decay"]["enabled"] is True
    assert config["reinforcement"]["frequentation"]["enabled"] is True
    assert config["orchestrator"]["emergent_resolution"]["enabled"] is True
    assert config["emergence"]["feedback_loop"]["enabled"] is True
    assert config["markers"]["session_isolation"] is True


def test_load_config_accepts_v5_full_preset() -> None:
    config = load_config(Path("config/ablation/v5_full.yaml"))

    assert config["agents"]["num_agents"] == 6
    assert config["orchestrator"]["max_ticks"] == 80
    assert config["markers"]["session_isolation"] is True
    assert config["agents"]["local_sensing"]["enabled"] is True
    assert config["markers"]["time_decay"]["enabled"] is True


def test_load_config_accepts_v6_presets() -> None:
    v6_a = load_config(Path("config/ablation/v6_A.yaml"))
    v6_c = load_config(Path("config/ablation/v6_C.yaml"))

    assert v6_a["orchestrator"]["idle_cycles_to_stop"] == 16
    assert v6_a["orchestrator"]["recovery_controller"]["enabled"] is True
    assert v6_a["agents"]["stickiness"]["enabled"] is False
    assert v6_c["orchestrator"]["targeted_repair"]["enabled"] is True


def test_validate_config_rejects_invalid_promotion_min_uses(
    config_dict: dict,
) -> None:
    config = copy.deepcopy(config_dict)
    config["reinforcement"]["promotion_min_uses"] = 0
    with pytest.raises(ConfigError):
        validate_config(config)


def test_validate_config_rejects_invalid_cross_run_flag(config_dict: dict) -> None:
    config = copy.deepcopy(config_dict)
    config["emergence"]["cross_run"]["enabled"] = "yes"
    with pytest.raises(ConfigError):
        validate_config(config)


def test_validate_config_requires_non_empty_skill_library_db_path(
    config_dict: dict,
) -> None:
    config = copy.deepcopy(config_dict)
    config["skill_library"]["db_path"] = ""
    with pytest.raises(ConfigError):
        validate_config(config)


def test_load_config_accepts_sprint9_train_eval_presets() -> None:
    adapt = load_config(Path("config/travelplanner_adapt.yaml"))
    evaluation = load_config(Path("config/travelplanner_eval.yaml"))

    assert adapt["skill_library"]["enabled"] is True
    assert adapt["travelplanner"]["dataset_split"] == "train"
    assert adapt["protocol"]["enabled"] is True
    assert adapt["emergence"]["cross_run"]["enabled"] is True
    assert evaluation["travelplanner"]["dataset_split"] == "validation"
    assert evaluation["skill_library"]["read_only"] is True
    assert evaluation["protocol"]["read_only"] is True
