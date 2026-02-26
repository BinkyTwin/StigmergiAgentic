"""Configuration loading and validation for V2 Sprint 1."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import yaml


DEFAULT_CONFIG_PATH = Path("config/default.yaml")
REQUIRED_TOP_LEVEL_SECTIONS = {
    "framework",
    "agents",
    "markers",
    "guardrails",
    "orchestrator",
    "llm",
    "pressures",
}


class ConfigError(ValueError):
    """Raised when configuration is invalid."""


def load_config(config_path: str | Path | None = None) -> dict[str, Any]:
    """Load default config and optionally merge overrides from config_path."""
    defaults = _read_yaml(DEFAULT_CONFIG_PATH)

    if config_path is None:
        config = defaults
    else:
        path = Path(config_path)
        overrides = _read_yaml(path)
        config = merge_config(defaults, overrides)

    validate_config(config)
    return config


def merge_config(
    defaults: Mapping[str, Any],
    overrides: Mapping[str, Any],
) -> dict[str, Any]:
    """Deep merge dictionaries with override precedence."""
    result: dict[str, Any] = dict(defaults)
    for key, override_value in overrides.items():
        if (
            key in result
            and isinstance(result[key], Mapping)
            and isinstance(override_value, Mapping)
        ):
            result[key] = merge_config(result[key], override_value)
        else:
            result[key] = override_value
    return result


def validate_config(config: Mapping[str, Any]) -> None:
    """Validate required structure and critical value constraints."""
    missing = REQUIRED_TOP_LEVEL_SECTIONS - set(config.keys())
    if missing:
        missing_str = ", ".join(sorted(missing))
        raise ConfigError(f"Missing required config sections: {missing_str}")

    _validate_int(config["agents"], "num_agents", minimum=1)
    _validate_float(config["agents"], "selection_temperature", minimum=0.0)

    markers = config["markers"]
    decay_type = str(markers.get("decay_type", ""))
    if decay_type not in {"exponential", "linear"}:
        raise ConfigError("markers.decay_type must be 'exponential' or 'linear'")

    _validate_float(markers, "decay_rate", minimum=0.0)
    _validate_float(markers, "inhibition_decay_rate", minimum=0.0)
    _validate_float(markers, "inhibition_increment", minimum=0.0)
    _validate_float(markers, "inhibition_threshold", minimum=0.0, maximum=1.0)

    clamp = markers.get("intensity_clamp")
    if not isinstance(clamp, list) or len(clamp) != 2:
        raise ConfigError("markers.intensity_clamp must be a list of two numbers")
    clamp_min = float(clamp[0])
    clamp_max = float(clamp[1])
    if clamp_min < 0.0 or clamp_max > 1.0 or clamp_min > clamp_max:
        raise ConfigError("markers.intensity_clamp must satisfy 0 <= min <= max <= 1")

    guardrails = config["guardrails"]
    _validate_int(guardrails, "max_retry_count", minimum=0)
    _validate_int(guardrails, "scope_lock_ttl", minimum=1)

    orchestrator = config["orchestrator"]
    _validate_int(orchestrator, "max_ticks", minimum=1)
    _validate_int(orchestrator, "idle_cycles_to_stop", minimum=0)

    llm = config["llm"]
    _validate_int(llm, "max_tokens_total", minimum=1)
    _validate_float(llm, "max_budget_usd", minimum=0.0)


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")

    with path.open("r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle) or {}

    if not isinstance(loaded, dict):
        raise ConfigError(f"Config file must contain a mapping: {path}")

    return loaded


def _validate_int(
    data: Mapping[str, Any],
    key: str,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int:
    value = int(data.get(key))
    if minimum is not None and value < minimum:
        raise ConfigError(f"{key} must be >= {minimum}, got {value}")
    if maximum is not None and value > maximum:
        raise ConfigError(f"{key} must be <= {maximum}, got {value}")
    return value


def _validate_float(
    data: Mapping[str, Any],
    key: str,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float:
    value = float(data.get(key))
    if minimum is not None and value < minimum:
        raise ConfigError(f"{key} must be >= {minimum}, got {value}")
    if maximum is not None and value > maximum:
        raise ConfigError(f"{key} must be <= {maximum}, got {value}")
    return value
