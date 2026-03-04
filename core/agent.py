"""Generic stigmergic agent implementation."""

from __future__ import annotations

import random
from typing import Any

from .dependency import unblocked_markers
from .environment import Environment, EnvironmentSnapshot
from .guardrails import BudgetExceededError
from .marker import Marker
from .pressure import compute_pressures, select_action
from .tool_registry import ActionResult, Decision, ToolRegistry


TERMINAL_STATES = {"terminal", "skipped", "escalated"}


class StigmergicAgent:
    """Homogeneous role-free agent guided by environmental pressure."""

    def __init__(
        self,
        *,
        agent_id: str,
        tool_registry: ToolRegistry,
        config: dict[str, Any],
        rng: random.Random | None = None,
    ) -> None:
        self.agent_id = agent_id
        self.tool_registry = tool_registry
        self.config = config
        self.rng = rng or random.Random()

    async def perceive_and_decide(
        self,
        snapshot: EnvironmentSnapshot,
    ) -> Decision | None:
        """Build one decision from current snapshot."""
        action_types = self.tool_registry.action_types()
        if not action_types:
            return None

        candidates = self._candidate_markers(snapshot=snapshot)
        if not candidates:
            return None

        pressure_weights = self.config.get("pressures", {}).get("default_weights", {})
        pressure_formula = str(
            self.config.get("pressures", {}).get("formula", "simple")
        )
        pressure_alpha = float(self.config.get("pressures", {}).get("alpha", 1.0))
        pressure_beta = float(self.config.get("pressures", {}).get("beta", 1.0))
        inhibition_threshold = float(
            self.config.get("markers", {}).get("inhibition_threshold", 1.0)
        )
        pressures = compute_pressures(
            markers=candidates,
            action_types=action_types,
            weights=pressure_weights,
            inhibition_threshold=inhibition_threshold,
            formula=pressure_formula,
            alpha=pressure_alpha,
            beta=pressure_beta,
        )

        temperature = float(
            self.config.get("agents", {}).get("selection_temperature", 0.1)
        )
        action_type = select_action(
            pressures=pressures, temperature=temperature, rng=self.rng
        )
        if action_type is None:
            return None

        eligible = [
            marker
            for marker in candidates
            if action_type in marker.payload.get("eligible_actions", [])
        ]
        if not eligible:
            return None

        target = sorted(
            eligible,
            key=lambda marker: (-marker.intensity, marker.inhibition, marker.id),
        )[0]

        return Decision(
            agent_id=self.agent_id,
            action_type=action_type,
            marker_id=target.id,
            target=target.target,
            pressures=pressures,
            selected_pressure=float(pressures.get(action_type, 0.0)),
        )

    async def execute(
        self,
        decision: Decision,
        environment: Environment,
        llm_client: Any | None = None,
    ) -> ActionResult:
        """Execute selected tool and persist updates through environment."""
        tool = self.tool_registry.get(decision.action_type)
        marker = environment.store.get_marker(decision.marker_id)
        if marker is None:
            return ActionResult(
                action_type=decision.action_type,
                metadata={"failed": True, "reason": "marker_not_found"},
            )

        if marker.lock_owner not in {None, self.agent_id}:
            return ActionResult(
                action_type=decision.action_type,
                metadata={"failed": True, "reason": "lock_conflict"},
            )

        try:
            result = await tool.execute(
                agent_id=self.agent_id,
                marker=marker,
                environment=environment,
                llm_client=llm_client,
            )
            environment.apply_action_result(agent_id=self.agent_id, result=result)
            return result
        except BudgetExceededError:
            raise
        except Exception as exc:  # noqa: BLE001
            return ActionResult(
                action_type=decision.action_type,
                metadata={"failed": True, "error": str(exc)},
            )

    def _candidate_markers(self, snapshot: EnvironmentSnapshot) -> list[Marker]:
        inhibition_threshold = float(
            self.config.get("markers", {}).get("inhibition_threshold", 1.0)
        )
        candidates: list[Marker] = []
        terminal_ids = {
            marker.id
            for marker in snapshot.markers
            if marker.state in TERMINAL_STATES
        }

        for marker in snapshot.markers:
            if marker.state in TERMINAL_STATES:
                continue
            if marker.lock_owner not in {None, self.agent_id}:
                continue
            if marker.inhibition >= inhibition_threshold:
                continue

            eligible_actions = self.tool_registry.eligible_actions_for(marker)
            raw_allowed_actions = marker.payload.get("eligible_actions")
            if (
                isinstance(raw_allowed_actions, (list, tuple, set))
                and len(raw_allowed_actions) > 0
            ):
                allowed_set = {str(action) for action in raw_allowed_actions}
                eligible_actions = [
                    action for action in eligible_actions if action in allowed_set
                ]
            if not eligible_actions:
                continue

            candidate = Marker.from_dict(marker.to_dict())
            candidate.payload = dict(candidate.payload)
            candidate.payload["eligible_actions"] = list(eligible_actions)
            candidates.append(candidate)

        return unblocked_markers(markers=candidates, terminal_ids=terminal_ids)
