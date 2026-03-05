"""Dependency graph helpers for marker DAG coordination."""

from __future__ import annotations

from collections import deque

from .marker import Marker


def validate_dag(markers: list[Marker]) -> bool:
    """Return True when marker dependencies form an acyclic graph."""
    try:
        _ = topological_sort(markers)
    except ValueError:
        return False
    return True


def build_dependency_graph(markers: list[Marker]) -> dict[str, list[str]]:
    """Build adjacency map where key node points to dependent child nodes."""
    marker_ids = {marker.id for marker in markers}
    adjacency: dict[str, list[str]] = {marker.id: [] for marker in markers}

    for marker in markers:
        for dependency_id in depends_on_ids(marker):
            if dependency_id not in marker_ids:
                continue
            adjacency.setdefault(dependency_id, [])
            adjacency[dependency_id].append(marker.id)

    for node, neighbors in adjacency.items():
        adjacency[node] = sorted(set(neighbors))
    return adjacency


def topological_sort(markers: list[Marker]) -> list[str]:
    """Return marker IDs ordered by dependency constraints.

    Raises ValueError when a cycle is detected.
    """
    adjacency = build_dependency_graph(markers)
    indegree = {node: 0 for node in adjacency}
    marker_ids = set(indegree.keys())

    for marker in markers:
        for dependency_id in depends_on_ids(marker):
            if dependency_id in marker_ids:
                indegree[marker.id] = indegree.get(marker.id, 0) + 1

    queue: deque[str] = deque(sorted(node for node, degree in indegree.items() if degree == 0))
    ordered: list[str] = []

    while queue:
        node = queue.popleft()
        ordered.append(node)
        for child_id in adjacency.get(node, []):
            indegree[child_id] -= 1
            if indegree[child_id] == 0:
                queue.append(child_id)

    if len(ordered) != len(marker_ids):
        raise ValueError("Dependency graph contains a cycle")

    return ordered


def unblocked_markers(markers: list[Marker], terminal_ids: set[str]) -> list[Marker]:
    """Return markers whose dependency IDs are all present in terminal_ids."""
    marker_ids = {marker.id for marker in markers}
    unblocked: list[Marker] = []

    for marker in markers:
        dependencies = depends_on_ids(marker)
        if not dependencies:
            unblocked.append(marker)
            continue

        all_satisfied = True
        for dependency_id in dependencies:
            if dependency_id not in marker_ids and dependency_id not in terminal_ids:
                all_satisfied = False
                break
            if dependency_id not in terminal_ids:
                all_satisfied = False
                break
        if all_satisfied:
            unblocked.append(marker)

    return unblocked


def depends_on_ids(marker: Marker) -> list[str]:
    """Return normalized dependency IDs from marker payload."""
    raw = marker.payload.get("depends_on")
    if not isinstance(raw, list):
        return []
    return [str(item).strip() for item in raw if str(item).strip()]
