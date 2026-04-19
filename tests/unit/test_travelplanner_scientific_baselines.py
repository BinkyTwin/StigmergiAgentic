"""Unit tests for TravelPlanner scientific baselines and paper-pack generation."""

from __future__ import annotations

import copy
import csv
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

from adapters.travelplanner.adapter import TravelPlannerAdapter
from adapters.travelplanner.scientific_baselines import (
    PlannerExecutorBlueprintOutput,
    SelfRefineCritiqueOutput,
    TravelPlannerScientificBaselineRunner,
)
from core.schemas import TravelItineraryOutput
from travelplanner_data import sample_query_rows, sample_valid_plan, write_sample_database


class FakeScientificBaselineLLM:
    """Deterministic fake LLM for scientific-baseline tests."""

    def __init__(self) -> None:
        self.total_tokens_used = 0
        self.total_cost_usd = 0.0

    def call(self, prompt: str, system: str | None = None, response_schema=None) -> SimpleNamespace:
        del system
        if response_schema is TravelItineraryOutput:
            if "CurrentDraft" in prompt:
                payload = {"plan": sample_valid_plan()}
            elif "Produce a strong first draft" in prompt:
                draft = sample_valid_plan()
                draft[1]["lunch"] = draft[1]["breakfast"]
                payload = {"plan": draft}
            else:
                payload = {"plan": sample_valid_plan()}
        elif response_schema is SelfRefineCritiqueOutput:
            payload = {
                "issues": ["Restaurant repetition detected."],
                "repair_instructions": ["Replace the repeated lunch with another valid restaurant."],
            }
        elif response_schema is PlannerExecutorBlueprintOutput:
            payload = {
                "outbound_transportation": "Flight Number: F3792603, from Washington to Myrtle Beach",
                "return_transportation": "Flight Number: F3791200, from Myrtle Beach to Washington",
                "accommodation": "Private Room A, Myrtle Beach",
                "days": [
                    {"day": 1, "breakfast": "-", "lunch": "-", "dinner": "-", "attraction": "-"},
                    {
                        "day": 2,
                        "breakfast": "Exotic India, Myrtle Beach",
                        "lunch": "Seafood Place, Myrtle Beach",
                        "dinner": "Cafe Blue, Myrtle Beach",
                        "attraction": "Broadway at the Beach, Myrtle Beach",
                    },
                    {"day": 3, "breakfast": "-", "lunch": "-", "dinner": "-", "attraction": "-"},
                ],
            }
        else:
            raise AssertionError(f"Unexpected response schema: {response_schema}")

        self.total_tokens_used += 13
        self.total_cost_usd += 0.0013
        return SimpleNamespace(
            content=json.dumps(payload),
            tokens_used=13,
            cost_usd=0.0013,
            model="fake-scientific-model",
            latency_ms=1,
            parsed=response_schema.model_validate(payload),
            parsed_response=None,
        )


class FakeSelfRefineFallbackLLM(FakeScientificBaselineLLM):
    """LLM fixture that truncates the self-refine critique JSON."""

    def call(self, prompt: str, system: str | None = None, response_schema=None) -> SimpleNamespace:
        if response_schema is SelfRefineCritiqueOutput:
            del prompt, system
            self.total_tokens_used += 13
            self.total_cost_usd += 0.0013
            return SimpleNamespace(
                content='{"issues":["Restaurant repetition detected","Missing room check"',
                tokens_used=13,
                cost_usd=0.0013,
                model="fake-scientific-model",
                latency_ms=1,
                parsed=None,
                parsed_response=None,
            )
        return super().call(prompt=prompt, system=system, response_schema=response_schema)


class FakePlannerExecutorFallbackLLM(FakeScientificBaselineLLM):
    """LLM fixture that truncates the planner blueprint JSON."""

    def call(self, prompt: str, system: str | None = None, response_schema=None) -> SimpleNamespace:
        if response_schema is PlannerExecutorBlueprintOutput:
            del prompt, system
            self.total_tokens_used += 13
            self.total_cost_usd += 0.0013
            return SimpleNamespace(
                content='{"outbound_transportation":"Flight Number: F3792603, from Washington to Myrtle Beach","days":[{"day":1}',
                tokens_used=13,
                cost_usd=0.0013,
                model="fake-scientific-model",
                latency_ms=1,
                parsed=None,
                parsed_response=None,
            )
        return super().call(prompt=prompt, system=system, response_schema=response_schema)


class FakeTransientDraftFailureLLM(FakeScientificBaselineLLM):
    """LLM fixture that fails once on the first self-refine draft call."""

    def __init__(self) -> None:
        super().__init__()
        self._draft_failures = 0

    def call(self, prompt: str, system: str | None = None, response_schema=None) -> SimpleNamespace:
        if (
            response_schema is TravelItineraryOutput
            and "Produce a strong first draft" in prompt
            and self._draft_failures == 0
        ):
            del system
            self._draft_failures += 1
            raise ConnectionError("transient transport failure")
        return super().call(prompt=prompt, system=system, response_schema=response_schema)


class FakePersistentDraftFailureLLM(FakeScientificBaselineLLM):
    """LLM fixture that always fails on the self-refine draft node."""

    def call(self, prompt: str, system: str | None = None, response_schema=None) -> SimpleNamespace:
        if response_schema is TravelItineraryOutput and "Produce a strong first draft" in prompt:
            del system
            raise ConnectionError("persistent transport failure")
        return super().call(prompt=prompt, system=system, response_schema=response_schema)


class FakeReviserFailureLLM(FakeScientificBaselineLLM):
    """LLM fixture that fails on the self-refine reviser node."""

    def call(self, prompt: str, system: str | None = None, response_schema=None) -> SimpleNamespace:
        if response_schema is TravelItineraryOutput and "Revise the draft minimally" in prompt:
            del system
            raise ConnectionError("reviser transport failure")
        return super().call(prompt=prompt, system=system, response_schema=response_schema)


def _build_runtime(tmp_path: Path, config_dict: dict) -> tuple[dict, object, object]:
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
    return config, workspace, objective


def test_scientific_baselines_export_contracts(tmp_path: Path, config_dict: dict) -> None:
    for mode, expected_framework in [
        ("direct", "solo_direct"),
        ("cot", "solo_cot"),
        ("self_refine", "solo_self_refine"),
        ("planner_executor", "planner_executor"),
    ]:
        config, workspace, objective = _build_runtime(tmp_path / mode, config_dict)
        runner = TravelPlannerScientificBaselineRunner(
            mode=mode,
            config=config,
            workspace=workspace,
            llm_client=FakeScientificBaselineLLM(),
            seed=42,
        )
        payload = runner.run_query(
            objective=objective.description,
            objective_id=objective.objective_id,
            query_idx=0,
            query_data=dict(objective.payload["query_data"]),
        )

        assert payload["status"] == "ok"
        assert payload["query_idx"] == 0
        assert payload["summary"]["framework"] == expected_framework
        assert payload["summary"]["seed"] == 42
        assert payload["summary"]["run_status"] == "success"
        assert isinstance(payload["summary"]["step_trace"], list)
        assert "final_pass_rate" in payload["evaluation"]
        assert "validation_failures" in payload["summary"]


def test_self_refine_uses_feedback_fallback_when_critique_json_is_truncated(
    tmp_path: Path,
    config_dict: dict,
) -> None:
    config, workspace, objective = _build_runtime(tmp_path / "self_refine_fallback", config_dict)
    runner = TravelPlannerScientificBaselineRunner(
        mode="self_refine",
        config=config,
        workspace=workspace,
        llm_client=FakeSelfRefineFallbackLLM(),
        seed=42,
    )

    payload = runner.run_query(
        objective=objective.description,
        objective_id=objective.objective_id,
        query_idx=0,
        query_data=dict(objective.payload["query_data"]),
    )

    assert payload["status"] == "ok"
    assert payload["final_pass"] is True
    nodes = [item.get("node") for item in payload["summary"]["step_trace"] if isinstance(item, dict)]
    assert "self_refine_critic_fallback" in nodes


def test_self_refine_retries_transient_draft_transport_failure(
    tmp_path: Path,
    config_dict: dict,
) -> None:
    config, workspace, objective = _build_runtime(tmp_path / "self_refine_transient_draft", config_dict)
    runner = TravelPlannerScientificBaselineRunner(
        mode="self_refine",
        config=config,
        workspace=workspace,
        llm_client=FakeTransientDraftFailureLLM(),
        seed=43,
    )
    runner.node_retry_backoff_seconds = 0.0

    payload = runner.run_query(
        objective=objective.description,
        objective_id=objective.objective_id,
        query_idx=0,
        query_data=dict(objective.payload["query_data"]),
    )

    assert payload["status"] == "ok"
    draft_node = next(
        item
        for item in payload["summary"]["step_trace"]
        if isinstance(item, dict) and item.get("node") == "self_refine_draft"
    )
    assert draft_node["attempt"] == 2


def test_self_refine_returns_payload_when_draft_transport_failure_persists(
    tmp_path: Path,
    config_dict: dict,
) -> None:
    config, workspace, objective = _build_runtime(tmp_path / "self_refine_persistent_draft", config_dict)
    runner = TravelPlannerScientificBaselineRunner(
        mode="self_refine",
        config=config,
        workspace=workspace,
        llm_client=FakePersistentDraftFailureLLM(),
        seed=43,
    )
    runner.node_retry_backoff_seconds = 0.0

    payload = runner.run_query(
        objective=objective.description,
        objective_id=objective.objective_id,
        query_idx=0,
        query_data=dict(objective.payload["query_data"]),
    )

    assert payload["status"] == "ok"
    assert payload["final_plan"] == []
    nodes = [item.get("node") for item in payload["summary"]["step_trace"] if isinstance(item, dict)]
    assert "self_refine_draft_fallback" in nodes


def test_self_refine_falls_back_to_draft_when_reviser_transport_fails(
    tmp_path: Path,
    config_dict: dict,
) -> None:
    config, workspace, objective = _build_runtime(tmp_path / "self_refine_reviser_failure", config_dict)
    runner = TravelPlannerScientificBaselineRunner(
        mode="self_refine",
        config=config,
        workspace=workspace,
        llm_client=FakeReviserFailureLLM(),
        seed=43,
    )
    runner.node_retry_backoff_seconds = 0.0

    payload = runner.run_query(
        objective=objective.description,
        objective_id=objective.objective_id,
        query_idx=0,
        query_data=dict(objective.payload["query_data"]),
    )

    assert payload["status"] == "ok"
    nodes = [item.get("node") for item in payload["summary"]["step_trace"] if isinstance(item, dict)]
    assert "self_refine_reviser_fallback" in nodes


def test_planner_executor_uses_itinerary_fallback_when_blueprint_json_is_truncated(
    tmp_path: Path,
    config_dict: dict,
) -> None:
    config, workspace, objective = _build_runtime(tmp_path / "planner_executor_fallback", config_dict)
    runner = TravelPlannerScientificBaselineRunner(
        mode="planner_executor",
        config=config,
        workspace=workspace,
        llm_client=FakePlannerExecutorFallbackLLM(),
        seed=42,
    )

    payload = runner.run_query(
        objective=objective.description,
        objective_id=objective.objective_id,
        query_idx=0,
        query_data=dict(objective.payload["query_data"]),
    )

    assert payload["status"] == "ok"
    assert payload["final_pass"] is True
    nodes = [item.get("node") for item in payload["summary"]["step_trace"] if isinstance(item, dict)]
    assert "central_planner_fallback_itinerary" in nodes
    assert "central_planner_fallback_blueprint" in nodes


def test_build_scientific_pack_outputs_files(tmp_path: Path) -> None:
    study_root = tmp_path / "study"
    pack_root = study_root / "scientific_pack"
    pack_root.mkdir(parents=True)
    (study_root / "runs").mkdir(parents=True, exist_ok=True)

    manifest = {
        "seeds": [42, 43, 44],
        "arms": [
            {"id": "solo_direct", "label": "Direct Solo"},
            {"id": "stigmergiagentic", "label": "StigmergiAgentic"},
        ],
    }
    (pack_root / "study_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    registry_path = pack_root / "run_registry.csv"
    fieldnames = [
        "stage",
        "arm",
        "arm_label",
        "seed",
        "status",
        "failure_kind",
        "failure_message",
        "queries_requested",
        "query_json_count",
        "started_at_utc",
        "ended_at_utc",
        "runtime_wall_seconds",
        "out_dir",
        "config_path",
        "runs_json",
        "official_eval_json",
        "benchmark_summary_json",
        "log_path",
    ]
    rows: list[dict[str, str]] = []
    for arm, label, final_score in [
        ("solo_direct", "Direct Solo", 0.10),
        ("stigmergiagentic", "StigmergiAgentic", 0.20),
    ]:
        for seed in [42, 43, 44]:
            run_dir = study_root / "runs" / arm / f"seed_{seed}" / "full"
            run_dir.mkdir(parents=True, exist_ok=True)
            runs_json = run_dir / "runs.json"
            official_json = run_dir / "official_eval.json"
            benchmark_summary = run_dir / "benchmark_summary.json"
            final_pass = arm == "stigmergiagentic"
            runs_json.write_text(
                json.dumps(
                    {
                        "runs": [
                            {
                                "query_idx": 0,
                                "final_pass": final_pass,
                                "summary": {},
                                "final_plan": sample_valid_plan(),
                            }
                        ]
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            official_json.write_text(
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
            benchmark_summary.write_text(
                json.dumps(
                    {
                        "tokens_total": 1000 + seed,
                        "cost_total_usd": 0.01,
                        "runtime_wall_seconds": 12.0,
                        "avg_runtime_per_query_seconds": 12.0,
                        "avg_coordination_overhead": 2.0,
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            rows.append(
                {
                    "stage": "full",
                    "arm": arm,
                    "arm_label": label,
                    "seed": str(seed),
                    "status": "success",
                    "failure_kind": "",
                    "failure_message": "",
                    "queries_requested": "180",
                    "query_json_count": "180",
                    "started_at_utc": "2026-04-09T00:00:00+00:00",
                    "ended_at_utc": "2026-04-09T00:10:00+00:00",
                    "runtime_wall_seconds": "12.0",
                    "out_dir": str(run_dir),
                    "config_path": str(study_root / "configs" / f"{arm}.yaml"),
                    "runs_json": str(runs_json),
                    "official_eval_json": str(official_json),
                    "benchmark_summary_json": str(benchmark_summary),
                    "log_path": str(run_dir / "stage_command.log"),
                }
            )

    with registry_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    command = [
        sys.executable,
        "scripts/build_travelplanner_scientific_pack.py",
        "--study-root",
        str(study_root),
        "--canonical-seed",
        "42",
        "--bootstrap-iters",
        "200",
    ]
    completed = subprocess.run(
        command,
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr

    assert (pack_root / "paper_table_main.md").exists()
    assert (pack_root / "pairwise_final_pass_stats.json").exists()
    assert "StigmergiAgentic" in (pack_root / "paper_table_main.md").read_text(encoding="utf-8")
