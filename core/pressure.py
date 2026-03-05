"""Pressure computation and probabilistic action selection."""

from __future__ import annotations

import math
import random
from typing import Callable, Mapping, Sequence

from .marker import Marker


TERMINAL_STATES = {"terminal", "skipped", "escalated"}


def compute_pressures(
    markers: Sequence[Marker],
    action_types: Sequence[str],
    weights: Mapping[str, float] | None = None,
    inhibition_threshold: float = 1.0,
    formula: str = "simple",
    alpha: float = 1.0,
    beta: float = 1.0,
    heuristic_fn: Callable[[Marker, str], float] | None = None,
) -> dict[str, float]:
    """Compute normalized pressure per action from eligible markers."""
    ordered_actions = list(dict.fromkeys(action_types))
    if not ordered_actions:
        return {}

    raw_scores = {action_type: 0.0 for action_type in ordered_actions}
    weights_map = dict(weights or {})
    formula_name = str(formula).strip().lower()
    if formula_name not in {"simple", "aco"}:
        formula_name = "simple"
    alpha_value = max(0.0, float(alpha))
    beta_value = max(0.0, float(beta))

    for marker in markers:
        if marker.state in TERMINAL_STATES:
            continue
        if float(marker.inhibition) >= float(inhibition_threshold):
            continue

        eligible_actions = _eligible_actions(
            marker=marker, action_types=ordered_actions
        )
        if not eligible_actions:
            continue

        for action_type in eligible_actions:
            weight = max(float(weights_map.get(action_type, 1.0)), 0.0)
            intensity = max(0.0, float(marker.intensity))
            if formula_name == "aco":
                # ACO-inspired pressure: pheromone^alpha * heuristic^beta.
                pheromone = intensity**alpha_value
                heuristic_input = weight
                if heuristic_fn is not None:
                    try:
                        heuristic_input = float(heuristic_fn(marker, action_type))
                    except Exception:  # noqa: BLE001
                        heuristic_input = weight
                heuristic = max(0.0, heuristic_input) ** beta_value
                raw_scores[action_type] += pheromone * heuristic
            else:
                raw_scores[action_type] += intensity * weight

    total = sum(raw_scores.values())
    if total <= 0.0:
        return {action_type: 0.0 for action_type in ordered_actions}

    return {
        action_type: float(raw_scores[action_type]) / float(total)
        for action_type in ordered_actions
    }


def select_action(
    pressures: Mapping[str, float],
    temperature: float,
    rng: random.Random | None = None,
) -> str | None:
    """Select one action from pressure distribution using softmax."""
    if not pressures:
        return None

    positive = {key: float(value) for key, value in pressures.items() if value > 0.0}
    if not positive:
        return None

    if float(temperature) <= 0.0:
        max_pressure = max(positive.values())
        winners = [key for key, value in positive.items() if value == max_pressure]
        return sorted(winners)[0]

    sampler = rng or random.Random()
    action_names = list(positive.keys())

    logits = [positive[action] / float(temperature) for action in action_names]
    max_logit = max(logits)
    exps = [math.exp(logit - max_logit) for logit in logits]
    denom = sum(exps)
    if denom <= 0.0:
        return sorted(action_names)[0]

    draw = sampler.random()
    cumulative = 0.0
    for action, weight in zip(action_names, exps):
        cumulative += weight / denom
        if draw <= cumulative:
            return action

    return action_names[-1]


def _eligible_actions(marker: Marker, action_types: Sequence[str]) -> list[str]:
    raw = marker.payload.get("eligible_actions")
    if raw is None:
        return list(action_types)
    if isinstance(raw, (list, tuple, set)):
        if len(raw) == 0:
            return list(action_types)
        selected = [str(action) for action in raw if str(action) in action_types]
        if selected:
            return selected
        return list(action_types)
    return list(action_types)
