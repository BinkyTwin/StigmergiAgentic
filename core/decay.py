"""Decay helpers for marker intensity and inhibition."""

from __future__ import annotations

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
