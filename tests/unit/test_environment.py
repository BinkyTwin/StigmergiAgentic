"""Unit tests for environment maintenance behavior."""

from __future__ import annotations

from core.environment import Environment
from core.marker import Marker
from core.marker_store import MarkerStore
from core.tool_registry import ActionResult


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


def test_environment_deposits_lesson_marker_on_high_quality_success(
    tmp_path,
    config_dict: dict,
) -> None:
    store = MarkerStore(db_path=tmp_path / "pheromones" / "markers.db")
    seed = _marker("m-success", intensity=1.0)
    seed.state = "active"
    store.upsert_marker(seed, agent_id="seed")
    env = Environment(store=store, config=config_dict)

    completed = Marker.from_dict(seed.to_dict())
    completed.state = "completed"
    completed.payload = {
        "task": "Write migration checklist",
        "last_thought": {"analysis": "Checklist-first execution reduces misses."},
    }

    env.apply_action_result(
        agent_id="agent-1",
        result=ActionResult(
            action_type="think",
            marker_updates=[completed],
            metadata={"quality_score": 0.95},
        ),
    )

    lesson = store.get_marker("lesson::m-success")
    assert lesson is not None
    assert lesson.marker_type == "lesson"
    assert lesson.state == "terminal"
    assert "source_marker" in lesson.payload


def test_environment_skips_lesson_marker_below_threshold(
    tmp_path,
    config_dict: dict,
) -> None:
    store = MarkerStore(db_path=tmp_path / "pheromones" / "markers.db")
    seed = _marker("m-low", intensity=1.0)
    seed.state = "active"
    store.upsert_marker(seed, agent_id="seed")
    env = Environment(store=store, config=config_dict)

    completed = Marker.from_dict(seed.to_dict())
    completed.state = "completed"
    completed.payload = {"task": "Low-signal completion"}

    env.apply_action_result(
        agent_id="agent-1",
        result=ActionResult(
            action_type="think",
            marker_updates=[completed],
            metadata={"quality_score": 0.4},
        ),
    )

    assert store.get_marker("lesson::m-low") is None


def test_environment_snapshot_applies_time_decay_without_mutating_store(
    tmp_path,
    config_dict: dict,
    monkeypatch,
) -> None:
    config = dict(config_dict)
    config["markers"] = dict(config_dict["markers"])
    config["markers"]["time_decay"] = {
        "enabled": True,
        "decay_period_seconds": 60.0,
    }
    config["markers"]["decay_rate"] = 0.1
    config["markers"]["default_decay_rate"] = 0.1

    store = MarkerStore(db_path=tmp_path / "pheromones" / "markers.db")
    marker = _marker("m-time", intensity=1.0)
    marker.last_active_at = "2026-03-04T12:00:00+00:00"
    store.upsert_marker(marker, agent_id="seed")
    env = Environment(store=store, config=config)

    monkeypatch.setattr("core.environment.utc_now_iso", lambda: "2026-03-04T12:02:00+00:00")

    snapshot = env.snapshot(tick=1)
    stored = store.get_marker("m-time")

    assert snapshot.markers[0].intensity < 1.0
    assert stored is not None
    assert stored.intensity == 1.0
