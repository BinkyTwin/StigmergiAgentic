"""Unit tests for run summary rendering in CLI entrypoint."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

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
