"""Unit tests for configuration validation."""

from __future__ import annotations

import copy

import pytest

from core.config import ConfigError, validate_config


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
