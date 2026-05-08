"""Agent local views over a V12 stigmergic medium.

The V12 medium stores guidance gradients. It never creates patches and never
selects tool parameters for the agent.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable

from core_v10.contracts import FeedbackDigest, to_jsonable
from core_v10.event_log import JsonlEventLog


JsonDict = dict[str, Any]

MEDIUM_UPDATED_EVENT = "medium.updated"
PHEROMONE_READ_EVENT = "pheromone.read"
AGENT_LOCAL_VIEW_CREATED_EVENT = "agent.local_view.created"


@dataclass(frozen=True)
class Pheromone:
    """One guidance marker readable by an autonomous agent."""

    pheromone_id: str
    kind: str
    target: str
    intensity: float
    reason: str
    evidence: tuple[str, ...] = ()
    metadata: JsonDict = field(default_factory=dict)

    def to_dict(self) -> JsonDict:
        return to_jsonable(asdict(self))


@dataclass(frozen=True)
class AgentLocalView:
    """The only V12 stigmergic payload shown to an autonomous agent."""

    objective: str
    migration_context: JsonDict
    current_best: JsonDict | None = None
    recent_failures: tuple[JsonDict, ...] = ()
    hot_files: tuple[str, ...] = ()
    tool_registry: tuple[str, ...] = ()
    tool_annotations: dict[str, JsonDict] = field(default_factory=dict)
    forbidden_tools: dict[str, str] = field(default_factory=dict)
    supported_tools: tuple[str, ...] = ()
    inhibited_tools: tuple[str, ...] = ()
    supported_actions: tuple[str, ...] = ()
    anti_actions: tuple[str, ...] = ()
    relevant_pheromones: tuple[JsonDict, ...] = ()
    candidate_history: tuple[JsonDict, ...] = ()

    def to_dict(self) -> JsonDict:
        return to_jsonable(asdict(self))


class V12StigmergicMedium:
    """Replay-friendly V12 guidance medium.

    This class intentionally has no method that returns a patch, edit set, or
    candidate. It can only store feedback-derived guidance and expose local
    views to an agent.
    """

    def __init__(self) -> None:
        self._pheromones: dict[str, Pheromone] = {}
        self._recent_failures: list[JsonDict] = []
        self._hot_files: set[str] = set()
        self._candidate_history: list[JsonDict] = []
        self._tool_history: list[JsonDict] = []
        self._created_patch_count = 0

    @property
    def created_patch_count(self) -> int:
        """Return the number of patches created by the medium: always zero."""

        return self._created_patch_count

    def update_from_feedback(
        self,
        feedback: FeedbackDigest | JsonDict,
        *,
        event_log: JsonlEventLog | None = None,
        run_id: str = "v12",
        instance_id: str = "unknown",
        actor: str = "v12_medium",
    ) -> tuple[Pheromone, ...]:
        """Convert verifier feedback into guidance pheromones."""

        payload = _feedback_to_dict(feedback)
        self._recent_failures.append(payload)
        self._recent_failures = self._recent_failures[-8:]
        for location in payload.get("locations") or []:
            if isinstance(location, dict) and location.get("path"):
                self._hot_files.add(str(location["path"]))

        created: list[Pheromone] = []
        for spec in _pheromone_specs_for_feedback(payload):
            pheromone = Pheromone(**spec)
            self._pheromones[pheromone.pheromone_id] = pheromone
            created.append(pheromone)
        if event_log is not None:
            event_log.append(
                run_id=run_id,
                instance_id=instance_id,
                event_type=MEDIUM_UPDATED_EVENT,
                actor=actor,
                payload={
                    "feedback": payload,
                    "created_pheromones": [item.to_dict() for item in created],
                    "medium_created_patch_count": self.created_patch_count,
                },
            )
        return tuple(created)

    def record_candidate(self, candidate: JsonDict) -> None:
        """Record candidate metadata for future local views."""

        self._candidate_history.append(dict(candidate))
        self._candidate_history = self._candidate_history[-16:]

    def record_tool_outcome(self, outcome: JsonDict) -> None:
        """Record tool outcome metadata for future guidance annotations."""

        self._tool_history.append(dict(outcome))
        self._tool_history = self._tool_history[-32:]

    def local_view(
        self,
        *,
        objective: str,
        migration_context: JsonDict | Any,
        current_best: JsonDict | None = None,
        tool_registry: Iterable[str] = (),
        forbidden_tools: dict[str, str] | None = None,
        event_log: JsonlEventLog | None = None,
        run_id: str = "v12",
        instance_id: str = "unknown",
        actor: str = "v12_agent",
    ) -> AgentLocalView:
        """Return a bounded local view and optionally log the pheromone read."""

        context_payload = (
            migration_context.to_dict()
            if hasattr(migration_context, "to_dict")
            else dict(migration_context or {})
        )
        pheromones = sorted(
            self._pheromones.values(),
            key=lambda item: (-item.intensity, item.pheromone_id),
        )[:12]
        supported_tools = _targets(pheromones, prefix="tool:", kind="support")
        inhibited_tools = _targets(pheromones, prefix="tool:", kind="inhibit")
        supported_actions = _targets(pheromones, prefix="action:", kind="support")
        anti_actions = _targets(pheromones, prefix="action:", kind="inhibit")
        forbidden = dict(forbidden_tools or {})
        visible_tools = _visible_tool_registry(
            tool_registry=tool_registry,
            supported_tools=supported_tools,
            inhibited_tools=inhibited_tools,
            forbidden_tools=forbidden,
        )
        view = AgentLocalView(
            objective=objective,
            migration_context=context_payload,
            current_best=current_best,
            recent_failures=tuple(self._recent_failures[-5:]),
            hot_files=tuple(sorted(self._hot_files)),
            tool_registry=visible_tools,
            tool_annotations=_tool_annotations(
                pheromones=pheromones,
                tool_registry=visible_tools,
                candidate_history=self._candidate_history,
                tool_history=self._tool_history,
            ),
            forbidden_tools=forbidden,
            supported_tools=supported_tools,
            inhibited_tools=inhibited_tools,
            supported_actions=supported_actions,
            anti_actions=anti_actions,
            relevant_pheromones=tuple(item.to_dict() for item in pheromones),
            candidate_history=tuple(self._candidate_history[-8:]),
        )
        if event_log is not None:
            event_log.append(
                run_id=run_id,
                instance_id=instance_id,
                event_type=PHEROMONE_READ_EVENT,
                actor=actor,
                payload={
                    "pheromone_ids": [item.pheromone_id for item in pheromones],
                    "tool_registry": list(visible_tools),
                    "tool_annotations": view.tool_annotations,
                    "forbidden_tools": view.forbidden_tools,
                },
            )
            event_log.append(
                run_id=run_id,
                instance_id=instance_id,
                event_type=AGENT_LOCAL_VIEW_CREATED_EVENT,
                actor=actor,
                payload={"local_view": view.to_dict()},
            )
        return view


def _feedback_to_dict(feedback: FeedbackDigest | JsonDict) -> JsonDict:
    if isinstance(feedback, FeedbackDigest):
        return to_jsonable(feedback)
    return dict(feedback)


def _pheromone_specs_for_feedback(payload: JsonDict) -> list[JsonDict]:
    failure_type = str(payload.get("failure_type") or "unknown")
    summary = str(payload.get("summary") or failure_type)
    evidence = tuple(str(item) for item in payload.get("evidence") or [] if item)
    specs: list[tuple[str, str, float]] = []
    if failure_type in {"compile_error", "class_version_error"}:
        specs.extend(
            [
                ("support", "tool:read_file", 0.8),
                ("support", "tool:search_repo", 0.7),
                ("support", "tool:inspect_pom", 0.7),
                ("support", "action:inspect_before_edit", 0.9),
            ]
        )
    if failure_type == "dependency_resolution_error":
        specs.extend(
            [
                ("support", "tool:inspect_pom", 0.9),
                ("support", "tool:search_repo", 0.6),
                ("inhibit", "action:guess_dependency_without_evidence", 0.8),
            ]
        )
    if failure_type in {"test_failure", "official_eval_failed"}:
        specs.extend(
            [
                ("support", "tool:run_tests", 0.7),
                ("support", "tool:run_official_eval", 0.6),
                ("support", "tool:suggest_surefire_upgrade", 0.6),
                ("inhibit", "action:delete_or_disable_tests", 1.0),
            ]
        )
    for action in payload.get("anti_actions") or []:
        specs.append(("inhibit", f"action:{action}", 0.9))
    for action in payload.get("recommended_next_actions") or []:
        if isinstance(action, dict) and action.get("action_type"):
            specs.append(("support", f"action:{action['action_type']}", 0.7))

    if not specs:
        specs.append(("support", "tool:read_file", 0.5))
    return [
        {
            "pheromone_id": _pheromone_id(kind, target, failure_type, summary),
            "kind": kind,
            "target": target,
            "intensity": intensity,
            "reason": failure_type,
            "evidence": evidence,
            "metadata": {"summary": summary, "failure_type": failure_type},
        }
        for kind, target, intensity in specs
    ]


def _pheromone_id(kind: str, target: str, failure_type: str, summary: str) -> str:
    digest = hashlib.sha1(
        f"{kind}|{target}|{failure_type}|{summary}".encode()
    ).hexdigest()[:10]
    return f"phr_{digest}"


def _targets(
    pheromones: Iterable[Pheromone],
    *,
    prefix: str,
    kind: str,
) -> tuple[str, ...]:
    values = {
        item.target[len(prefix) :]
        for item in pheromones
        if item.kind == kind and item.target.startswith(prefix)
    }
    return tuple(sorted(values))


def _visible_tool_registry(
    *,
    tool_registry: Iterable[str],
    supported_tools: Iterable[str],
    inhibited_tools: Iterable[str],
    forbidden_tools: dict[str, str],
) -> tuple[str, ...]:
    tools = {str(name) for name in tool_registry if str(name)}
    if not tools:
        tools.update(str(name) for name in supported_tools if str(name))
        tools.update(str(name) for name in inhibited_tools if str(name))
    tools.difference_update(forbidden_tools)
    return tuple(sorted(tools))


def _tool_annotations(
    *,
    pheromones: Iterable[Pheromone],
    tool_registry: Iterable[str],
    candidate_history: Iterable[JsonDict],
    tool_history: Iterable[JsonDict],
) -> dict[str, JsonDict]:
    pheromone_list = tuple(pheromones)
    candidate_history_list = tuple(candidate_history)
    tool_history_list = tuple(dict(item) for item in tool_history)
    annotations: dict[str, JsonDict] = {}
    for tool_name in tool_registry:
        tool = str(tool_name)
        support_markers = _tool_markers(pheromone_list, tool=tool, kind="support")
        inhibition_markers = _tool_markers(pheromone_list, tool=tool, kind="inhibit")
        support = max((item.intensity for item in support_markers), default=0.0)
        inhibition = max((item.intensity for item in inhibition_markers), default=0.0)
        history_guidance = _tool_history_guidance(
            tool=tool,
            tool_history=tool_history_list,
        )
        support = max(support, float(history_guidance.get("support") or 0.0))
        inhibition = max(
            inhibition,
            float(history_guidance.get("inhibition") or 0.0),
        )
        reason = _annotation_reason(support_markers, inhibition_markers)
        history_reason = str(history_guidance.get("reason") or "")
        if history_reason:
            reason = (
                f"{reason}; {history_reason}"
                if reason != "no active medium annotation"
                else history_reason
            )
        evidence = _annotation_evidence(support_markers, inhibition_markers)
        evidence.extend(str(item) for item in history_guidance.get("evidence") or ())
        annotations[tool] = {
            "support": round(float(support), 4),
            "inhibition": round(float(inhibition), 4),
            "risk": _risk_for_tool(tool, inhibition=inhibition),
            "recommendation": _recommendation(
                support=support,
                inhibition=inhibition,
            ),
            "reason": reason,
            "evidence": sorted(set(evidence)),
            "recent_outcomes": _recent_tool_outcomes(
                candidate_history_list,
                tool_history_list,
                tool,
            ),
        }
    return annotations


def _tool_markers(
    pheromones: Iterable[Pheromone],
    *,
    tool: str,
    kind: str,
) -> tuple[Pheromone, ...]:
    target = f"tool:{tool}"
    return tuple(item for item in pheromones if item.kind == kind and item.target == target)


def _recommendation(*, support: float, inhibition: float) -> str:
    if inhibition >= 0.7:
        return "inhibited"
    if inhibition >= 0.4:
        return "caution"
    if support >= 0.75:
        return "strong_support"
    if support >= 0.4:
        return "support"
    return "neutral"


def _risk_for_tool(tool: str, *, inhibition: float) -> str:
    if inhibition >= 0.7 or tool == "apply_patch":
        return "high"
    if tool in {"edit_file_guarded", "run_maven", "run_tests", "run_official_eval"}:
        return "medium"
    if inhibition >= 0.4:
        return "medium"
    return "low"


def _annotation_reason(
    support_markers: Iterable[Pheromone],
    inhibition_markers: Iterable[Pheromone],
) -> str:
    parts: list[str] = []
    for marker in tuple(support_markers)[:2]:
        parts.append(f"support:{marker.reason}")
    for marker in tuple(inhibition_markers)[:2]:
        parts.append(f"inhibit:{marker.reason}")
    return "; ".join(parts) if parts else "no active medium annotation"


def _annotation_evidence(
    support_markers: Iterable[Pheromone],
    inhibition_markers: Iterable[Pheromone],
) -> list[str]:
    evidence: list[str] = []
    for marker in (*tuple(support_markers), *tuple(inhibition_markers)):
        evidence.extend(str(item) for item in marker.evidence if item)
        evidence.append(marker.pheromone_id)
    return sorted(set(evidence))


def _recent_tool_outcomes(
    candidate_history: Iterable[JsonDict],
    tool_history: Iterable[JsonDict],
    tool: str,
) -> list[JsonDict]:
    outcomes: list[JsonDict] = []
    for item in tool_history:
        if str(item.get("tool_name") or "") != tool:
            continue
        outcomes.append(
            {
                "step_index": item.get("step_index"),
                "status": item.get("status"),
                "summary": item.get("summary"),
                "candidate_created": bool(item.get("candidate_created")),
                "proposal_kind": item.get("proposal_kind"),
            }
        )
    for item in candidate_history:
        if str(item.get("tool_name") or "") != tool:
            continue
        outcomes.append(
            {
                "candidate_id": item.get("candidate_id"),
                "status": item.get("status"),
                "summary": item.get("summary"),
            }
        )
    return outcomes[-3:]


def _tool_history_guidance(
    *,
    tool: str,
    tool_history: Iterable[JsonDict],
) -> JsonDict:
    history = tuple(dict(item) for item in tool_history)
    if not history:
        return {}
    recent = history[-8:]
    recent_candidate = any(bool(item.get("candidate_created")) for item in recent[-3:])
    success_count = sum(
        1
        for item in history
        if str(item.get("tool_name") or "") == tool
        and str(item.get("status") or "") == "success"
    )
    proposal_ready = any(
        str(item.get("status") or "") == "success"
        and (
            str(item.get("tool_name") or "").startswith("suggest_")
            or bool(item.get("proposal_kind"))
        )
        for item in recent[-5:]
    )
    evidence_reads = sum(
        1
        for item in recent[-5:]
        if str(item.get("status") or "") == "success"
        and str(item.get("tool_name") or "")
        in {"inspect_pom", "read_file", "search_repo"}
    )
    reasons: list[str] = []
    evidence: list[str] = []
    support = 0.0
    inhibition = 0.0
    if tool == "edit_file_guarded" and not recent_candidate:
        if proposal_ready:
            support = max(support, 0.82)
            reasons.append("support:proposal_ready_use_guarded_edit_if_justified")
        elif evidence_reads >= 2:
            support = max(support, 0.68)
            reasons.append("support:inspection_evidence_available_for_guarded_edit")
    if tool.startswith("suggest_") and success_count >= 1 and not recent_candidate:
        inhibition = max(inhibition, 0.5)
        reasons.append("inhibit:proposal_already_returned")
    elif tool == "inspect_pom" and success_count >= 1 and not recent_candidate:
        inhibition = max(inhibition, 0.45)
        reasons.append("inhibit:repeated_pom_inspection")
    elif tool in {"read_file", "search_repo"} and success_count >= 2 and not recent_candidate:
        inhibition = max(inhibition, 0.42)
        reasons.append("inhibit:repeated_non_mutating_inspection")
    if reasons:
        for item in recent:
            if str(item.get("tool_name") or "") == tool or (
                tool == "edit_file_guarded"
                and str(item.get("status") or "") == "success"
                and str(item.get("tool_name") or "")
                in {
                    "inspect_pom",
                    "read_file",
                    "search_repo",
                    "suggest_maven_compiler_config",
                    "suggest_lombok_upgrade",
                    "suggest_surefire_upgrade",
                    "suggest_javafx_dependencies",
                    "suggest_base64_rewrite",
                }
            ):
                evidence.append(f"tool_outcome:{item.get('step_index')}")
    return {
        "support": support,
        "inhibition": inhibition,
        "reason": "; ".join(reasons),
        "evidence": tuple(evidence),
    }


__all__ = [
    "AGENT_LOCAL_VIEW_CREATED_EVENT",
    "MEDIUM_UPDATED_EVENT",
    "PHEROMONE_READ_EVENT",
    "AgentLocalView",
    "Pheromone",
    "V12StigmergicMedium",
]
