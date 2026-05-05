"""Reconstructible V10 blackboard projection."""

from __future__ import annotations

from dataclasses import dataclass, field

from pathlib import Path

from core_v10.contracts import (
    Candidate,
    CandidateKind,
    FeedbackDigest,
    JsonDict,
    ValidationResult,
    ValidationStatus,
    WorkspaceHandle,
    to_jsonable,
)
from core_v10.event_log import EventRecord, ReplaySnapshot, replay_events
from core_v10.hypothesis_graph import (
    HypothesisGraph,
    HypothesisNode,
    HypothesisStatus,
)
from core_v10.signals import CoordinationSignal, SignalKind, clamp_intensity


@dataclass(frozen=True)
class BlackboardSnapshot:
    """Current active projection used by strategies and future roles."""

    run_id: str | None
    instance_id: str | None
    event_count: int
    counts_by_type: dict[str, int]
    open_hypotheses: tuple[str, ...] = ()
    validated_hypotheses: tuple[str, ...] = ()
    failed_hypotheses: tuple[str, ...] = ()
    selected_hypothesis_id: str | None = None
    recent_feedback: tuple[FeedbackDigest, ...] = ()
    signals: tuple[CoordinationSignal, ...] = ()
    metrics: JsonDict = field(default_factory=dict)

    def signals_by_kind(self, kind: SignalKind) -> tuple[CoordinationSignal, ...]:
        """Return active signals of one type."""

        return tuple(signal for signal in self.signals if signal.kind == kind)

    def to_dict(self) -> JsonDict:
        """Return a JSON-friendly blackboard representation."""

        return {
            "run_id": self.run_id,
            "instance_id": self.instance_id,
            "event_count": self.event_count,
            "counts_by_type": self.counts_by_type,
            "open_hypotheses": list(self.open_hypotheses),
            "validated_hypotheses": list(self.validated_hypotheses),
            "failed_hypotheses": list(self.failed_hypotheses),
            "selected_hypothesis_id": self.selected_hypothesis_id,
            "recent_feedback": [to_jsonable(item) for item in self.recent_feedback],
            "signals": [signal.to_dict() for signal in self.signals],
            "metrics": to_jsonable(self.metrics),
        }


def build_blackboard(
    *,
    events: list[EventRecord],
    graph: HypothesisGraph | None = None,
    max_recent_feedback: int = 5,
) -> BlackboardSnapshot:
    """Build a blackboard from source-of-truth events and hypothesis graph."""

    replay = replay_events(events)
    graph = graph or graph_from_events(events)
    nodes = graph.nodes()
    selected = next(
        (
            node.hypothesis_id
            for node in nodes
            if node.status == HypothesisStatus.SELECTED
        ),
        None,
    )
    feedback = tuple(
        node.feedback
        for node in nodes
        if node.feedback is not None
    )[-max_recent_feedback:]

    return BlackboardSnapshot(
        run_id=replay.run_id,
        instance_id=_single_instance_id(events),
        event_count=replay.event_count,
        counts_by_type=replay.counts_by_type,
        open_hypotheses=tuple(
            node.hypothesis_id
            for node in nodes
            if node.status in {HypothesisStatus.OPEN, HypothesisStatus.APPLIED}
        ),
        validated_hypotheses=tuple(
            node.hypothesis_id
            for node in nodes
            if node.status in {HypothesisStatus.VALIDATED, HypothesisStatus.SELECTED}
        ),
        failed_hypotheses=tuple(
            node.hypothesis_id
            for node in nodes
            if node.status in {HypothesisStatus.FAILED, HypothesisStatus.DISCARDED}
        ),
        selected_hypothesis_id=selected,
        recent_feedback=feedback,
        signals=tuple(_signals_from_nodes(nodes)),
        metrics=_metrics_from_graph(nodes, replay),
    )


def _signals_from_nodes(nodes: list[HypothesisNode]) -> list[CoordinationSignal]:
    signals: list[CoordinationSignal] = []
    for node in nodes:
        if node.status in {HypothesisStatus.VALIDATED, HypothesisStatus.SELECTED}:
            signals.append(
                CoordinationSignal(
                    kind=SignalKind.SUPPORT,
                    target=f"candidate:{node.candidate.kind.value}",
                    intensity=clamp_intensity(0.6 + node.score.total / 10.0),
                    source="validation",
                    hypothesis_id=node.hypothesis_id,
                    rationale="validated hypothesis supports similar candidates",
                )
            )
            signals.append(
                CoordinationSignal(
                    kind=SignalKind.REINFORCE,
                    target=f"origin:{node.candidate.origin}",
                    intensity=clamp_intensity(0.5 + node.score.confidence / 2.0),
                    source=(
                        "selection"
                        if node.status == HypothesisStatus.SELECTED
                        else "validation"
                    ),
                    hypothesis_id=node.hypothesis_id,
                    rationale="successful origin should remain visible",
                )
            )
        if node.status in {HypothesisStatus.FAILED, HypothesisStatus.DISCARDED}:
            failure_type = (
                node.feedback.failure_type
                if node.feedback is not None
                else "unknown_failure"
            )
            signals.append(
                CoordinationSignal(
                    kind=SignalKind.INHIBIT,
                    target=f"failure:{failure_type}",
                    intensity=(
                        0.8
                        if node.feedback and node.feedback.is_blocking
                        else 0.5
                    ),
                    source="feedback",
                    hypothesis_id=node.hypothesis_id,
                    rationale="failed hypothesis should suppress repeated errors",
                )
            )
    if len(nodes) > 1:
        signals.append(
            CoordinationSignal(
                kind=SignalKind.NOVELTY,
                target="hypothesis_space",
                intensity=clamp_intensity(len(nodes) / 10.0),
                source="hypothesis_graph",
                rationale="multiple branches are active in the search space",
                metadata={"hypothesis_count": len(nodes)},
            )
        )
    return signals


def _metrics_from_graph(
    nodes: list[HypothesisNode], replay: ReplaySnapshot
) -> JsonDict:
    root_count = sum(1 for node in nodes if node.parent_id is None)
    child_count = max(0, len(nodes) - root_count)
    max_depth = 0
    by_id = {node.hypothesis_id: node for node in nodes}
    for node in nodes:
        depth = 0
        current = node
        while current.parent_id and current.parent_id in by_id:
            depth += 1
            current = by_id[current.parent_id]
        max_depth = max(max_depth, depth)
    return {
        "hypothesis_count": len(nodes),
        "branching_factor": child_count / root_count if root_count else 0.0,
        "lineage_depth": max_depth,
        "validation_events": replay.counts_by_type.get("validation.completed", 0),
        "feedback_events": replay.counts_by_type.get("feedback.created", 0),
    }


def _single_instance_id(events: list[EventRecord]) -> str | None:
    instance_ids = {event.instance_id for event in events}
    return next(iter(instance_ids)) if len(instance_ids) == 1 else None


def graph_from_events(events: list[EventRecord]) -> HypothesisGraph:
    """Reconstruct a hypothesis graph from V10 verifier events."""

    graph = HypothesisGraph()
    selected_id: str | None = None
    for event in sorted(events, key=lambda item: item.sequence):
        if event.event_type == "candidate.created":
            candidate_data = event.payload.get("candidate")
            if isinstance(candidate_data, dict):
                candidate = _candidate_from_dict(candidate_data)
                graph.add_candidate(
                    candidate,
                    hypothesis_id=event.hypothesis_id or candidate.candidate_id,
                    parent_id=candidate.parent_id,
                )
        elif event.event_type == "candidate.applied" and event.hypothesis_id:
            apply_data = event.payload.get("apply_result")
            workspace_data = (
                apply_data.get("workspace")
                if isinstance(apply_data, dict)
                else None
            )
            if isinstance(workspace_data, dict):
                graph.attach_workspace(
                    event.hypothesis_id,
                    _workspace_from_dict(workspace_data),
                )
        elif event.event_type == "validation.completed" and event.hypothesis_id:
            validation_data = event.payload.get("validation")
            if isinstance(validation_data, dict):
                graph.attach_validation(
                    event.hypothesis_id,
                    _validation_from_dict(validation_data),
                )
        elif event.event_type == "feedback.created" and event.hypothesis_id:
            feedback_data = event.payload.get("feedback")
            if isinstance(feedback_data, dict):
                graph.attach_feedback(
                    event.hypothesis_id,
                    _feedback_from_dict(feedback_data),
                )
        elif event.event_type == "run.completed":
            raw_selected = event.payload.get("selected_hypothesis_id")
            selected_id = str(raw_selected) if raw_selected else None
    if selected_id:
        graph.select_best([selected_id])
    return graph


def _candidate_from_dict(data: JsonDict) -> Candidate:
    return Candidate(
        candidate_id=str(data["candidate_id"]),
        kind=CandidateKind(str(data["kind"])),
        payload=dict(data.get("payload") or {}),
        origin=str(data["origin"]),
        parent_id=data.get("parent_id"),
        metadata=dict(data.get("metadata") or {}),
    )


def _workspace_from_dict(data: JsonDict) -> WorkspaceHandle:
    return WorkspaceHandle(
        root=Path(str(data["root"])),
        instance_id=str(data["instance_id"]),
        metadata=dict(data.get("metadata") or {}),
    )


def _validation_from_dict(data: JsonDict) -> ValidationResult:
    return ValidationResult(
        candidate_id=str(data["candidate_id"]),
        status=ValidationStatus(str(data["status"])),
        validator_name=str(data["validator_name"]),
        signals=dict(data.get("signals") or {}),
        summary=str(data.get("summary") or ""),
        raw_output=str(data.get("raw_output") or ""),
        errors=list(data.get("errors") or []),
        metadata=dict(data.get("metadata") or {}),
    )


def _feedback_from_dict(data: JsonDict) -> FeedbackDigest:
    return FeedbackDigest(
        candidate_id=str(data["candidate_id"]),
        failure_type=str(data["failure_type"]),
        severity=str(data["severity"]),
        summary=str(data["summary"]),
        locations=list(data.get("locations") or []),
        evidence=list(data.get("evidence") or []),
        candidate_causes=list(data.get("candidate_causes") or []),
        recommended_next_actions=list(data.get("recommended_next_actions") or []),
        anti_actions=list(data.get("anti_actions") or []),
        metadata=dict(data.get("metadata") or {}),
    )
