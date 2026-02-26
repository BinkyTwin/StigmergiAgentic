"""Unit tests for decay helpers."""

from __future__ import annotations

import math

import pytest

from core.decay import decay_inhibition, decay_intensity


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
