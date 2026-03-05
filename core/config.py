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
    "reinforcement",
    "guardrails",
    "orchestrator",
    "emergence",
    "llm",
    "pressures",
    "decompose",
    "async",
    "tools",
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

    agents = dict(config["agents"])
    _validate_int(agents, "num_agents", minimum=1)
    _validate_float(agents, "selection_temperature", minimum=0.0)
    agents.setdefault("memory_capacity", 20)
    agents.setdefault("memory_decay_rate", 0.1)
    _validate_int(agents, "memory_capacity", minimum=1)
    _validate_float(agents, "memory_decay_rate", minimum=0.0, maximum=1.0)

    markers = config["markers"]
    decay_type = str(markers.get("decay_type", ""))
    if decay_type not in {"exponential", "linear"}:
        raise ConfigError("markers.decay_type must be 'exponential' or 'linear'")

    _validate_float(markers, "decay_rate", minimum=0.0)
    _validate_float(markers, "default_decay_rate", minimum=0.0)
    _validate_float(markers, "inhibition_decay_rate", minimum=0.0)
    _validate_float(markers, "inhibition_increment", minimum=0.0)
    _validate_float(markers, "inhibition_threshold", minimum=0.0, maximum=1.0)
    prune_threshold = markers.get("prune_threshold")
    if prune_threshold is not None:
        _validate_float(markers, "prune_threshold", minimum=0.0, maximum=1.0)

    decay_rates_by_type = markers.get("decay_rates_by_type", {})
    if not isinstance(decay_rates_by_type, Mapping):
        raise ConfigError("markers.decay_rates_by_type must be a mapping")
    for marker_type, rate in decay_rates_by_type.items():
        try:
            parsed = float(rate)
        except (TypeError, ValueError) as exc:
            raise ConfigError(
                f"markers.decay_rates_by_type.{marker_type} must be numeric"
            ) from exc
        if parsed < 0.0:
            raise ConfigError(
                f"markers.decay_rates_by_type.{marker_type} must be >= 0.0"
            )

    session_isolation = markers.get("session_isolation")
    if not isinstance(session_isolation, bool):
        raise ConfigError("markers.session_isolation must be a boolean")

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

    emergence = config["emergence"]
    enabled = emergence.get("enabled")
    if not isinstance(enabled, bool):
        raise ConfigError("emergence.enabled must be a boolean")
    metrics = emergence.get("metrics")
    if not isinstance(metrics, list) or not metrics:
        raise ConfigError("emergence.metrics must be a non-empty list")
    if not all(isinstance(metric, str) and metric.strip() for metric in metrics):
        raise ConfigError("emergence.metrics entries must be non-empty strings")

    llm = config["llm"]
    _validate_int(llm, "max_tokens_total", minimum=1)
    _validate_float(llm, "max_budget_usd", minimum=0.0)

    reinforcement = config["reinforcement"]
    enabled = reinforcement.get("enabled")
    if not isinstance(enabled, bool):
        raise ConfigError("reinforcement.enabled must be a boolean")
    _validate_float(reinforcement, "rate", minimum=0.0)
    _validate_float(reinforcement, "propagation_factor", minimum=0.0)
    _validate_float(reinforcement, "max_intensity", minimum=0.0, maximum=1.0)
    if "lesson_threshold" in reinforcement:
        _validate_float(
            reinforcement,
            "lesson_threshold",
            minimum=0.0,
            maximum=1.0,
        )

    decompose = config["decompose"]
    _validate_int(decompose, "max_depth", minimum=1)
    _validate_int(decompose, "max_subtasks", minimum=1)
    allow_redecompose = decompose.get("allow_redecompose")
    if not isinstance(allow_redecompose, bool):
        raise ConfigError("decompose.allow_redecompose must be a boolean")

    async_cfg = config["async"]
    _validate_int(async_cfg, "max_concurrent_llm_calls", minimum=1)
    _validate_float(async_cfg, "subprocess_timeout", minimum=1.0)

    pressures = config["pressures"]
    formula = str(pressures.get("formula", "simple")).strip().lower()
    if formula not in {"aco", "simple"}:
        raise ConfigError("pressures.formula must be 'aco' or 'simple'")
    _validate_float(pressures, "alpha", minimum=0.0)
    _validate_float(pressures, "beta", minimum=0.0)

    tools = config["tools"]
    sandbox_root = str(tools.get("sandbox_root", "")).strip()
    if not sandbox_root:
        raise ConfigError("tools.sandbox_root cannot be empty")

    allowed_commands = tools.get("allowed_commands")
    if not isinstance(allowed_commands, list) or not allowed_commands:
        raise ConfigError("tools.allowed_commands must be a non-empty list")
    if not all(isinstance(command, str) and command.strip() for command in allowed_commands):
        raise ConfigError("tools.allowed_commands entries must be non-empty strings")

    _validate_int(tools, "bash_timeout_seconds", minimum=1)
    _validate_int(tools, "max_file_size_bytes", minimum=1)
    _validate_int(tools, "web_search_max_results", minimum=1)

    provider = str(tools.get("web_search_provider", "none")).strip().lower()
    if provider not in {"none", "tavily", "serper"}:
        raise ConfigError(
            "tools.web_search_provider must be one of: none, tavily, serper"
        )


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
