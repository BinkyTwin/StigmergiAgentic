"""V12 native tool-call provider tests."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from adapters_v10.migrationbench.context import MigrationContext
from core_v12.agent_loop import AgentLoop
from core_v12.medium.local_view import AgentLocalView, V12StigmergicMedium
from core_v12.tools.executor import build_default_tool_registry
from core_v12.tools.registry import ToolExecutionContext
from scripts.bench.providers_v12_llm import (
    DEFAULT_DEEPSEEK_MODEL,
    V12LLMConfig,
    V12NativeToolClient,
)


class FakeCompletions:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def create(self, **kwargs):  # noqa: ANN001
        self.calls.append(kwargs)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class FakeClient:
    def __init__(self, responses):
        self.completions = FakeCompletions(responses)
        self.chat = SimpleNamespace(completions=self.completions)


class StubWorkspace:
    def __init__(self, files: dict[str, str]) -> None:
        self.files = dict(files)

    def read_file(self, rel: str, *, max_bytes: int = 0) -> str:
        return self.files[rel]

    def write_file(self, rel: str, content: str) -> None:
        self.files[rel] = content


def _response(tool_calls, *, content=None, usage=None):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message={"content": content, "tool_calls": tool_calls},
                finish_reason="tool_calls" if tool_calls else "stop",
            )
        ],
        usage=usage or {"total_tokens": 12},
    )


def _tool_call(name: str, arguments: dict, *, call_id: str = "call_1"):
    return {
        "id": call_id,
        "function": {
            "name": name,
            "arguments": json.dumps(arguments),
        },
    }


def _config(tmp_path: Path) -> V12LLMConfig:
    return V12LLMConfig(
        provider="deepseek",
        model="deepseek-chat",
        base_url="https://api.deepseek.com/beta",
        api_key="test-key",
        trace_dir=tmp_path / "llm_traces",
        max_schema_retries=1,
    )


def test_config_defaults_to_current_deepseek_model(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

    config = V12LLMConfig.from_extras({"provider": "deepseek", "out_dir": tmp_path})

    assert config is not None
    assert config.model == DEFAULT_DEEPSEEK_MODEL
    assert config.base_url == "https://api.deepseek.com/beta"
    assert config.trace_dir == tmp_path / "llm_traces"


def test_config_parses_boolean_strings(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

    disabled = V12LLMConfig.from_extras({"use_v12_llm_provider": "false"})
    config = V12LLMConfig.from_extras(
        {
            "provider": "deepseek",
            "v12_strict_tools": "false",
            "llm_trace_enabled": "false",
            "out_dir": tmp_path,
        }
    )

    assert disabled is None
    assert config is not None
    assert config.strict_tools is False
    assert config.trace_dir is None


def test_non_deepseek_provider_requires_explicit_model(monkeypatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    with pytest.raises(ValueError, match="model must be configured explicitly"):
        V12LLMConfig.from_extras({"provider": "openrouter"})

    config = V12LLMConfig.from_extras(
        {
            "provider": "openrouter",
            "v12_llm": {"model": "deepseek/deepseek-v4-flash"},
        }
    )

    assert config is not None
    assert config.provider == "openrouter"
    assert config.model == "deepseek/deepseek-v4-flash"


def _view() -> AgentLocalView:
    registry = build_default_tool_registry()
    return AgentLocalView(
        objective="migrate repository",
        migration_context={
            "source_language": "java",
            "source_version": 8,
            "target_language": "java",
            "target_version": 17,
            "target_class_major": 61,
            "build_system": "maven",
            "migration_mode": "minimal",
            "dependency_policy": "minimal",
        },
        tool_registry=registry.names(),
        tool_annotations={
            "read_file": {
                "support": 0.9,
                "inhibition": 0.0,
                "risk": "low",
                "recommendation": "strong_support",
                "reason": "compile feedback cites source file",
                "evidence": ["signal_1"],
            },
            "edit_file_guarded": {
                "support": 0.2,
                "inhibition": 0.6,
                "risk": "medium",
                "recommendation": "caution",
                "reason": "previous old span absent",
                "evidence": ["candidate_1"],
            },
        },
    )


def _context(workspace: StubWorkspace) -> ToolExecutionContext:
    return ToolExecutionContext(
        workspace=workspace,
        migration_context=MigrationContext(
            source_language="java",
            source_version=8,
            target_language="java",
            target_version=17,
            target_class_major=61,
            build_system="maven",
            migration_mode="minimal",
            dependency_policy="minimal",
        ),
    )


def test_native_deepseek_openai_tool_response_returns_tool_call(tmp_path) -> None:
    fake = FakeClient(
        [
            _response(
                [
                    _tool_call(
                        "read_file",
                        {
                            "path": "pom.xml",
                            "max_bytes": None,
                            "rationale": "inspect pom first",
                        },
                    )
                ]
            )
        ]
    )
    client = V12NativeToolClient(_config(tmp_path), sdk_client=fake)

    call = client.choose_tool(_view(), build_default_tool_registry().specs(), ())

    assert call.tool_name == "read_file"
    assert call.arguments["path"] == "pom.xml"
    assert fake.completions.calls[0]["tools"]
    assert fake.completions.calls[0]["parallel_tool_calls"] is False
    assert fake.completions.calls[0]["tool_choice"] == "required"
    assert fake.completions.calls[0]["extra_body"] == {
        "thinking": {"type": "disabled"}
    }


def test_provider_sends_full_non_forbidden_toolbox_not_medium_shortlist(tmp_path) -> None:
    registry = build_default_tool_registry()
    view = _view()
    view = AgentLocalView(
        **{
            **view.to_dict(),
            "forbidden_tools": {"run_official_eval": "official eval disabled"},
        }
    )
    fake = FakeClient(
        [
            _response(
                [
                    _tool_call(
                        "read_file",
                        {
                            "path": "pom.xml",
                            "max_bytes": None,
                            "rationale": "follow strong support",
                        },
                    )
                ]
            )
        ]
    )
    client = V12NativeToolClient(_config(tmp_path), sdk_client=fake)

    client.choose_tool(view, registry.specs(), ())

    sent_tools = {
        tool["function"]["name"] for tool in fake.completions.calls[0]["tools"]
    }
    assert sent_tools == set(registry.names()) - {"run_official_eval"}
    assert "edit_file_guarded" in sent_tools


def test_provider_retries_schema_failure_then_succeeds(tmp_path) -> None:
    fake = FakeClient(
        [
            _response([], content="I would inspect the pom"),
            _response(
                [
                    _tool_call(
                        "inspect_pom",
                        {"path": None, "rationale": "inspect Maven structure"},
                    )
                ]
            ),
        ]
    )
    client = V12NativeToolClient(_config(tmp_path), sdk_client=fake)

    call = client.choose_tool(_view(), build_default_tool_registry().specs(), ())

    assert call.tool_name == "inspect_pom"
    assert len(fake.completions.calls) == 2
    traces = _read_traces(tmp_path)
    assert [row["parse_status"] for row in traces] == ["parse_failed", "ok"]


@pytest.mark.parametrize(
    "bad_tool_calls",
    [
        [
            _tool_call("read_file", {"path": "pom.xml", "max_bytes": None, "rationale": "a"}),
            _tool_call("inspect_pom", {"path": None, "rationale": "b"}),
        ],
        [_tool_call("unknown_tool", {"rationale": "bad"})],
        [{"id": "bad", "function": {"name": "read_file", "arguments": "{bad-json}"}}],
    ],
)
def test_provider_rejects_invalid_native_tool_calls(tmp_path, bad_tool_calls) -> None:
    fake = FakeClient([_response(bad_tool_calls), _response(bad_tool_calls)])
    client = V12NativeToolClient(_config(tmp_path), sdk_client=fake)

    with pytest.raises(Exception):
        client.choose_tool(_view(), build_default_tool_registry().specs(), ())

    traces = _read_traces(tmp_path)
    assert len(traces) == 2
    assert all(row["parse_status"] == "parse_failed" for row in traces)


def test_tool_rejection_after_valid_choice_does_not_retry_llm(tmp_path) -> None:
    fake = FakeClient(
        [
            _response(
                [
                    _tool_call(
                        "run_maven",
                        {
                            "command": "mvn test; touch bad",
                            "rationale": "try unsafe command",
                        },
                    )
                ]
            )
        ]
    )
    client = V12NativeToolClient(_config(tmp_path), sdk_client=fake)
    loop = AgentLoop(
        tool_chooser=lambda view, tools, history: client.choose_tool(view, tools, history)
    )

    step = loop.step(
        context=_context(StubWorkspace({"pom.xml": "<project/>"})),
        objective="migrate",
        migration_context=_view().migration_context,
    )

    assert step.result.status == "rejected"
    assert len(fake.completions.calls) == 1


def test_trace_captures_full_tool_decision_and_redacts_secrets(tmp_path) -> None:
    fake = FakeClient(
        [
            _response(
                [
                    _tool_call(
                        "read_file",
                        {
                            "path": "pom.xml",
                            "max_bytes": None,
                            "rationale": "authorization: Bearer raw-token",
                        },
                    )
                ],
                content="api_key='raw-secret'",
                usage={"total_tokens": 99},
            )
        ]
    )
    client = V12NativeToolClient(_config(tmp_path), sdk_client=fake)

    client.choose_tool(_view(), build_default_tool_registry().specs(), ())

    traces = _read_traces(tmp_path)
    assert traces[0]["schema_version"] == "v12.llm_native_tool_trace.v1"
    assert traces[0]["parsed_tool_call"]["tool_name"] == "read_file"
    assert traces[0]["usage"]["total_tokens"] == 99
    serialized = json.dumps(traces[0])
    assert "raw-token" not in serialized
    assert "raw-secret" not in serialized


def test_provider_does_not_create_candidate_or_patch(tmp_path) -> None:
    fake = FakeClient(
        [
            _response(
                [
                    _tool_call(
                        "suggest_maven_compiler_config",
                        {
                            "feedback": None,
                            "target_java": 17,
                            "rationale": "ask for a proposal before editing",
                        },
                    )
                ]
            )
        ]
    )
    client = V12NativeToolClient(_config(tmp_path), sdk_client=fake)
    medium = V12StigmergicMedium()
    loop = AgentLoop(
        medium=medium,
        tool_chooser=lambda view, tools, history: client.choose_tool(view, tools, history),
    )
    workspace = StubWorkspace({"pom.xml": "<project/>"})

    step = loop.step(
        context=_context(workspace),
        objective="migrate",
        migration_context=_view().migration_context,
    )

    assert step.result.status == "success"
    assert step.result.proposal is not None
    assert step.result.workspace_mutated is False
    assert step.result.candidate_created is False
    assert medium.created_patch_count == 0
    assert workspace.files["pom.xml"] == "<project/>"


def test_parallel_tool_calls_param_fallback_is_traced(tmp_path) -> None:
    fake = FakeClient(
        [
            ValueError("unknown parameter parallel_tool_calls"),
            _response(
                [
                    _tool_call(
                        "read_file",
                        {
                            "path": "pom.xml",
                            "max_bytes": None,
                            "rationale": "inspect pom",
                        },
                    )
                ]
            ),
        ]
    )
    client = V12NativeToolClient(_config(tmp_path), sdk_client=fake)

    client.choose_tool(_view(), build_default_tool_registry().specs(), ())

    assert len(fake.completions.calls) == 2
    assert "parallel_tool_calls" not in fake.completions.calls[1]
    assert fake.completions.calls[1]["tool_choice"] == "required"
    assert _read_traces(tmp_path)[0]["provider_param_fallback"] is True


def _read_traces(tmp_path: Path) -> list[dict]:
    path = tmp_path / "llm_traces" / "calls.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
