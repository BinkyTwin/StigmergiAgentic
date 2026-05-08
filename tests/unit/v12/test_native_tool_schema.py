"""Native OpenAI-compatible V12 tool schema tests."""

from __future__ import annotations

import json

import pytest

from core_v12.tools.executor import build_default_tool_registry
from core_v12.tools.native_schema import (
    UNSUPPORTED_DEEPSEEK_STRICT_KEYS,
    NativeToolCallParseError,
    parse_native_tool_call_message,
    registry_to_native_tools,
    tool_schema_hash,
)


def test_each_v12_tool_becomes_strict_native_function() -> None:
    registry = build_default_tool_registry()
    native_tools = registry_to_native_tools(registry)

    assert {tool["function"]["name"] for tool in native_tools} == set(registry.names())
    for tool in native_tools:
        assert tool["type"] == "function"
        function = tool["function"]
        assert function["strict"] is True
        parameters = function["parameters"]
        assert parameters["type"] == "object"
        assert parameters["additionalProperties"] is False
        assert "rationale" in parameters["properties"]
        assert "rationale" in parameters["required"]


def test_native_schemas_are_deepseek_strict_compatible() -> None:
    native_tools = registry_to_native_tools(build_default_tool_registry())

    def walk(node):
        if isinstance(node, dict):
            assert not (set(node) & UNSUPPORTED_DEEPSEEK_STRICT_KEYS)
            if node.get("type") == "object":
                assert node.get("additionalProperties") is False
                assert set(node.get("required") or ()) == set(node.get("properties") or {})
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(native_tools)


def test_tool_schema_hash_is_stable() -> None:
    registry = build_default_tool_registry()

    assert tool_schema_hash(registry) == tool_schema_hash(registry)


def test_parse_native_tool_call_message_to_tool_call() -> None:
    message = {
        "tool_calls": [
            {
                "id": "call_1",
                "function": {
                    "name": "read_file",
                    "arguments": json.dumps(
                        {
                            "path": "pom.xml",
                            "max_bytes": None,
                            "rationale": "inspect project build file",
                        }
                    ),
                },
            }
        ]
    }

    call = parse_native_tool_call_message(message, build_default_tool_registry())

    assert call.tool_name == "read_file"
    assert call.call_id == "call_1"
    assert call.arguments["path"] == "pom.xml"
    assert call.rationale == "inspect project build file"


@pytest.mark.parametrize(
    ("message", "reason"),
    [
        ({"content": "I would inspect pom.xml"}, "no_tool_call"),
        (
            {
                "tool_calls": [
                    {"function": {"name": "read_file", "arguments": "{}"}},
                    {"function": {"name": "inspect_pom", "arguments": "{}"}},
                ]
            },
            "multiple_tool_calls",
        ),
        (
            {
                "tool_calls": [
                    {"function": {"name": "unknown_tool", "arguments": "{}"}}
                ]
            },
            "unknown_tool",
        ),
        (
            {
                "tool_calls": [
                    {
                        "function": {
                            "name": "read_file",
                            "arguments": "{not-json}",
                        }
                    }
                ]
            },
            "invalid_arguments_json",
        ),
        (
            {
                "tool_calls": [
                    {
                        "function": {
                            "name": "read_file",
                            "arguments": json.dumps({"path": "pom.xml"}),
                        }
                    }
                ]
            },
            "missing required field",
        ),
    ],
)
def test_parse_native_tool_call_rejects_invalid_messages(message, reason: str) -> None:
    with pytest.raises(NativeToolCallParseError) as exc_info:
        parse_native_tool_call_message(message, build_default_tool_registry())

    assert reason in " ".join(exc_info.value.errors)
