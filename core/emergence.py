"""Emergence metrics computed from orchestrator tick telemetry."""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping


@dataclass(slots=True)
class EmergenceMetrics:
    """Aggregate emergence metrics for one orchestrator run."""

    specialization_entropy: float = 0.0
    colony_specialization: float = 0.0
    collaboration_density: float = 0.0
    action_switching_rate: float = 0.0
    convergence_tick: int | None = None
    lock_contention_rate: float = 0.0
    parallel_utilization: float = 0.0
    pressure_entropy: float = 0.0


def compute_emergence_metrics(
    tick_rows: Iterable[Any],
    total_agents: int,
    audit_log_path: str | Path | None = None,
) -> dict[str, Any]:
    """Compute Sprint 5 emergence metrics from in-memory tick rows."""
    rows = list(tick_rows)
    if not rows:
        empty = EmergenceMetrics()
        return asdict(empty)

    agent_actions = _agent_action_sequences(rows)
    agent_ids = sorted(agent_actions.keys())
    unique_actions = sorted(
        {
            action
            for actions in agent_actions.values()
            for action in actions
            if isinstance(action, str) and action
        }
    )

    specialization_entropy = _mean_normalized_entropy(
        agent_actions=agent_actions,
        agent_ids=agent_ids,
        unique_actions=unique_actions,
    )
    colony_specialization = max(0.0, min(1.0, 1.0 - specialization_entropy))

    metrics = EmergenceMetrics(
        specialization_entropy=specialization_entropy,
        colony_specialization=colony_specialization,
        collaboration_density=_collaboration_density(audit_log_path),
        action_switching_rate=_action_switching_rate(agent_actions, agent_ids),
        convergence_tick=_convergence_tick(rows),
        lock_contention_rate=_lock_contention_rate(rows),
        parallel_utilization=_parallel_utilization(rows, total_agents),
        pressure_entropy=_pressure_entropy(rows),
    )
    return asdict(metrics)


def _agent_action_sequences(rows: list[Any]) -> dict[str, list[str]]:
    sequences: dict[str, list[str]] = {}
    for row in rows:
        decisions = _row_mapping(row, "decisions")
        for agent_id, action in decisions.items():
            agent = str(agent_id).strip()
            if not agent:
                continue
            sequences.setdefault(agent, [])
            if action is None:
                continue
            action_name = str(action).strip()
            if action_name:
                sequences[agent].append(action_name)
    return sequences


def _mean_normalized_entropy(
    *,
    agent_actions: Mapping[str, list[str]],
    agent_ids: list[str],
    unique_actions: list[str],
) -> float:
    if not agent_ids:
        return 0.0
    if len(unique_actions) <= 1:
        return 0.0

    norm_base = math.log2(float(len(unique_actions)))
    entropies: list[float] = []
    for agent_id in agent_ids:
        actions = list(agent_actions.get(agent_id, []))
        if not actions:
            entropies.append(0.0)
            continue

        counts: dict[str, int] = {}
        for action in actions:
            counts[action] = counts.get(action, 0) + 1

        total = float(len(actions))
        entropy = 0.0
        for count in counts.values():
            probability = float(count) / total
            if probability > 0.0:
                entropy -= probability * math.log2(probability)
        entropies.append(entropy / norm_base)

    if not entropies:
        return 0.0
    mean_entropy = sum(entropies) / float(len(entropies))
    return max(0.0, min(1.0, mean_entropy))


def _action_switching_rate(
    agent_actions: Mapping[str, list[str]],
    agent_ids: list[str],
) -> float:
    if not agent_ids:
        return 0.0

    rates: list[float] = []
    for agent_id in agent_ids:
        actions = list(agent_actions.get(agent_id, []))
        if len(actions) <= 1:
            rates.append(0.0)
            continue
        transitions = 0
        for previous, current in zip(actions, actions[1:]):
            if previous != current:
                transitions += 1
        rates.append(float(transitions) / float(len(actions) - 1))

    if not rates:
        return 0.0
    return max(0.0, min(1.0, sum(rates) / float(len(rates))))


def _convergence_tick(rows: list[Any]) -> int | None:
    for row in rows:
        progress = _row_float(row, "terminal_progress")
        if progress >= 0.8:
            return _row_int(row, "tick")
    return None


def _lock_contention_rate(rows: list[Any]) -> float:
    attempts = 0
    conflicts = 0
    for row in rows:
        decisions = _row_mapping(row, "decisions")
        attempts += sum(1 for action in decisions.values() if action is not None)
        conflicts += max(0, _row_int(row, "lock_conflicts"))
    if attempts <= 0:
        return 0.0
    return max(0.0, min(1.0, float(conflicts) / float(attempts)))


def _parallel_utilization(rows: list[Any], total_agents: int) -> float:
    if not rows or int(total_agents) <= 0:
        return 0.0
    denominator = float(total_agents)
    utilization = [
        max(0.0, min(1.0, _row_float(row, "active_agents") / denominator))
        for row in rows
    ]
    return sum(utilization) / float(len(utilization))


def _pressure_entropy(rows: list[Any]) -> float:
    if not rows:
        return 0.0

    actions = sorted(
        {
            action
            for row in rows
            for action in _row_mapping(row, "pressures").keys()
            if str(action).strip()
        }
    )
    if len(actions) <= 1:
        return 0.0

    row_count = float(len(rows))
    mean_pressures = {
        action: sum(
            float(_row_mapping(row, "pressures").get(action, 0.0)) for row in rows
        )
        / row_count
        for action in actions
    }
    total = sum(mean_pressures.values())
    if total <= 0.0:
        return 0.0

    entropy = 0.0
    for value in mean_pressures.values():
        probability = float(value) / float(total)
        if probability > 0.0:
            entropy -= probability * math.log2(probability)
    normalized = entropy / math.log2(float(len(actions)))
    return max(0.0, min(1.0, normalized))


def _collaboration_density(audit_log_path: str | Path | None) -> float:
    if audit_log_path is None:
        return 0.0

    path = Path(audit_log_path)
    if not path.exists():
        return 0.0

    touched_by_marker: dict[str, set[str]] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            raw = line.strip()
            if not raw:
                continue
            try:
                event = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if not isinstance(event, dict):
                continue

            marker_id = str(event.get("marker_id", "")).strip()
            agent_id = str(event.get("agent_id", "")).strip()
            if not marker_id or not agent_id:
                continue
            if agent_id.startswith("system"):
                continue

            touched_by_marker.setdefault(marker_id, set()).add(agent_id)

    if not touched_by_marker:
        return 0.0
    collaborative = sum(
        1 for agents in touched_by_marker.values() if len(agents) > 1
    )
    return float(collaborative) / float(len(touched_by_marker))


def _row_mapping(row: Any, field: str) -> dict[str, Any]:
    value = getattr(row, field, {})
    if isinstance(value, Mapping):
        return {str(k): v for k, v in value.items()}
    return {}


def _row_float(row: Any, field: str) -> float:
    value = getattr(row, field, 0.0)
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _row_int(row: Any, field: str) -> int:
    value = getattr(row, field, 0)
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
