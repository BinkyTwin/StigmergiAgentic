"""Unit tests for the LangGraph TravelPlanner supervisor baseline."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

from adapters.travelplanner.adapter import TravelPlannerAdapter
from adapters.travelplanner.langgraph_supervisor import (
    AccommodationPlanOutput,
    AttractionPlanOutput,
    LangGraphTravelPlannerRunner,
    RestaurantPlanOutput,
    RoutePlanOutput,
)
from core.schemas import TravelItineraryOutput
from scripts.render_travelplanner_comparison_table import build_rows, render_markdown
from travelplanner_data import sample_query_rows, sample_valid_plan, write_sample_database


class FakeLangGraphLLM:
    """Deterministic fake LLM for LangGraph supervisor tests."""

    def __init__(self) -> None:
        self.total_tokens_used = 0
        self.total_cost_usd = 0.0

    def call(self, prompt: str, system: str | None = None, response_schema=None) -> SimpleNamespace:
        del prompt, system
        if response_schema is RoutePlanOutput:
            payload = {
                "outbound_transportation": "Flight Number: F3792603, from Washington to Myrtle Beach",
                "return_transportation": "Flight Number: F3791200, from Myrtle Beach to Washington",
                "rationale": "Use the available round-trip flights.",
            }
        elif response_schema is AccommodationPlanOutput:
            payload = {
                "accommodation": "Private Room A, Myrtle Beach",
                "rationale": "Matches the query constraints.",
            }
        elif response_schema is RestaurantPlanOutput:
            payload = {
                "days": [
                    {"day": 1, "breakfast": "-", "lunch": "-", "dinner": "-"},
                    {"day": 2, "breakfast": "Exotic India, Myrtle Beach", "lunch": "Seafood Place, Myrtle Beach", "dinner": "Cafe Blue, Myrtle Beach"},
                    {"day": 3, "breakfast": "-", "lunch": "-", "dinner": "-"},
                ],
                "rationale": "Meals are concentrated on the stay day.",
            }
        elif response_schema is AttractionPlanOutput:
            payload = {
                "days": [
                    {"day": 1, "attraction": "-"},
                    {"day": 2, "attraction": "Broadway at the Beach, Myrtle Beach"},
                    {"day": 3, "attraction": "-"},
                ],
                "rationale": "One attraction on the stay day.",
            }
        elif response_schema is TravelItineraryOutput:
            payload = {"plan": sample_valid_plan()}
        else:
            raise AssertionError(f"Unexpected response schema: {response_schema}")

        self.total_tokens_used += 11
        self.total_cost_usd += 0.0011
        return SimpleNamespace(
            content=json.dumps(payload),
            tokens_used=11,
            cost_usd=0.0011,
            model="fake-langgraph-model",
            latency_ms=1,
            parsed=response_schema.model_validate(payload),
        )


def _build_langgraph_runtime(tmp_path: Path, config_dict: dict) -> tuple[dict, TravelPlannerAdapter, object]:
    config = copy.deepcopy(config_dict)
    config["travelplanner"] = {
        "database_path": str(write_sample_database(tmp_path / "database")),
        "dataset_split": "validation",
        "query_rows": sample_query_rows(),
        "default_query_idx": 0,
    }
    adapter = TravelPlannerAdapter(config=config)
    workspace = adapter.create_workspace(config)
    objective = adapter.create_objective({"objective": "Query 0", "query_idx": 0}, config)
    return config, adapter, workspace, objective


def test_langgraph_supervisor_query_export_contract(tmp_path: Path, config_dict: dict) -> None:
    config, _, workspace, objective = _build_langgraph_runtime(tmp_path, config_dict)
    runner = LangGraphTravelPlannerRunner(
        config=config,
        workspace=workspace,
        llm_client=FakeLangGraphLLM(),
        max_validation_retries=2,
    )

    payload = runner.run_query(
        objective=objective.description,
        objective_id=objective.objective_id,
        query_idx=0,
        query_data=dict(objective.payload["query_data"]),
    )

    assert set(payload.keys()) >= {
        "status",
        "query_idx",
        "objective",
        "assistant_response",
        "evaluation",
        "final_pass",
        "final_plan",
        "summary",
    }
    assert payload["status"] == "ok"
    assert payload["query_idx"] == 0
    assert payload["final_pass"] is True
    assert payload["summary"]["framework"] == "langgraph_supervisor"
    assert payload["summary"]["retry_count"] == 0
    assert payload["summary"]["coordination_overhead"] >= 9
    assert len(payload["summary"]["step_trace"]) >= 9


def test_langgraph_runs_json_is_compatible_with_official_scorer(tmp_path: Path, config_dict: dict) -> None:
    config, _, workspace, objective = _build_langgraph_runtime(tmp_path, config_dict)
    runner = LangGraphTravelPlannerRunner(
        config=config,
        workspace=workspace,
        llm_client=FakeLangGraphLLM(),
        max_validation_retries=2,
    )
    payload = runner.run_query(
        objective=objective.description,
        objective_id=objective.objective_id,
        query_idx=0,
        query_data=dict(objective.payload["query_data"]),
    )

    runs_json = tmp_path / "runs.json"
    official_json = tmp_path / "official_eval.json"
    runs_json.write_text(json.dumps({"runs": [payload]}, indent=2) + "\n", encoding="utf-8")

    command = [
        sys.executable,
        "scripts/eval_travelplanner_official.py",
        "--runs-json",
        str(runs_json),
        "--database-root",
        str(tmp_path / "database"),
        "--split",
        "validation",
        "--out",
        str(official_json),
    ]
    completed = subprocess.run(
        command,
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr

    payload = json.loads(official_json.read_text(encoding="utf-8"))
    assert payload["predicted_queries"] == [0]
    assert payload["scores"]["evaluated_queries"] == 180
    assert "final_pass_rate" in payload["scores"]


def test_comparison_table_renders_langgraph_row(tmp_path: Path) -> None:
    eval_paths: list[tuple[str, Path]] = []
    for label, final_score in [
        ("Solo", 0.1),
        ("LangGraph Supervisor", 0.2),
        ("StigmergiAgentic", 0.3),
    ]:
        path = tmp_path / f"{label.lower().replace(' ', '_')}.json"
        path.write_text(
            json.dumps(
                {
                    "scores": {
                        "delivery_rate": 0.5,
                        "commonsense_micro": 0.4,
                        "commonsense_macro": 0.3,
                        "hard_constraint_micro": 0.2,
                        "hard_constraint_macro": 0.1,
                        "final_pass_rate": final_score,
                    }
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        eval_paths.append((label, path))

    rows = build_rows([f"{label}={path}" for label, path in eval_paths])
    markdown = render_markdown(rows)

    assert len(rows) == 3
    assert "LangGraph Supervisor" in markdown
    assert "StigmergiAgentic" in markdown
