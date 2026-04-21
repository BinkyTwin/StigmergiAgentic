"""Unit tests for objective-conditioned protocol compilation."""

from __future__ import annotations

from types import SimpleNamespace

from adapters.assistant.adapter import AssistantAdapter
from adapters.base import Objective
from core.schemas import ProtocolSpec


class _FakeLLMClient:
    def __init__(self, parsed: ProtocolSpec | None) -> None:
        self.parsed = parsed

    def call(self, *args, **kwargs):  # noqa: ANN002, ANN003
        return SimpleNamespace(parsed=self.parsed)


def _objective() -> Objective:
    return Objective(
        objective_id="obj-1",
        description="Inspect the repository and summarize the test surface.",
    )


def test_assistant_compile_protocol_returns_valid_markers(config_dict: dict) -> None:
    config = dict(config_dict)
    config["agents"] = dict(config_dict["agents"])
    config["agents"]["protocol_compiler"] = {"enabled": True}
    adapter = AssistantAdapter(config=config)

    parsed = ProtocolSpec.model_validate(
        {
            "markers": [
                {
                    "id": "collect-context",
                    "target": "repo",
                    "eligible_actions": ["file_read"],
                    "intensity": 0.9,
                },
                {
                    "id": "summarize-findings",
                    "target": "summary",
                    "eligible_actions": ["think"],
                    "depends_on": ["collect-context"],
                    "intensity": 0.8,
                },
            ]
        }
    )

    markers = adapter.compile_protocol(
        objective=_objective(),
        config=config,
        llm_client=_FakeLLMClient(parsed),
    )

    assert markers is not None
    assert [marker.id for marker in markers] == [
        "collect-context",
        "summarize-findings",
    ]
    assert markers[1].payload["depends_on"] == ["collect-context"]
    assert markers[0].payload["eligible_actions"] == ["file_read"]


def test_assistant_compile_protocol_rejects_unknown_actions(
    config_dict: dict,
) -> None:
    config = dict(config_dict)
    config["agents"] = dict(config_dict["agents"])
    config["agents"]["protocol_compiler"] = {"enabled": True}
    adapter = AssistantAdapter(config=config)

    parsed = ProtocolSpec.model_validate(
        {
            "markers": [
                {
                    "id": "invalid",
                    "target": "repo",
                    "eligible_actions": ["search_flights"],
                    "intensity": 0.8,
                }
            ]
        }
    )

    markers = adapter.compile_protocol(
        objective=_objective(),
        config=config,
        llm_client=_FakeLLMClient(parsed),
    )

    assert markers is None


def test_assistant_compile_protocol_rejects_cyclic_graph(config_dict: dict) -> None:
    config = dict(config_dict)
    config["agents"] = dict(config_dict["agents"])
    config["agents"]["protocol_compiler"] = {"enabled": True}
    adapter = AssistantAdapter(config=config)

    parsed = ProtocolSpec.model_validate(
        {
            "markers": [
                {
                    "id": "a",
                    "target": "repo",
                    "eligible_actions": ["file_read"],
                    "depends_on": ["b"],
                    "intensity": 0.8,
                },
                {
                    "id": "b",
                    "target": "summary",
                    "eligible_actions": ["think"],
                    "depends_on": ["a"],
                    "intensity": 0.8,
                },
            ]
        }
    )

    markers = adapter.compile_protocol(
        objective=_objective(),
        config=config,
        llm_client=_FakeLLMClient(parsed),
    )

    assert markers is None
