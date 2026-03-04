"""Unit tests for decay helpers."""

from __future__ import annotations

import math

import pytest

from core.decay import decay_inhibition, decay_intensity, decay_intensity_by_type


def test_decay_intensity_exponential() -> None:
    value = decay_intensity(1.0, "exponential", 0.05, (0.1, 1.0))
    assert value == pytest.approx(math.exp(-0.05))


def test_decay_intensity_linear_with_clamp() -> None:
    value = decay_intensity(0.12, "linear", 0.05, (0.1, 1.0))
    assert value == pytest.approx(0.1)


def test_decay_inhibition_exponential() -> None:
    value = decay_inhibition(0.5, 0.08)
    assert value == pytest.approx(0.5 * math.exp(-0.08))


def test_decay_intensity_rejects_unsupported_type() -> None:
    with pytest.raises(ValueError):
        decay_intensity(0.5, "cubic", 0.1, (0.1, 1.0))


def test_decay_intensity_by_type_uses_specific_rates() -> None:
    task_value = decay_intensity_by_type(
        value=1.0,
        marker_type="task",
        decay_rates={"task": 0.1, "quality": 0.01},
        default_rate=0.05,
        clamp=(0.1, 1.0),
    )
    quality_value = decay_intensity_by_type(
        value=1.0,
        marker_type="quality",
        decay_rates={"task": 0.1, "quality": 0.01},
        default_rate=0.05,
        clamp=(0.1, 1.0),
    )
    assert task_value < quality_value


def test_decay_intensity_by_type_falls_back_to_default_rate() -> None:
    value = decay_intensity_by_type(
        value=1.0,
        marker_type="unknown_type",
        decay_rates={"task": 0.2},
        default_rate=0.03,
        clamp=(0.1, 1.0),
    )
    assert value == pytest.approx(math.exp(-0.03))


def test_decay_intensity_by_type_edge_case_clamp() -> None:
    value = decay_intensity_by_type(
        value=-2.0,
        marker_type="task",
        decay_rates={"task": 0.5},
        default_rate=0.1,
        clamp=(0.1, 1.0),
        decay_type="linear",
    )
    assert value == pytest.approx(0.1)
