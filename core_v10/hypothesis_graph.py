"""Explicit hypothesis graph for V10 verified-resolution search."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable

from core_v10.contracts import (
    Candidate,
    FeedbackDigest,
    JsonDict,
    ValidationResult,
    ValidationStatus,
    WorkspaceHandle,
    to_jsonable,
)


class HypothesisStatus(str, Enum):
    """Lifecycle states for candidate hypotheses."""

    OPEN = "open"
    APPLIED = "applied"
    VALIDATED = "validated"
    FAILED = "failed"
    DISCARDED = "discarded"
    SELECTED = "selected"


@dataclass(frozen=True)
class HypothesisScore:
    """Comparable score used by deterministic selectors."""

    quality: float = 0.0
    confidence: float = 0.0
    cost: float = 0.0
    risk: float = 0.0

    @property
    def total(self) -> float:
        """Return a simple deterministic ranking score."""

        return self.quality + self.confidence - self.cost - self.risk

    def to_dict(self) -> JsonDict:
        """Return JSON-friendly score data."""

        return {
            "quality": self.quality,
            "confidence": self.confidence,
            "cost": self.cost,
            "risk": self.risk,
            "total": self.total,
        }


@dataclass
class HypothesisNode:
    """One candidate, branch, repair, or diagnostic node."""

    hypothesis_id: str
    candidate: Candidate
    parent_id: str | None = None
    status: HypothesisStatus = HypothesisStatus.OPEN
    score: HypothesisScore = field(default_factory=HypothesisScore)
    validation: ValidationResult | None = None
    feedback: FeedbackDigest | None = None
    workspace: WorkspaceHandle | None = None
    metadata: JsonDict = field(default_factory=dict)

    def to_dict(self) -> JsonDict:
        """Return a JSON-friendly node representation."""

        return {
            "hypothesis_id": self.hypothesis_id,
            "parent_id": self.parent_id,
            "status": self.status.value,
            "candidate": to_jsonable(self.candidate),
            "score": self.score.to_dict(),
            "validation": to_jsonable(self.validation)
            if self.validation is not None
            else None,
            "feedback": to_jsonable(self.feedback) if self.feedback else None,
            "workspace": to_jsonable(self.workspace) if self.workspace else None,
            "metadata": to_jsonable(self.metadata),
        }


class HypothesisGraph:
    """In-memory graph of candidate hypotheses and repair lineages."""

    def __init__(self) -> None:
        self._nodes: dict[str, HypothesisNode] = {}
        self._children: dict[str, list[str]] = {}

    def add_candidate(
        self,
        candidate: Candidate,
        *,
        hypothesis_id: str | None = None,
        parent_id: str | None = None,
        score: HypothesisScore | None = None,
        metadata: JsonDict | None = None,
    ) -> HypothesisNode:
        """Add a candidate hypothesis to the graph."""

        node_id = hypothesis_id or candidate.candidate_id
        if node_id in self._nodes:
            raise ValueError(f"duplicate hypothesis id: {node_id}")
        if parent_id is not None and parent_id not in self._nodes:
            raise ValueError(f"unknown parent hypothesis id: {parent_id}")

        node = HypothesisNode(
            hypothesis_id=node_id,
            candidate=candidate,
            parent_id=parent_id,
            score=score or HypothesisScore(),
            metadata=metadata or {},
        )
        self._nodes[node_id] = node
        if parent_id is not None:
            self._children.setdefault(parent_id, []).append(node_id)
        return node

    def mark_applied(self, hypothesis_id: str) -> HypothesisNode:
        """Mark a hypothesis as applied to a workspace/branch."""

        node = self.get(hypothesis_id)
        node.status = HypothesisStatus.APPLIED
        return node

    def attach_validation(
        self,
        hypothesis_id: str,
        validation: ValidationResult,
        *,
        score: HypothesisScore | None = None,
    ) -> HypothesisNode:
        """Attach validation output and update status."""

        node = self.get(hypothesis_id)
        node.validation = validation
        if score is not None:
            node.score = score
        if validation.status == ValidationStatus.PASSED:
            node.status = HypothesisStatus.VALIDATED
        elif validation.status in {ValidationStatus.FAILED, ValidationStatus.ERROR}:
            node.status = HypothesisStatus.FAILED
        else:
            node.status = HypothesisStatus.APPLIED
        return node

    def attach_feedback(
        self, hypothesis_id: str, feedback: FeedbackDigest
    ) -> HypothesisNode:
        """Attach structured feedback to a hypothesis."""

        node = self.get(hypothesis_id)
        node.feedback = feedback
        return node

    def attach_workspace(
        self, hypothesis_id: str, workspace: WorkspaceHandle
    ) -> HypothesisNode:
        """Attach the workspace where a hypothesis was actually applied."""

        node = self.get(hypothesis_id)
        node.workspace = workspace
        return node

    def discard(self, hypothesis_id: str, reason: str) -> HypothesisNode:
        """Discard a hypothesis with an auditable reason."""

        node = self.get(hypothesis_id)
        node.status = HypothesisStatus.DISCARDED
        node.metadata["discard_reason"] = reason
        return node

    def select_best(
        self, hypothesis_ids: Iterable[str] | None = None
    ) -> HypothesisNode | None:
        """Select the best validated node by deterministic evidence score."""

        allowed_ids = set(hypothesis_ids) if hypothesis_ids is not None else None
        candidates = [
            node
            for node in self._nodes.values()
            if node.status in {HypothesisStatus.VALIDATED, HypothesisStatus.SELECTED}
            and (allowed_ids is None or node.hypothesis_id in allowed_ids)
        ]
        if not candidates:
            return None
        best = max(
            candidates,
            key=lambda node: (node.score.total, node.score.quality, node.hypothesis_id),
        )
        for node in self._nodes.values():
            if node.status == HypothesisStatus.SELECTED:
                node.status = HypothesisStatus.VALIDATED
        best.status = HypothesisStatus.SELECTED
        return best

    def get(self, hypothesis_id: str) -> HypothesisNode:
        """Return one hypothesis node."""

        try:
            return self._nodes[hypothesis_id]
        except KeyError as exc:
            raise ValueError(f"unknown hypothesis id: {hypothesis_id}") from exc

    def children_of(self, hypothesis_id: str) -> list[HypothesisNode]:
        """Return child hypotheses in insertion order."""

        child_ids = self._children.get(hypothesis_id, [])
        return [self._nodes[node_id] for node_id in child_ids]

    def lineage(self, hypothesis_id: str) -> list[HypothesisNode]:
        """Return root-to-node lineage."""

        lineage: list[HypothesisNode] = []
        current: HypothesisNode | None = self.get(hypothesis_id)
        while current is not None:
            lineage.append(current)
            current = self._nodes.get(current.parent_id) if current.parent_id else None
        return list(reversed(lineage))

    def nodes(self) -> list[HypothesisNode]:
        """Return all nodes in insertion order."""

        return list(self._nodes.values())

    def to_dict(self) -> JsonDict:
        """Return a serializable graph representation."""

        return {
            "nodes": [node.to_dict() for node in self.nodes()],
            "edges": [
                {"parent_id": parent_id, "child_id": child_id}
                for parent_id, child_ids in self._children.items()
                for child_id in child_ids
            ],
        }

    def to_json(self) -> str:
        """Return deterministic JSON for reports and snapshots."""

        return json.dumps(self.to_dict(), indent=2, sort_keys=True)

    @classmethod
    def from_nodes(cls, nodes: Iterable[HypothesisNode]) -> HypothesisGraph:
        """Build a graph from existing nodes."""

        graph = cls()
        for node in nodes:
            graph.add_candidate(
                node.candidate,
                hypothesis_id=node.hypothesis_id,
                parent_id=node.parent_id,
                score=node.score,
                metadata=node.metadata,
            )
            graph._nodes[node.hypothesis_id].status = node.status
            graph._nodes[node.hypothesis_id].validation = node.validation
            graph._nodes[node.hypothesis_id].feedback = node.feedback
            graph._nodes[node.hypothesis_id].workspace = node.workspace
        return graph
