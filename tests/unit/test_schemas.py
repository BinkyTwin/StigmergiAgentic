"""Unit tests for Pydantic runtime schemas."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from core.schemas import (
    DecomposeOutput,
    LLMParsedResponse,
    SubtaskSpec,
    ThinkOutput,
    ToolResult,
)


def test_think_output_valid_payload() -> None:
    payload = ThinkOutput.model_validate(
        {
            "analysis": "Inspect repository and run tests.",
            "command": "pytest -q",
            "next_action": "bash_exec",
        }
    )
    assert payload.analysis.startswith("Inspect")
    assert payload.command == "pytest -q"


def test_think_output_rejects_missing_analysis() -> None:
    with pytest.raises(ValidationError):
        ThinkOutput.model_validate({"command": "pytest -q"})


def test_subtask_spec_defaults() -> None:
    spec = SubtaskSpec.model_validate({"title": "Implement endpoint"})
    assert spec.description == ""
    assert spec.depends_on_indices == []
    assert spec.eligible_actions == []


def test_decompose_output_nested_subtasks() -> None:
    payload = DecomposeOutput.model_validate(
        {
            "subtasks": [
                {
                    "title": "Plan",
                    "depends_on_indices": [],
                    "eligible_actions": ["think"],
                },
                {
                    "title": "Implement",
                    "depends_on_indices": [0],
                    "eligible_actions": ["file_write", "bash_exec"],
                },
            ]
        }
    )
    assert len(payload.subtasks) == 2
    assert payload.subtasks[1].depends_on_indices == [0]


def test_model_validate_json_support() -> None:
    raw = '{"analysis":"Use workspace context","path":"README.md"}'
    parsed = ThinkOutput.model_validate_json(raw)
    assert parsed.path == "README.md"


def test_tool_result_and_parsed_response_edge_cases() -> None:
    tool_result = ToolResult.model_validate({"success": True, "output": "ok"})
    parsed = LLMParsedResponse(
        raw_content='{"analysis":"ok"}',
        parsed={"analysis": "ok"},
    )
    invalid = LLMParsedResponse(
        raw_content="not-json",
        validation_error="invalid_json",
    )

    assert tool_result.artifacts == {}
    assert parsed.is_valid is True
    assert invalid.is_valid is False
