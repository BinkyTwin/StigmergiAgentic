"""Reinforcement utilities for adaptive marker intensity updates."""

from __future__ import annotations

import math
from collections import deque

from .dependency import depends_on_ids
from .marker import Marker


def reinforce_on_success(
    marker: Marker,
    reinforcement_rate: float,
    quality_score: float,
    max_intensity: float,
) -> float:
    """Increase marker intensity after successful execution.

    Uses a sigmoid quality transform so low-quality successes get weaker gains.
    """
    current = _clamp(marker.intensity, 0.0, max_intensity)
    rate = max(0.0, float(reinforcement_rate))
    quality = _clamp(float(quality_score), 0.0, 1.0)

    quality_signal = _sigmoid((quality - 0.5) * 8.0)
    intensity_gap = max(0.0, float(max_intensity) - current)
    delta = rate * intensity_gap * quality_signal
    return _clamp(current + delta, 0.0, max_intensity)


def penalize_on_failure(marker: Marker, penalty_rate: float) -> tuple[float, float]:
    """Decrease intensity and increase inhibition for failed actions."""
    rate = max(0.0, float(penalty_rate))
    new_intensity = _clamp(float(marker.intensity) - rate, 0.0, 1.0)
    new_inhibition = _clamp(float(marker.inhibition) + (rate * 0.5), 0.0, 1.0)
    return new_intensity, new_inhibition


def frequentation_boost(
    read_count: int,
    base_boost: float = 0.01,
    max_boost: float = 0.1,
    diminishing_factor: float = 0.5,
) -> float:
    """Return a bounded read-traffic reinforcement boost."""
    count = max(0, int(read_count))
    if count <= 0:
        return 0.0

    base = max(0.0, float(base_boost))
    cap = max(0.0, float(max_boost))
    diminishing = float(diminishing_factor)
    if base <= 0.0 or cap <= 0.0:
        return 0.0

    if diminishing <= 0.0 or diminishing == 1.0:
        boost = base * float(count)
    else:
        boost = base * (1.0 - (diminishing**count)) / (1.0 - diminishing)
    return _clamp(boost, 0.0, cap)


def propagate_backward(
    completed_marker_id: str,
    all_markers: list[Marker],
    propagation_factor: float,
) -> list[tuple[str, float]]:
    """Return ancestor reinforcement deltas propagated through dependency edges.

    Each returned tuple is ``(marker_id, delta)`` for one ancestor marker.
    """
    if propagation_factor <= 0.0:
        return []

    markers_by_id = {marker.id: marker for marker in all_markers}
    if completed_marker_id not in markers_by_id:
        return []

    queue: deque[tuple[str, int]] = deque([(completed_marker_id, 0)])
    visited: set[tuple[str, int]] = set()
    deltas: dict[str, float] = {}

    while queue:
        marker_id, depth = queue.popleft()
        key = (marker_id, depth)
        if key in visited:
            continue
        visited.add(key)

        marker = markers_by_id.get(marker_id)
        if marker is None:
            continue

        for dependency_id in depends_on_ids(marker):
            if dependency_id not in markers_by_id:
                continue
            next_depth = depth + 1
            delta = float(propagation_factor) ** float(next_depth)
            deltas[dependency_id] = deltas.get(dependency_id, 0.0) + delta
            queue.append((dependency_id, next_depth))

    if not deltas:
        return []

    ordered = sorted(deltas.items(), key=lambda item: item[0])
    return ordered


def _clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(max_value, float(value)))


def _sigmoid(value: float) -> float:
    return 1.0 / (1.0 + math.exp(-float(value)))
