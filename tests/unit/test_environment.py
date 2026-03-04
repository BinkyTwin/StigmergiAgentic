"""Unit tests for environment maintenance behavior."""

from __future__ import annotations

from core.environment import Environment
from core.marker import Marker
from core.marker_store import MarkerStore


def _marker(marker_id: str, intensity: float) -> Marker:
    return Marker(
        id=marker_id,
        marker_type="task",
        target=marker_id,
        intensity=intensity,
        state="pending",
        payload={},
        created_by="seed",
        created_at="2026-03-04T12:00:00+00:00",
        updated_by="seed",
        updated_at="2026-03-04T12:00:00+00:00",
    )


def test_environment_maintain_reports_pruned_markers_once(tmp_path, config_dict: dict) -> None:
    config = dict(config_dict)
    config["markers"] = dict(config_dict["markers"])
    config["markers"]["prune_threshold"] = 0.9

    store = MarkerStore(db_path=tmp_path / "pheromones" / "markers.db")
    store.upsert_marker(_marker("m1", intensity=0.2), agent_id="seed")

    env = Environment(store=store, config=config)
    result = env.maintain(current_tick=1)

    assert result["pruned_markers"] == 1
    assert env.pruned_markers == 1
    assert store.get_marker("m1") is None
