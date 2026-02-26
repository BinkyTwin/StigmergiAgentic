"""Decay helpers for marker intensity and inhibition."""

from __future__ import annotations

import math


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


def decay_inhibition(value: float, inhibition_decay_rate: float) -> float:
    """Apply exponential decay to inhibition values."""
    if inhibition_decay_rate < 0:
        raise ValueError("inhibition_decay_rate must be non-negative")

    current = _clamp(value, 0.0, 1.0)
    return _clamp(current * math.exp(-inhibition_decay_rate), 0.0, 1.0)
