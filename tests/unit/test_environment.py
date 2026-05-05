"""Unit tests for environment maintenance behavior."""

from __future__ import annotations

from core.environment import Environment
from core.marker import Marker
from core.marker_store import MarkerStore
from core.tool_registry import ActionResult, RepairRequest, ValidationResult


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


def test_environment_deposits_lesson_marker_on_successful_terminal_state(
    tmp_path,
    config_dict: dict,
) -> None:
    store = MarkerStore(db_path=tmp_path / "pheromones" / "markers.db")
    seed = _marker("m-terminal", intensity=1.0)
    seed.state = "verified"
    store.upsert_marker(seed, agent_id="seed")
    env = Environment(store=store, config=config_dict)

    terminal = Marker.from_dict(seed.to_dict())
    terminal.state = "terminal"
    terminal.payload = {"task": "Search hotels cheaply", "failure_reason": "ok"}

    env.apply_action_result(
        agent_id="agent-1",
        result=ActionResult(
            action_type="search_hotels",
            marker_updates=[terminal],
            metadata={"quality_score": 0.95},
        ),
    )

    lesson = store.get_marker("lesson::m-terminal")
    assert lesson is not None
    assert lesson.payload["source_state"] == "terminal"


def test_environment_waits_for_validation_before_learning_plan_terminal(
    tmp_path,
    config_dict: dict,
) -> None:
    store = MarkerStore(db_path=tmp_path / "pheromones" / "markers.db")
    seed = _marker("plan", intensity=1.0)
    seed.state = "verified"
    store.upsert_marker(seed, agent_id="seed")
    env = Environment(store=store, config=config_dict)

    terminal = Marker.from_dict(seed.to_dict())
    terminal.state = "terminal"
    terminal.payload = {"plan": [{"current_city": "A"}], "failure_reason": "ok"}

    env.apply_action_result(
        agent_id="agent-1",
        result=ActionResult(
            action_type="plan_itinerary",
            marker_updates=[terminal],
            metadata={"quality_score": 0.95},
        ),
    )

    assert store.get_marker("lesson::plan") is None


def test_environment_does_not_promote_lesson_on_failed_validation(
    tmp_path,
    config_dict: dict,
) -> None:
    config = dict(config_dict)
    config["skill_library"] = dict(config_dict["skill_library"])
    config["skill_library"]["enabled"] = True
    config["reinforcement"] = dict(config_dict["reinforcement"])
    config["reinforcement"]["promotion_min_uses"] = 1

    store = MarkerStore(db_path=tmp_path / "pheromones" / "markers.db")
    skills_store = MarkerStore(db_path=tmp_path / "pheromones" / "skills.db")
    lesson = Marker(
        id="lesson::failed",
        marker_type="lesson",
        target="query",
        intensity=0.8,
        state="terminal",
        payload={"lesson": "Do not learn from failed validation", "usage_count": 0},
        created_by="seed",
        created_at="2026-03-04T12:00:00+00:00",
        updated_by="seed",
        updated_at="2026-03-04T12:00:00+00:00",
    )
    store.upsert_marker(marker=lesson, agent_id="seed")
    env = Environment(
        store=store,
        config=config,
        skills_store=skills_store,
        adapter_name="travelplanner",
    )

    failed = _marker("validate", intensity=1.0)
    failed.state = "active"
    store.upsert_marker(failed, agent_id="seed")
    terminal = Marker.from_dict(failed.to_dict())
    terminal.state = "completed"

    env.apply_action_result(
        agent_id="agent-1",
        result=ActionResult(
            action_type="validate_constraints",
            marker_updates=[terminal],
            metadata={
                "quality_score": 0.95,
                "final_pass": False,
                "credited_lesson_ids": ["lesson::failed"],
            },
        ),
    )

    assert skills_store.query_markers(marker_type="skill") == []


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


def test_environment_deposits_targeted_repair_marker_when_enabled(
    tmp_path,
    config_dict: dict,
) -> None:
    config = dict(config_dict)
    config["orchestrator"] = dict(config_dict["orchestrator"])
    config["orchestrator"]["targeted_repair"] = {
        "enabled": True,
        "max_cycles": 2,
        "repair_marker_intensity": 0.95,
    }

    store = MarkerStore(db_path=tmp_path / "pheromones" / "markers.db")
    plan_marker = _marker("plan", intensity=0.7)
    plan_marker.payload = {
        "query_data": {"days": 3},
        "plan": [],
        "eligible_actions": ["plan_itinerary"],
    }
    validate_marker = _marker("validate", intensity=0.8)
    validate_marker.payload = {"depends_on": ["plan"]}
    store.upsert_marker(plan_marker, agent_id="seed")
    store.upsert_marker(validate_marker, agent_id="seed")
    env = Environment(store=store, config=config)

    updated_validate = Marker.from_dict(validate_marker.to_dict())

    env.apply_action_result(
        agent_id="agent-1",
        result=ActionResult(
            action_type="validate_constraints",
            marker_updates=[updated_validate],
            validation=ValidationResult(
                status="failed",
                source_marker_id="validate",
                targets=["plan"],
                feedback=["Fix the invalid breakfast venue."],
                repair=RepairRequest(
                    target_marker_id="plan",
                    attempt=1,
                    max_attempts=2,
                    eligible_actions=["plan_itinerary"],
                ),
            ),
        ),
    )

    repair_marker = store.get_marker("repair::validate::plan::attempt::1")
    assert repair_marker is not None
    assert repair_marker.marker_type == "repair"
    assert repair_marker.state == "pending"
    assert repair_marker.payload["repair_target_id"] == "plan"
    assert repair_marker.payload["validation_feedback"] == [
        "Fix the invalid breakfast venue."
    ]
