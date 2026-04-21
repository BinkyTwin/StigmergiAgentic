"""Unit tests for Sprint 9 skill promotion in Environment.apply_action_result."""

from __future__ import annotations

from pathlib import Path

import copy

from core.environment import Environment
from core.marker import Marker
from core.marker_store import MarkerStore
from core.tool_registry import ActionResult


def _seed_task(store: MarkerStore) -> Marker:
    marker = Marker(
        id="task::alpha",
        marker_type="task",
        target="alpha",
        intensity=1.0,
        state="active",
        payload={"task": "plan alpha"},
        created_by="seed",
        created_at="2026-04-21T12:00:00+00:00",
        updated_by="seed",
        updated_at="2026-04-21T12:00:00+00:00",
    )
    return store.upsert_marker(marker=marker, agent_id="seed")


def _seed_lesson(store: MarkerStore, lesson_id: str) -> Marker:
    lesson = Marker(
        id=lesson_id,
        marker_type="lesson",
        target="alpha",
        intensity=0.8,
        state="terminal",
        payload={
            "lesson": "Prefer explicit dependency ordering",
            "source_marker": "task::alpha",
            "source_agent": "agent-1",
            "usage_count": 0,
        },
        created_by="agent-1",
        created_at="2026-04-21T12:00:01+00:00",
        updated_by="agent-1",
        updated_at="2026-04-21T12:00:01+00:00",
    )
    return store.upsert_marker(marker=lesson, agent_id="agent-1")


def _enable_skill_library(config: dict) -> dict:
    cfg = copy.deepcopy(config)
    cfg["skill_library"] = dict(cfg.get("skill_library", {}))
    cfg["skill_library"]["enabled"] = True
    cfg["skill_library"]["read_only"] = False
    return cfg


def test_no_promotion_without_credited_lessons(tmp_path, config_dict: dict) -> None:
    config = _enable_skill_library(config_dict)
    store = MarkerStore(db_path=tmp_path / "main.db")
    skills_store = MarkerStore(db_path=tmp_path / "skills.db")
    _seed_task(store)
    _seed_lesson(store, "lesson::task::alpha")
    env = Environment(
        store=store,
        config=config,
        skills_store=skills_store,
        adapter_name="assistant",
    )

    completed = Marker.from_dict(store.get_marker("task::alpha").to_dict())
    completed.state = "completed"
    env.apply_action_result(
        agent_id="agent-1",
        result=ActionResult(
            action_type="think",
            marker_updates=[completed],
            metadata={"quality_score": 0.95},
        ),
    )

    assert skills_store.get_marker("skill::assistant::lesson::task::alpha") is None


def test_no_promotion_below_promotion_min_uses(tmp_path, config_dict: dict) -> None:
    config = _enable_skill_library(config_dict)
    config["reinforcement"] = dict(config["reinforcement"])
    config["reinforcement"]["promotion_min_uses"] = 2
    store = MarkerStore(db_path=tmp_path / "main.db")
    skills_store = MarkerStore(db_path=tmp_path / "skills.db")
    _seed_task(store)
    _seed_lesson(store, "lesson::task::alpha")
    env = Environment(
        store=store,
        config=config,
        skills_store=skills_store,
        adapter_name="assistant",
    )

    completed = Marker.from_dict(store.get_marker("task::alpha").to_dict())
    completed.state = "completed"
    env.apply_action_result(
        agent_id="agent-1",
        result=ActionResult(
            action_type="think",
            marker_updates=[completed],
            metadata={
                "quality_score": 0.95,
                "credited_lesson_ids": ["lesson::task::alpha"],
            },
        ),
    )

    lesson = store.get_marker("lesson::task::alpha")
    assert lesson is not None
    assert int(lesson.payload.get("usage_count", 0)) == 1
    assert skills_store.get_marker("skill::assistant::lesson::task::alpha") is None


def test_promotes_skill_at_threshold(tmp_path, config_dict: dict) -> None:
    config = _enable_skill_library(config_dict)
    config["reinforcement"] = dict(config["reinforcement"])
    config["reinforcement"]["promotion_min_uses"] = 2
    store = MarkerStore(db_path=tmp_path / "main.db")
    skills_store = MarkerStore(db_path=tmp_path / "skills.db")
    _seed_task(store)
    lesson = _seed_lesson(store, "lesson::task::alpha")
    lesson_payload = dict(lesson.payload)
    lesson_payload["usage_count"] = 1
    bumped = Marker.from_dict(lesson.to_dict())
    bumped.payload = lesson_payload
    store.upsert_marker(marker=bumped, agent_id="agent-1")

    env = Environment(
        store=store,
        config=config,
        skills_store=skills_store,
        adapter_name="assistant",
    )

    completed = Marker.from_dict(store.get_marker("task::alpha").to_dict())
    completed.state = "completed"
    env.apply_action_result(
        agent_id="agent-2",
        result=ActionResult(
            action_type="think",
            marker_updates=[completed],
            metadata={
                "quality_score": 0.92,
                "credited_lesson_ids": ["lesson::task::alpha"],
            },
        ),
    )

    # With meta-skill grouping, skill_id is based on context fingerprint.
    # Find any promoted skill (should be exactly 1)
    all_skills = skills_store.query_markers(marker_type="skill")
    assert len(all_skills) == 1
    promoted = all_skills[0]
    assert promoted.marker_type == "skill"
    assert promoted.state == "terminal"
    assert promoted.payload["domain"] == "assistant"
    assert int(promoted.payload.get("usage_count", 0)) >= 2
    assert float(promoted.intensity) > 0.0
    assert env.skills_promoted == 1


def test_skill_library_read_only_blocks_promotion(
    tmp_path,
    config_dict: dict,
) -> None:
    config = _enable_skill_library(config_dict)
    config["skill_library"]["read_only"] = True
    store = MarkerStore(db_path=tmp_path / "main.db")
    skills_store = MarkerStore(db_path=tmp_path / "skills.db")
    _seed_task(store)
    lesson = _seed_lesson(store, "lesson::task::alpha")
    bumped_payload = dict(lesson.payload)
    bumped_payload["usage_count"] = 1
    bumped = Marker.from_dict(lesson.to_dict())
    bumped.payload = bumped_payload
    store.upsert_marker(marker=bumped, agent_id="agent-1")

    env = Environment(
        store=store,
        config=config,
        skills_store=skills_store,
        adapter_name="assistant",
    )

    completed = Marker.from_dict(store.get_marker("task::alpha").to_dict())
    completed.state = "completed"
    env.apply_action_result(
        agent_id="agent-2",
        result=ActionResult(
            action_type="think",
            marker_updates=[completed],
            metadata={
                "quality_score": 0.95,
                "credited_lesson_ids": ["lesson::task::alpha"],
            },
        ),
    )

    assert skills_store.get_marker("skill::assistant::lesson::task::alpha") is None


def test_no_promotion_when_quality_below_threshold(
    tmp_path,
    config_dict: dict,
) -> None:
    config = _enable_skill_library(config_dict)
    config["reinforcement"] = dict(config["reinforcement"])
    config["reinforcement"]["promotion_min_uses"] = 1
    config["reinforcement"]["lesson_threshold"] = 0.7
    store = MarkerStore(db_path=tmp_path / "main.db")
    skills_store = MarkerStore(db_path=tmp_path / "skills.db")
    _seed_task(store)
    _seed_lesson(store, "lesson::task::alpha")

    env = Environment(
        store=store,
        config=config,
        skills_store=skills_store,
        adapter_name="assistant",
    )

    completed = Marker.from_dict(store.get_marker("task::alpha").to_dict())
    completed.state = "completed"
    env.apply_action_result(
        agent_id="agent-1",
        result=ActionResult(
            action_type="think",
            marker_updates=[completed],
            metadata={
                "quality_score": 0.5,
                "credited_lesson_ids": ["lesson::task::alpha"],
            },
        ),
    )

    assert skills_store.get_marker("skill::assistant::lesson::task::alpha") is None
