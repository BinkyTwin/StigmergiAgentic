"""Integration tests for TravelPlannerAdapter.compile_protocol (Sprint 9 T3)."""

from __future__ import annotations

import copy
from types import SimpleNamespace

from adapters.travelplanner.adapter import TravelPlannerAdapter
from core.schemas import ProtocolSpec
from travelplanner_data import sample_query_rows, write_sample_database


class _FakeCompilerLLM:
    def __init__(self, parsed: ProtocolSpec | None) -> None:
        self.parsed = parsed

    def call(self, *args, **kwargs):  # noqa: ANN002, ANN003
        return SimpleNamespace(parsed=self.parsed)


def _build_adapter(tmp_path, config_dict: dict) -> tuple[TravelPlannerAdapter, dict]:
    config = copy.deepcopy(config_dict)
    config["agents"] = dict(config["agents"])
    config["agents"]["protocol_compiler"] = {"enabled": True}
    config["travelplanner"] = {
        "database_path": str(write_sample_database(tmp_path / "database")),
        "dataset_split": "validation",
        "query_rows": sample_query_rows(),
        "default_query_idx": 0,
    }
    adapter = TravelPlannerAdapter(config=config)
    adapter.create_workspace(config)
    return adapter, config


def test_travelplanner_compile_protocol_returns_valid_markers(
    tmp_path,
    config_dict: dict,
) -> None:
    adapter, config = _build_adapter(tmp_path, config_dict)
    objective = adapter.create_objective({"objective": "Query 0"}, config)

    parsed = ProtocolSpec.model_validate(
        {
            "markers": [
                {
                    "id": "custom::search_flights",
                    "target": "flights",
                    "eligible_actions": ["search_flights"],
                    "intensity": 0.9,
                },
                {
                    "id": "custom::plan",
                    "target": "plan",
                    "eligible_actions": ["plan_itinerary"],
                    "depends_on": ["custom::search_flights"],
                    "intensity": 0.85,
                },
                {
                    "id": "custom::validate",
                    "target": "validate",
                    "eligible_actions": ["validate_constraints"],
                    "depends_on": ["custom::plan"],
                    "intensity": 0.8,
                },
                {
                    "id": "custom::finalize",
                    "target": "finalize",
                    "eligible_actions": ["validate_constraints"],
                    "depends_on": ["custom::validate"],
                    "intensity": 0.75,
                    "payload": {"stage": "finalize"},
                },
            ]
        }
    )

    markers = adapter.compile_protocol(
        objective=objective,
        config=config,
        llm_client=_FakeCompilerLLM(parsed),
    )

    assert markers is not None
    assert [marker.id for marker in markers] == [
        "custom::search_flights",
        "custom::plan",
        "custom::validate",
        "custom::finalize",
    ]
    assert markers[1].payload["depends_on"] == ["custom::search_flights"]
    assert markers[0].payload["eligible_actions"] == ["search_flights"]
    for marker in markers:
        assert marker.state == "pending"
        assert marker.payload["objective"] == objective.description
        assert marker.payload["query_idx"] == objective.payload["query_idx"]


def test_travelplanner_compile_protocol_disabled_returns_none(
    tmp_path,
    config_dict: dict,
) -> None:
    adapter, config = _build_adapter(tmp_path, config_dict)
    config["agents"]["protocol_compiler"] = {"enabled": False}
    objective = adapter.create_objective({"objective": "Query 0"}, config)

    parsed = ProtocolSpec.model_validate(
        {
            "markers": [
                {
                    "id": "x",
                    "target": "t",
                    "eligible_actions": ["search_flights"],
                    "intensity": 0.9,
                }
            ]
        }
    )
    markers = adapter.compile_protocol(
        objective=objective,
        config=config,
        llm_client=_FakeCompilerLLM(parsed),
    )
    assert markers is None


def test_travelplanner_compile_protocol_rejects_unknown_actions(
    tmp_path,
    config_dict: dict,
) -> None:
    adapter, config = _build_adapter(tmp_path, config_dict)
    objective = adapter.create_objective({"objective": "Query 0"}, config)

    parsed = ProtocolSpec.model_validate(
        {
            "markers": [
                {
                    "id": "bad",
                    "target": "x",
                    "eligible_actions": ["compile_rocket"],
                    "intensity": 0.8,
                }
            ]
        }
    )
    markers = adapter.compile_protocol(
        objective=objective,
        config=config,
        llm_client=_FakeCompilerLLM(parsed),
    )
    assert markers is None


def test_travelplanner_compile_protocol_fallback_on_llm_error(
    tmp_path,
    config_dict: dict,
) -> None:
    """Invalid LLM output (None parsed) triggers fallback — initial_markers still works."""
    adapter, config = _build_adapter(tmp_path, config_dict)
    objective = adapter.create_objective({"objective": "Query 0"}, config)

    markers = adapter.compile_protocol(
        objective=objective,
        config=config,
        llm_client=_FakeCompilerLLM(parsed=None),
    )
    assert markers is None

    # Fallback path — initial_markers must remain callable without exception.
    fallback = adapter.initial_markers(objective=objective, agent_id="agent-fallback")
    assert isinstance(fallback, list)
    assert len(fallback) >= 1
    assert any(marker.state == "pending" for marker in fallback)


def test_travelplanner_compile_protocol_rejects_cyclic_graph(
    tmp_path,
    config_dict: dict,
) -> None:
    adapter, config = _build_adapter(tmp_path, config_dict)
    objective = adapter.create_objective({"objective": "Query 0"}, config)

    parsed = ProtocolSpec.model_validate(
        {
            "markers": [
                {
                    "id": "a",
                    "target": "x",
                    "eligible_actions": ["search_flights"],
                    "depends_on": ["b"],
                    "intensity": 0.8,
                },
                {
                    "id": "b",
                    "target": "y",
                    "eligible_actions": ["plan_itinerary"],
                    "depends_on": ["a"],
                    "intensity": 0.8,
                },
            ]
        }
    )
    markers = adapter.compile_protocol(
        objective=objective,
        config=config,
        llm_client=_FakeCompilerLLM(parsed),
    )
    assert markers is None
