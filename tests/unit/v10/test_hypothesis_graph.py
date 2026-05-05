from __future__ import annotations

import json

import pytest

from core_v10.contracts import (
    Candidate,
    CandidateKind,
    FeedbackDigest,
    ValidationResult,
    ValidationStatus,
    WorkspaceHandle,
)
from core_v10.hypothesis_graph import (
    HypothesisGraph,
    HypothesisScore,
    HypothesisStatus,
)


def make_candidate(candidate_id: str, parent_id: str | None = None) -> Candidate:
    return Candidate(
        candidate_id=candidate_id,
        kind=CandidateKind.PATCH,
        payload={"files": ["example.py"]},
        origin="unit-test",
        parent_id=parent_id,
    )


def test_hypothesis_graph_tracks_parent_child_lineage() -> None:
    graph = HypothesisGraph()
    graph.add_candidate(make_candidate("h-root"))
    graph.add_candidate(
        make_candidate("h-repair", parent_id="h-root"),
        parent_id="h-root",
    )

    assert [node.hypothesis_id for node in graph.children_of("h-root")] == [
        "h-repair"
    ]
    assert [node.hypothesis_id for node in graph.lineage("h-repair")] == [
        "h-root",
        "h-repair",
    ]


def test_hypothesis_graph_rejects_duplicate_and_unknown_parent() -> None:
    graph = HypothesisGraph()
    graph.add_candidate(make_candidate("h-root"))

    with pytest.raises(ValueError, match="duplicate hypothesis id"):
        graph.add_candidate(make_candidate("h-root"))

    with pytest.raises(ValueError, match="unknown parent hypothesis id"):
        graph.add_candidate(make_candidate("h-child"), parent_id="missing")


def test_hypothesis_graph_attaches_validation_feedback_and_selects_best() -> None:
    graph = HypothesisGraph()
    graph.add_candidate(make_candidate("h-low"))
    graph.add_candidate(make_candidate("h-high"))

    graph.attach_validation(
        "h-low",
        ValidationResult(
            candidate_id="h-low",
            status=ValidationStatus.PASSED,
            validator_name="unit",
        ),
        score=HypothesisScore(quality=0.5, confidence=0.5, cost=0.2, risk=0.1),
    )
    graph.attach_validation(
        "h-high",
        ValidationResult(
            candidate_id="h-high",
            status=ValidationStatus.PASSED,
            validator_name="unit",
        ),
        score=HypothesisScore(quality=0.9, confidence=0.6, cost=0.1, risk=0.1),
    )
    graph.attach_feedback(
        "h-low",
        FeedbackDigest(
            candidate_id="h-low",
            failure_type="test_failure",
            severity="blocking",
            summary="failed after local validation",
        ),
    )

    selected = graph.select_best()

    assert selected is not None
    assert selected.hypothesis_id == "h-high"
    assert selected.status == HypothesisStatus.SELECTED
    assert graph.get("h-low").feedback is not None


def test_hypothesis_graph_tracks_applied_workspace(tmp_path) -> None:
    graph = HypothesisGraph()
    graph.add_candidate(make_candidate("h-root"))
    workspace = WorkspaceHandle(root=tmp_path / "branch-a", instance_id="inst-001")

    node = graph.attach_workspace("h-root", workspace)

    assert node.workspace == workspace
    assert graph.to_dict()["nodes"][0]["workspace"]["root"].endswith("branch-a")


def test_hypothesis_graph_selection_is_filtered_and_idempotent() -> None:
    graph = HypothesisGraph()
    graph.add_candidate(make_candidate("h-old"))
    graph.add_candidate(make_candidate("h-new"))
    for hypothesis_id, quality in (("h-old", 1.0), ("h-new", 0.1)):
        graph.attach_validation(
            hypothesis_id,
            ValidationResult(
                candidate_id=hypothesis_id,
                status=ValidationStatus.PASSED,
                validator_name="unit",
            ),
            score=HypothesisScore(quality=quality),
        )

    first = graph.select_best(["h-new"])
    second = graph.select_best(["h-new"])

    assert first is not None
    assert second is not None
    assert first.hypothesis_id == "h-new"
    assert second.hypothesis_id == "h-new"
    assert graph.get("h-old").status == HypothesisStatus.VALIDATED
    assert graph.get("h-new").status == HypothesisStatus.SELECTED


def test_hypothesis_graph_exports_deterministic_json() -> None:
    graph = HypothesisGraph()
    graph.add_candidate(make_candidate("h-root"))

    data = json.loads(graph.to_json())

    assert data["nodes"][0]["hypothesis_id"] == "h-root"
    assert data["nodes"][0]["status"] == "open"
