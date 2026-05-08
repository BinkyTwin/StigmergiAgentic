"""OpenAI-compatible native tool-call schemas for V12 tools.

DeepSeek exposes tool calls through the OpenAI Chat Completions shape. This
module keeps that provider-facing schema separate from the looser human-facing
``ToolSpec.input_schema`` descriptions.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from core_v12.tools.registry import ToolRegistry
from core_v12.tools.schema import ToolCall, ToolSpec


JsonDict = dict[str, Any]

UNSUPPORTED_DEEPSEEK_STRICT_KEYS = {
    "minLength",
    "maxLength",
    "minItems",
    "maxItems",
}


class NativeToolSchemaError(ValueError):
    """Raised when a V12 tool cannot be represented as a native tool schema."""


class NativeToolCallParseError(ValueError):
    """Raised when a provider message cannot be parsed into one ToolCall."""

    def __init__(self, message: str, *, errors: Sequence[str] | None = None) -> None:
        super().__init__(message)
        self.errors = tuple(errors or (message,))


def registry_to_native_tools(
    registry_or_specs: ToolRegistry | Sequence[ToolSpec],
    *,
    strict: bool = True,
) -> list[JsonDict]:
    """Convert the V12 registry into OpenAI/DeepSeek Chat Completions tools."""

    return [
        tool_spec_to_native_tool(spec, strict=strict)
        for spec in _specs(registry_or_specs)
    ]


def tool_schema_hash(
    registry_or_specs: ToolRegistry | Sequence[ToolSpec],
    *,
    strict: bool = True,
) -> str:
    """Return a stable short hash for the provider-facing tool schema."""

    import hashlib

    payload = json.dumps(
        registry_to_native_tools(registry_or_specs, strict=strict),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]


def tool_spec_to_native_tool(spec: ToolSpec, *, strict: bool = True) -> JsonDict:
    """Convert one V12 ToolSpec into one provider-native function tool."""

    parameters = _parameters_for_tool(spec.name)
    _assert_deepseek_strict_compatible(parameters)
    function: JsonDict = {
        "name": spec.name,
        "description": spec.description,
        "parameters": parameters,
    }
    if strict:
        function["strict"] = True
    return {"type": "function", "function": function}


def parse_native_tool_call_message(
    message: Any,
    registry_or_specs: ToolRegistry | Sequence[ToolSpec],
) -> ToolCall:
    """Parse a provider message with exactly one native tool call."""

    specs = _specs(registry_or_specs)
    known_tools = {spec.name for spec in specs}
    schema_by_name = {spec.name: _parameters_for_tool(spec.name) for spec in specs}
    tool_calls = _extract_tool_calls(message)
    if not tool_calls:
        raise NativeToolCallParseError("no tool call returned", errors=["no_tool_call"])
    if len(tool_calls) != 1:
        raise NativeToolCallParseError(
            "expected exactly one tool call",
            errors=[f"multiple_tool_calls:{len(tool_calls)}"],
        )
    raw = tool_calls[0]
    call_id = _get(raw, "id")
    function = _get(raw, "function") or {}
    name = str(_get(function, "name") or "").strip()
    if name not in known_tools:
        raise NativeToolCallParseError(
            "unknown tool returned",
            errors=[f"unknown_tool:{name or '<empty>'}"],
        )
    raw_arguments = _get(function, "arguments")
    if isinstance(raw_arguments, str):
        try:
            arguments = json.loads(raw_arguments or "{}")
        except json.JSONDecodeError as exc:
            raise NativeToolCallParseError(
                "tool arguments are not valid JSON",
                errors=[f"invalid_arguments_json:{exc}"],
            ) from exc
    elif isinstance(raw_arguments, dict):
        arguments = dict(raw_arguments)
    else:
        raise NativeToolCallParseError(
            "tool arguments are not a JSON object",
            errors=[f"invalid_arguments_type:{type(raw_arguments).__name__}"],
        )
    validation_errors = validate_against_native_schema(
        arguments,
        schema_by_name[name],
    )
    if validation_errors:
        raise NativeToolCallParseError(
            "tool arguments failed local schema validation",
            errors=validation_errors,
        )
    rationale = str(arguments.get("rationale") or "")
    return ToolCall(
        tool_name=name,
        arguments=arguments,
        rationale=rationale,
        call_id=str(call_id) if call_id else None,
    )


def validate_against_native_schema(value: Any, schema: JsonDict) -> list[str]:
    """Return validation errors for the supported strict JSON-schema subset."""

    errors: list[str] = []
    _validate(value, schema, path="$", errors=errors)
    return errors


def _parameters_for_tool(tool_name: str) -> JsonDict:
    rationale = {
        "type": "string",
        "description": "Why this tool is the right next action.",
    }
    schemas: dict[str, JsonDict] = {
        "read_file": _object(
            {
                "path": {"type": "string", "description": "Repository-relative path."},
                "max_bytes": _nullable("integer", "Maximum bytes to read."),
                "rationale": rationale,
            }
        ),
        "search_repo": _object(
            {
                "query": {"type": "string", "description": "Literal text to search."},
                "max_results": _nullable("integer", "Maximum number of matches."),
                "rationale": rationale,
            }
        ),
        "inspect_pom": _object(
            {
                "path": _nullable("string", "Repository-relative pom.xml path."),
                "rationale": rationale,
            }
        ),
        "read_build_log": _object(
            {
                "path": _nullable(
                    "string",
                    "Artifact log key or allowlisted artifact path; null means latest known log.",
                ),
                "max_bytes": _nullable("integer", "Maximum bytes to read."),
                "rationale": rationale,
            }
        ),
        "parse_maven_errors": _object(
            {
                "log_text": _nullable("string", "Log text to parse, or null."),
                "path": _nullable(
                    "string",
                    "Artifact log key or allowlisted artifact path, or null.",
                ),
                "rationale": rationale,
            }
        ),
        "inspect_effective_pom": _object(
            {
                "command": _nullable(
                    "string",
                    "Exact Maven help:effective-pom command, or null for default.",
                ),
                "rationale": rationale,
            }
        ),
        "dependency_tree": _object(
            {
                "command": _nullable(
                    "string",
                    "Exact Maven dependency:tree command, or null for default.",
                ),
                "rationale": rationale,
            }
        ),
        "lookup_dependency_version": _object(
            {
                "artifact": {"type": "string", "description": "Artifact/plugin query."},
                "rationale": rationale,
            }
        ),
        "edit_file_guarded": _object(
            {
                "edits": {
                    "type": "array",
                    "description": "Typed edit objects to validate against the workspace.",
                    "items": {
                        "anyOf": [
                            _replace_text_edit_schema(),
                            _write_file_edit_schema(),
                        ]
                    },
                },
                "expected_build_command": _nullable(
                    "string",
                    "Expected Maven verification command.",
                ),
                "rationale": rationale,
            }
        ),
        "apply_patch": _object(
            {
                "patch": {"type": "string", "description": "Unified diff text."},
                "rationale": rationale,
            }
        ),
        "run_maven": _object(
            {
                "command": _nullable(
                    "string",
                    "Maven command such as mvn clean verify.",
                ),
                "rationale": rationale,
            }
        ),
        "run_tests": _object(
            {
                "command": _nullable("string", "Maven test command."),
                "rationale": rationale,
            }
        ),
        "run_official_eval": _object(
            {
                "command": _nullable(
                    "string",
                    "Official evaluator command from workspace metadata, or null.",
                ),
                "rationale": rationale,
            }
        ),
    }
    suggest_schema = _object(
        {
            "feedback": _nullable("string", "Relevant verifier feedback excerpt."),
            "target_java": _nullable("integer", "Target Java version if known."),
            "rationale": rationale,
        }
    )
    for name in (
        "suggest_maven_compiler_config",
        "suggest_lombok_upgrade",
        "suggest_surefire_upgrade",
        "suggest_javafx_dependencies",
        "suggest_base64_rewrite",
    ):
        schemas[name] = suggest_schema
    try:
        return schemas[tool_name]
    except KeyError as exc:
        raise NativeToolSchemaError(f"no native schema for tool: {tool_name}") from exc


def _replace_text_edit_schema() -> JsonDict:
    return _object(
        {
            "type": {"type": "string", "enum": ["replace_text"]},
            "path": {"type": "string"},
            "old": {"type": "string"},
            "new": {"type": "string"},
            "expected_replacements": _nullable("integer", "Expected replacement count."),
            "allow_multiple": _nullable("boolean", "Whether multiple matches are allowed."),
        }
    )


def _write_file_edit_schema() -> JsonDict:
    return _object(
        {
            "type": {"type": "string", "enum": ["write_file"]},
            "path": {"type": "string"},
            "content": {"type": "string"},
        }
    )


def _object(properties: dict[str, JsonDict]) -> JsonDict:
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def _nullable(type_name: str, description: str) -> JsonDict:
    return {"type": [type_name, "null"], "description": description}


def _assert_deepseek_strict_compatible(schema: JsonDict) -> None:
    bad_keys: list[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key in UNSUPPORTED_DEEPSEEK_STRICT_KEYS:
                    bad_keys.append(key)
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(schema)
    if bad_keys:
        raise NativeToolSchemaError(
            f"schema uses DeepSeek-strict unsupported keys: {sorted(set(bad_keys))}"
        )


def _validate(value: Any, schema: JsonDict, *, path: str, errors: list[str]) -> None:
    if "anyOf" in schema:
        for option in schema["anyOf"]:
            option_errors: list[str] = []
            _validate(value, option, path=path, errors=option_errors)
            if not option_errors:
                return
        errors.append(f"{path}: does not match any allowed schema")
        return
    expected = schema.get("type")
    if isinstance(expected, list):
        if value is None and "null" in expected:
            return
        non_null = [item for item in expected if item != "null"]
        if len(non_null) == 1:
            _validate(value, {**schema, "type": non_null[0]}, path=path, errors=errors)
            return
    if expected == "object":
        if not isinstance(value, dict):
            errors.append(f"{path}: expected object")
            return
        required = tuple(schema.get("required") or ())
        for key in required:
            if key not in value:
                errors.append(f"{path}.{key}: missing required field")
        if schema.get("additionalProperties") is False:
            allowed = set(schema.get("properties") or {})
            for key in value:
                if key not in allowed:
                    errors.append(f"{path}.{key}: additional property not allowed")
        for key, child_schema in (schema.get("properties") or {}).items():
            if key in value:
                _validate(value[key], child_schema, path=f"{path}.{key}", errors=errors)
        return
    if expected == "array":
        if not isinstance(value, list):
            errors.append(f"{path}: expected array")
            return
        for index, item in enumerate(value):
            _validate(
                item,
                schema.get("items") or {},
                path=f"{path}[{index}]",
                errors=errors,
            )
        return
    if expected == "string" and not isinstance(value, str):
        errors.append(f"{path}: expected string")
        return
    if expected == "integer" and (not isinstance(value, int) or isinstance(value, bool)):
        errors.append(f"{path}: expected integer")
        return
    if expected == "number" and (not isinstance(value, (int, float)) or isinstance(value, bool)):
        errors.append(f"{path}: expected number")
        return
    if expected == "boolean" and not isinstance(value, bool):
        errors.append(f"{path}: expected boolean")
        return
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: expected one of {schema['enum']}")


def _extract_tool_calls(message: Any) -> list[Any]:
    calls = _get(message, "tool_calls")
    if calls is None:
        return []
    return list(calls)


def _get(value: Any, key: str) -> Any:
    if isinstance(value, dict):
        return value.get(key)
    return getattr(value, key, None)


def _specs(registry_or_specs: ToolRegistry | Sequence[ToolSpec]) -> tuple[ToolSpec, ...]:
    if isinstance(registry_or_specs, ToolRegistry):
        return registry_or_specs.specs()
    return tuple(registry_or_specs)


__all__ = [
    "NativeToolCallParseError",
    "NativeToolSchemaError",
    "UNSUPPORTED_DEEPSEEK_STRICT_KEYS",
    "parse_native_tool_call_message",
    "registry_to_native_tools",
    "tool_schema_hash",
    "tool_spec_to_native_tool",
    "validate_against_native_schema",
]
