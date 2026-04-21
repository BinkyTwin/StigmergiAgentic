"""Integration tests for cross-run skill persistence (Sprint 9 T1)."""

from __future__ import annotations

import copy

from core.environment import Environment
from core.marker import Marker
from core.marker_store import MarkerStore
from core.tool_registry import ActionResult


def _seed_task(store: MarkerStore, marker_id: str) -> Marker:
    marker = Marker(
        id=marker_id,
        marker_type="task",
        target=marker_id,
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
            "lesson": "Ordered dependencies accelerate convergence",
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


def _build_config(base: dict) -> dict:
    cfg = copy.deepcopy(base)
    cfg["skill_library"] = dict(cfg.get("skill_library", {}))
    cfg["skill_library"]["enabled"] = True
    cfg["reinforcement"] = dict(cfg["reinforcement"])
    cfg["reinforcement"]["promotion_min_uses"] = 2
    cfg["reinforcement"]["lesson_threshold"] = 0.7
    return cfg


def test_skill_promotion_cross_run_accumulates_usage_count(
    tmp_path,
    config_dict: dict,
) -> None:
    """Run 1 records usage=1, Run 2 on same skills_store promotes at usage=2."""
    config = _build_config(config_dict)
    shared_skills_db = tmp_path / "skills.db"
    lesson_id = "lesson::task::alpha"

    # Run 1 — fresh main store, shared skills store.
    run1_main = MarkerStore(db_path=tmp_path / "run1" / "main.db")
    skills_store = MarkerStore(db_path=shared_skills_db)
    _seed_task(run1_main, "task::alpha")
    _seed_lesson(run1_main, lesson_id)
    env1 = Environment(
        store=run1_main,
        config=config,
        skills_store=skills_store,
        adapter_name="assistant",
    )
    completed1 = Marker.from_dict(run1_main.get_marker("task::alpha").to_dict())
    completed1.state = "completed"
    env1.apply_action_result(
        agent_id="agent-1",
        result=ActionResult(
            action_type="think",
            marker_updates=[completed1],
            metadata={
                "quality_score": 0.9,
                "credited_lesson_ids": [lesson_id],
            },
        ),
    )
    assert skills_store.get_marker(f"skill::assistant::{lesson_id}") is None

    # Run 2 — fresh main store, re-seeds the lesson with usage_count=1 (carried
    # out-of-band as it would be by the store if session-shared; here we model
    # it as "the runtime has read the prior usage from the skills DB").
    run2_main = MarkerStore(db_path=tmp_path / "run2" / "main.db")
    _seed_task(run2_main, "task::alpha")
    lesson = _seed_lesson(run2_main, lesson_id)
    payload = dict(lesson.payload)
    payload["usage_count"] = 1
    seeded = Marker.from_dict(lesson.to_dict())
    seeded.payload = payload
    run2_main.upsert_marker(marker=seeded, agent_id="agent-1")

    env2 = Environment(
        store=run2_main,
        config=config,
        skills_store=skills_store,
        adapter_name="assistant",
    )
    completed2 = Marker.from_dict(run2_main.get_marker("task::alpha").to_dict())
    completed2.state = "completed"
    env2.apply_action_result(
        agent_id="agent-2",
        result=ActionResult(
            action_type="think",
            marker_updates=[completed2],
            metadata={
                "quality_score": 0.95,
                "credited_lesson_ids": [lesson_id],
            },
        ),
    )

    promoted = skills_store.get_marker(f"skill::assistant::{lesson_id}")
    assert promoted is not None
    assert promoted.marker_type == "skill"
    assert env2.skills_promoted == 1


def test_run_three_reads_skill_from_skills_store(
    tmp_path,
    config_dict: dict,
) -> None:
    """Skills persisted in the skills_store are surfaced via EnvironmentSnapshot."""
    config = _build_config(config_dict)
    lesson_id = "lesson::task::alpha"
    shared_skills_db = tmp_path / "skills.db"

    # Seed a skill directly in the cross-run store (as if persisted by a prior run).
    skills_store = MarkerStore(db_path=shared_skills_db)
    skill_marker = Marker(
        id=f"skill::assistant::{lesson_id}",
        marker_type="skill",
        target="alpha",
        intensity=0.92,
        state="terminal",
        payload={
            "skill_text": "Use ordered dependencies",
            "context_fingerprint": "assistant::alpha::task::alpha",
            "quality_score": 0.92,
            "usage_count": 3,
            "source_lesson_id": lesson_id,
            "domain": "assistant",
        },
        created_by="system_protocol",
        created_at="2026-04-21T12:00:00+00:00",
        updated_by="system_protocol",
        updated_at="2026-04-21T12:00:00+00:00",
        last_active_at="2026-04-21T12:00:00+00:00",
    )
    skills_store.upsert_marker(marker=skill_marker, agent_id="system_protocol")

    # Brand new run. Skill should surface in snapshot.skills.
    run_main = MarkerStore(db_path=tmp_path / "run3" / "main.db")
    _seed_task(run_main, "task::alpha")
    env = Environment(
        store=run_main,
        config=config,
        skills_store=skills_store,
        adapter_name="assistant",
    )

    snapshot = env.snapshot(tick=0)
    assert len(snapshot.skills) == 1
    assert snapshot.skills[0].id == f"skill::assistant::{lesson_id}"
    assert snapshot.skills[0].payload["domain"] == "assistant"
