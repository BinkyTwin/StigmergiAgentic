"""Decay helpers for marker intensity and inhibition."""

from __future__ import annotations

from datetime import datetime
import math
from typing import Mapping


def _clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(max_value, float(value)))


def decay_intensity(
    value: float,
    decay_type: str,
    decay_rate: float,
    clamp: tuple[float, float],
) -> float:
    """Apply decay to marker intensity using configured strategy."""
    if decay_rate < 0:
        raise ValueError("decay_rate must be non-negative")

    min_value, max_value = clamp
    if min_value > max_value:
        raise ValueError("clamp min must be <= clamp max")

    current = _clamp(value, min_value, max_value)

    if decay_type == "exponential":
        updated = current * math.exp(-decay_rate)
        return _clamp(updated, min_value, max_value)

    if decay_type == "linear":
        updated = current - decay_rate
        return _clamp(updated, min_value, max_value)

    raise ValueError(f"Unsupported decay_type: {decay_type}")


def decay_intensity_by_type(
    value: float,
    marker_type: str,
    decay_rates: Mapping[str, float] | None,
    default_rate: float,
    clamp: tuple[float, float],
    decay_type: str = "exponential",
) -> float:
    """Apply marker-type specific decay rate with a default fallback."""
    rates = dict(decay_rates or {})
    rate = float(rates.get(str(marker_type), default_rate))
    return decay_intensity(
        value=value,
        decay_type=decay_type,
        decay_rate=rate,
        clamp=clamp,
    )


def decay_inhibition(value: float, inhibition_decay_rate: float) -> float:
    """Apply exponential decay to inhibition values."""
    if inhibition_decay_rate < 0:
        raise ValueError("inhibition_decay_rate must be non-negative")

    current = _clamp(value, 0.0, 1.0)
    return _clamp(current * math.exp(-inhibition_decay_rate), 0.0, 1.0)


def effective_intensity(
    stored_intensity: float,
    last_active_at: str,
    now: str,
    decay_type: str,
    decay_rate: float,
    decay_period_seconds: float,
    clamp: tuple[float, float],
) -> float:
    """Return the time-adjusted intensity visible at read time."""
    if decay_period_seconds <= 0.0:
        return _clamp(stored_intensity, clamp[0], clamp[1])

    last_active = _parse_iso8601(last_active_at)
    current_time = _parse_iso8601(now)
    if last_active is None or current_time is None:
        return _clamp(stored_intensity, clamp[0], clamp[1])

    elapsed_seconds = max(0.0, (current_time - last_active).total_seconds())
    if elapsed_seconds <= 0.0:
        return _clamp(stored_intensity, clamp[0], clamp[1])

    periods = elapsed_seconds / float(decay_period_seconds)
    if decay_type == "exponential":
        updated = float(stored_intensity) * math.exp(-float(decay_rate) * periods)
        return _clamp(updated, clamp[0], clamp[1])

    if decay_type == "linear":
        updated = float(stored_intensity) - (float(decay_rate) * periods)
        return _clamp(updated, clamp[0], clamp[1])

    raise ValueError(f"Unsupported decay_type: {decay_type}")


def _parse_iso8601(value: str) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None
