"""Decay helpers for pheromone intensities and inhibition values."""

from __future__ import annotations

import math


def _clamp_unit(value: float) -> float:
    """Clamp a float value to the [0.0, 1.0] interval."""
    return max(0.0, min(1.0, float(value)))


def decay_intensity(value: float, decay_type: str, decay_rate: float) -> float:
    """Apply configured decay to a task intensity."""
    if decay_rate < 0:
        raise ValueError("decay_rate must be non-negative")

    current_value = _clamp_unit(value)

    if decay_type == "exponential":
        return _clamp_unit(current_value * math.exp(-decay_rate))

    if decay_type == "linear":
        return _clamp_unit(current_value - decay_rate)

    raise ValueError(f"Unsupported decay_type: {decay_type}")


def decay_inhibition(value: float, inhibition_decay_rate: float) -> float:
    """Apply exponential decay to inhibition gamma."""
    if inhibition_decay_rate < 0:
        raise ValueError("inhibition_decay_rate must be non-negative")

    current_value = _clamp_unit(value)
    return _clamp_unit(current_value * math.exp(-inhibition_decay_rate))
