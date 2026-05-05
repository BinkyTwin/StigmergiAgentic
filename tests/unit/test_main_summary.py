"""Unit tests for run summary rendering in CLI entrypoint."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from core.marker import Marker
from main import _build_run_summary


def test_build_run_summary_includes_llm_metadata() -> None:
    summary = _build_run_summary(
        adapter_name="travelplanner",
        objective_id="travelplanner::query-0",
        session_id="session-123",
        store=SimpleNamespace(db_path=Path("/tmp/markers.db")),
        result=SimpleNamespace(
            stop_reason="all_terminal",
            total_ticks=4,
            final_snapshot=SimpleNamespace(markers=["m1", "m2"]),
            emergence_summary={"parallel_utilization": 0.5},
        ),
        environment=SimpleNamespace(
            tokens_used=42,
            cost_used=0.12,
            reinforcement_events=3,
            propagation_events=1,
            pruned_markers=2,
        ),
        agents=[SimpleNamespace(), SimpleNamespace()],
        evaluation={"final_pass_rate": 1.0},
        dag_info={"valid": True},
        assistant_response="plan ready",
        config={"llm": {"provider": "openrouter", "model": "qwen/qwen3.5-9b"}},
    )

    assert summary["adapter"] == "travelplanner"
    assert summary["llm_provider"] == "openrouter"
    assert summary["llm_model"] == "qwen/qwen3.5-9b"
    assert summary["markers"] == 2
    assert summary["reinforcement"] == {"events": 3, "propagation_events": 1}


def test_build_run_summary_falls_back_to_plan_marker_artifact() -> None:
    plan_marker = Marker(
        id="travelplanner::query::plan_itinerary",
        marker_type="task",
        target="plan",
        intensity=1.0,
        state="terminal",
        payload={
            "query_data": {"query_idx": 7},
            "plan": [
                {
                    "current_city": "Myrtle Beach",
                    "transportation": "-",
                    "breakfast": "Cafe A, Myrtle Beach",
                    "attraction": "Beach, Myrtle Beach",
                    "lunch": "Cafe B, Myrtle Beach",
                    "dinner": "Cafe C, Myrtle Beach",
                    "accommodation": "Hotel A, Myrtle Beach",
                }
            ],
            "evaluation": {
                "final_pass": True,
                "raw_final_pass": True,
                "strict_final_pass": True,
            },
        },
        created_by="test",
        created_at="2026-04-25T00:00:00+00:00",
        updated_by="test",
        updated_at="2026-04-25T00:00:00+00:00",
    )
    finalize_marker = Marker(
        id="travelplanner::query::finalize",
        marker_type="task",
        target="final",
        intensity=1.0,
        state="terminal",
        payload={
            "query_data": {"query_idx": 7},
            "final_plan": [],
            "failure_reason": "ok",
        },
        created_by="test",
        created_at="2026-04-25T00:00:00+00:00",
        updated_by="test",
        updated_at="2026-04-25T00:00:00+00:00",
    )

    summary = _build_run_summary(
        adapter_name="travelplanner",
        objective_id="travelplanner::query-7",
        session_id="session-123",
        store=SimpleNamespace(db_path=Path("/tmp/markers.db")),
        result=SimpleNamespace(
            stop_reason="all_terminal",
            total_ticks=4,
            final_snapshot=SimpleNamespace(markers=[plan_marker, finalize_marker]),
            emergence_summary={},
        ),
        environment=SimpleNamespace(
            tokens_used=42,
            cost_used=0.12,
            reinforcement_events=3,
            propagation_events=1,
            pruned_markers=2,
        ),
        agents=[SimpleNamespace()],
        evaluation={"final_pass_rate": 1.0},
        dag_info={"valid": True},
        assistant_response="No travel plan generated.",
        config={"llm": {"provider": "openrouter", "model": "google/gemma-4-31b-it"}},
    )

    assert summary["artifact_delivered"] is True
    assert summary["final_pass"] is True
    assert summary["strict_final_pass"] is True
    assert summary["query_idx"] == 7
    assert len(summary["final_plan"]) == 1
