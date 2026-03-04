"""Unit tests for marker dependency DAG utilities."""

from __future__ import annotations

import pytest

from core.dependency import (
    build_dependency_graph,
    topological_sort,
    unblocked_markers,
    validate_dag,
)
from core.marker import Marker


def _marker(marker_id: str, depends_on: list[str] | None = None) -> Marker:
    payload = {}
    if depends_on is not None:
        payload["depends_on"] = depends_on
    return Marker(
        id=marker_id,
        marker_type="task",
        target=marker_id,
        intensity=1.0,
        state="pending",
        payload=payload,
        created_by="seed",
        created_at="2026-03-04T10:00:00+00:00",
        updated_by="seed",
        updated_at="2026-03-04T10:00:00+00:00",
    )


def test_validate_dag_accepts_acyclic_graph() -> None:
    markers = [_marker("a"), _marker("b", ["a"]), _marker("c", ["b"])]
    assert validate_dag(markers) is True


def test_validate_dag_detects_cycle() -> None:
    markers = [_marker("a", ["b"]), _marker("b", ["a"])]
    assert validate_dag(markers) is False


def test_unblocked_markers_filters_by_terminal_dependencies() -> None:
    markers = [_marker("a"), _marker("b", ["a"]), _marker("c", ["b"])]
    first = unblocked_markers(markers, terminal_ids=set())
    second = unblocked_markers(markers, terminal_ids={"a"})

    assert [marker.id for marker in first] == ["a"]
    assert [marker.id for marker in second] == ["a", "b"]


def test_topological_sort_empty_graph() -> None:
    assert topological_sort([]) == []


def test_topological_sort_single_node() -> None:
    assert topological_sort([_marker("solo")]) == ["solo"]


def test_build_graph_and_sort_diamond_dependency() -> None:
    markers = [
        _marker("a"),
        _marker("b", ["a"]),
        _marker("c", ["a"]),
        _marker("d", ["b", "c"]),
    ]
    graph = build_dependency_graph(markers)
    ordered = topological_sort(markers)

    assert graph["a"] == ["b", "c"]
    assert ordered.index("a") < ordered.index("b")
    assert ordered.index("a") < ordered.index("c")
    assert ordered.index("b") < ordered.index("d")
    assert ordered.index("c") < ordered.index("d")

    cyclical = [_marker("x", ["y"]), _marker("y", ["x"])]
    with pytest.raises(ValueError):
        topological_sort(cyclical)
