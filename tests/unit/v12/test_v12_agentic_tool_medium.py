"""V12 autonomous-agent medium and tool tests."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from adapters_v10.migrationbench.context import MigrationContext
from core_v10.contracts import FeedbackDigest
from core_v10.event_log import JsonlEventLog
from core_v10.replay import replay_events
from core_v12.agent_loop import (
    AGENT_TOOL_CALL_PARSE_FAILED_EVENT,
    AGENT_TOOL_CALL_REQUESTED_EVENT,
    CANDIDATE_CREATED_BY_AGENT_EVENT,
    TOOL_EXECUTED_EVENT,
    AgentLoop,
    ToolChoiceError,
    assert_same_tools_available_s2_and_v12,
    build_llm_trace_payload,
)
from core_v12.medium.local_view import MEDIUM_UPDATED_EVENT, V12StigmergicMedium
from core_v12.metrics import summarize_tool_recommendation_metrics
from core_v12.tools import (
    ToolCall,
    ToolExecutionContext,
    ToolRegistry,
    ToolResult,
    ToolSpec,
)
from core_v12.tools.executor import ToolExecutor, build_default_tool_registry


class StubWorkspace:
    def __init__(self, files: dict[str, str]) -> None:
        self.files = dict(files)

    def read_file(self, rel: str, *, max_bytes: int = 0) -> str:
        return self.files[rel]

    def write_file(self, rel: str, content: str) -> None:
        self.files[rel] = content


def _ctx(workspace: StubWorkspace) -> ToolExecutionContext:
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


def test_llm_tool_choice_schema() -> None:
    call = ToolCall.model_validate(
        {
            "tool_name": "inspect_pom",
            "arguments": {"path": "pom.xml"},
            "rationale": "inspect before editing",
        }
    )

    assert call.tool_name == "inspect_pom"
    with pytest.raises(ValidationError):
        ToolCall.model_validate({"tool_name": "read_file", "unexpected": True})


def test_medium_does_not_create_patch() -> None:
    medium = V12StigmergicMedium()
    feedback = FeedbackDigest(
        candidate_id="c1",
        failure_type="compile_error",
        severity="blocking",
        summary="cannot find symbol",
    )

    created = medium.update_from_feedback(feedback)

    assert created
    assert medium.created_patch_count == 0


def test_tool_execution_guarded() -> None:
    workspace = StubWorkspace({"pom.xml": "<java.version>1.8</java.version>"})
    executor = ToolExecutor(build_default_tool_registry())

    rejected = executor.execute(
        ToolCall(
            tool_name="edit_file_guarded",
            arguments={
                "edits": [
                    {
                        "type": "replace_text",
                        "path": "pom.xml",
                        "old": "<missing>1.8</missing>",
                        "new": "<java.version>17</java.version>",
                    }
                ]
            },
        ),
        _ctx(workspace),
    )
    assert rejected.status == "rejected"
    assert workspace.files["pom.xml"] == "<java.version>1.8</java.version>"

    applied = executor.execute(
        ToolCall(
            tool_name="edit_file_guarded",
            arguments={
                "edits": [
                    {
                        "type": "replace_text",
                        "path": "pom.xml",
                        "old": "<java.version>1.8</java.version>",
                        "new": "<java.version>17</java.version>",
                    }
                ]
            },
        ),
        _ctx(workspace),
    )
    assert applied.status == "success"
    assert applied.workspace_mutated is True
    assert workspace.files["pom.xml"] == "<java.version>17</java.version>"


def test_same_tools_available_s2_and_v12() -> None:
    assert_same_tools_available_s2_and_v12()


def test_stigmergic_view_adds_pheromones() -> None:
    medium = V12StigmergicMedium()
    registry = build_default_tool_registry()
    feedback = FeedbackDigest(
        candidate_id="c1",
        failure_type="compile_error",
        severity="blocking",
        summary="src/main/java/App.java cannot find symbol",
        locations=[{"path": "src/main/java/App.java", "line": 12}],
    )
    medium.update_from_feedback(feedback)

    view = medium.local_view(
        objective="migrate",
        migration_context={"target_java": 17},
        tool_registry=registry.names(),
    )

    assert view.relevant_pheromones
    assert "src/main/java/App.java" in view.hot_files
    assert set(view.tool_registry) == set(registry.names())
    assert view.tool_annotations["read_file"]["recommendation"] == "strong_support"
    assert view.tool_annotations["edit_file_guarded"]["recommendation"] == "neutral"
    assert "read_file" in view.supported_tools


def test_medium_annotations_do_not_hide_inhibited_tools() -> None:
    medium = V12StigmergicMedium()
    registry = build_default_tool_registry()
    medium.update_from_feedback(
        {
            "candidate_id": "c1",
            "failure_type": "compile_error",
            "severity": "blocking",
            "summary": "old span absent after premature edit",
            "evidence": ["feedback_1"],
        }
    )
    medium.update_from_feedback(
        {
            "candidate_id": "c2",
            "failure_type": "unknown",
            "severity": "blocking",
            "summary": "avoid immediate edit",
            "evidence": ["feedback_2"],
            "anti_actions": ["free_replace_text"],
        }
    )

    view = medium.local_view(
        objective="migrate",
        migration_context={"target_java": 17},
        tool_registry=registry.names(),
    )

    assert set(view.tool_registry) == set(registry.names())
    assert "edit_file_guarded" in view.tool_registry
    assert "read_file" in view.tool_annotations
    assert view.forbidden_tools == {}


def test_medium_guides_after_successful_suggestion_without_hiding_tools() -> None:
    medium = V12StigmergicMedium()
    registry = build_default_tool_registry()
    medium.record_tool_outcome(
        {
            "tool_name": "inspect_pom",
            "status": "success",
            "summary": "inspected pom.xml",
            "step_index": 0,
        }
    )
    medium.record_tool_outcome(
        {
            "tool_name": "read_file",
            "status": "success",
            "summary": "read pom.xml",
            "step_index": 1,
        }
    )
    medium.record_tool_outcome(
        {
            "tool_name": "suggest_lombok_upgrade",
            "status": "success",
            "summary": "returned target-aware Lombok proposal",
            "step_index": 2,
            "proposal_kind": "dependency_upgrade",
        }
    )

    view = medium.local_view(
        objective="migrate",
        migration_context={"target_java": 17},
        tool_registry=registry.names(),
    )

    assert set(view.tool_registry) == set(registry.names())
    assert view.tool_annotations["edit_file_guarded"]["recommendation"] == (
        "strong_support"
    )
    assert "proposal_ready" in view.tool_annotations["edit_file_guarded"]["reason"]
    assert view.tool_annotations["suggest_lombok_upgrade"]["recommendation"] == (
        "caution"
    )
    assert view.tool_annotations["inspect_pom"]["recommendation"] == "caution"


def test_forbidden_tools_are_not_visible_and_are_rejected(tmp_path) -> None:
    workspace = StubWorkspace({"pom.xml": "<project/>"})
    log = JsonlEventLog(tmp_path / "events.jsonl")
    medium = V12StigmergicMedium()
    original_files = dict(workspace.files)
    loop = AgentLoop(
        medium=medium,
        event_log=log,
        run_id="r1",
        instance_id="i1",
        tool_chooser=lambda view, tools, history: ToolCall(
            tool_name="run_official_eval",
            arguments={"command": None},
            rationale="try even though forbidden",
        ),
    )
    # Runner-level forbidden context is represented by the local view. The
    # provider normally filters it out; this direct chooser verifies execution
    # safety if an agent still attempts it.
    medium.local_view = lambda **kwargs: V12StigmergicMedium.local_view(  # type: ignore[method-assign]
        medium,
        **kwargs,
        forbidden_tools={"run_official_eval": "official_eval disabled"},
    )

    step = loop.step(context=_ctx(workspace), objective="migrate")

    assert step.result.status == "rejected"
    assert step.result.metadata["forbidden_tool"] is True
    assert workspace.files == original_files
    requested = next(
        event
        for event in log.read_all()
        if event.event_type == AGENT_TOOL_CALL_REQUESTED_EVENT
    )
    assert "run_official_eval" not in requested.payload["visible_tool_registry"]


def test_verifier_feedback_updates_medium(tmp_path) -> None:
    log = JsonlEventLog(tmp_path / "events.jsonl")
    medium = V12StigmergicMedium()
    loop = AgentLoop(
        medium=medium,
        event_log=log,
        run_id="r1",
        instance_id="i1",
        tool_chooser=lambda view, tools, history: ToolCall(
            tool_name="read_file", arguments={"path": "pom.xml"}
        ),
    )
    feedback = FeedbackDigest(
        candidate_id="c1",
        failure_type="dependency_resolution_error",
        severity="blocking",
        summary="could not resolve dependencies",
    )

    loop.record_verifier_feedback(feedback)

    events = log.read_all()
    assert any(event.event_type == "verifier.feedback" for event in events)
    assert any(event.event_type == MEDIUM_UPDATED_EVENT for event in events)
    assert medium.local_view(
        objective="migrate", migration_context={"target_java": 17}
    ).supported_tools


def test_agent_can_choose_edit_file_tool(tmp_path) -> None:
    workspace = StubWorkspace({"pom.xml": "<java.version>1.8</java.version>"})
    log = JsonlEventLog(tmp_path / "events.jsonl")
    loop = AgentLoop(
        event_log=log,
        run_id="r1",
        instance_id="i1",
        tool_chooser=lambda view, tools, history: ToolCall(
            tool_name="edit_file_guarded",
            arguments={
                "edits": [
                    {
                        "type": "replace_text",
                        "path": "pom.xml",
                        "old": "<java.version>1.8</java.version>",
                        "new": "<java.version>17</java.version>",
                    }
                ]
            },
        ),
    )

    step = loop.step(context=_ctx(workspace), objective="migrate")

    assert step.result.status == "success"
    assert workspace.files["pom.xml"] == "<java.version>17</java.version>"
    assert any(
        event.event_type == CANDIDATE_CREATED_BY_AGENT_EVENT for event in log.read_all()
    )


def test_agent_can_choose_inspect_pom_before_patch() -> None:
    workspace = StubWorkspace(
        {
            "pom.xml": (
                "<project><properties>"
                "<java.version>1.8</java.version>"
                "</properties></project>"
            )
        }
    )

    def chooser(view, tools, history):
        if not history:
            return ToolCall(tool_name="inspect_pom", arguments={"path": "pom.xml"})
        return ToolCall(
            tool_name="edit_file_guarded",
            arguments={
                "edits": [
                    {
                        "type": "replace_text",
                        "path": "pom.xml",
                        "old": "<java.version>1.8</java.version>",
                        "new": "<java.version>17</java.version>",
                    }
                ]
            },
        )

    loop = AgentLoop(tool_chooser=chooser)
    first = loop.step(context=_ctx(workspace), objective="migrate")
    second = loop.step(context=_ctx(workspace), objective="migrate")

    assert first.call.tool_name == "inspect_pom"
    assert second.call.tool_name == "edit_file_guarded"
    assert workspace.files["pom.xml"].count("17") == 1


def test_suggest_tools_return_proposals_only() -> None:
    workspace = StubWorkspace({"pom.xml": "<project></project>"})
    executor = ToolExecutor(build_default_tool_registry())

    result = executor.execute(
        ToolCall(tool_name="suggest_maven_compiler_config", arguments={}),
        _ctx(workspace),
    )

    assert result.status == "success"
    assert result.proposal is not None
    assert result.proposal.applies_patch is False
    assert result.workspace_mutated is False
    assert workspace.files["pom.xml"] == "<project></project>"


def test_target_dependent_suggest_tools_do_not_default_to_java17() -> None:
    workspace = StubWorkspace({"pom.xml": "<project></project>"})
    executor = ToolExecutor(build_default_tool_registry())
    context = ToolExecutionContext(workspace=workspace)

    for tool_name in (
        "suggest_maven_compiler_config",
        "suggest_lombok_upgrade",
        "suggest_surefire_upgrade",
        "suggest_javafx_dependencies",
    ):
        result = executor.execute(ToolCall(tool_name=tool_name, arguments={}), context)
        assert result.status == "rejected"
        assert result.summary == "target Java unavailable"


def test_v12_eventlog_replay_preserves_agent_tool_trace(tmp_path) -> None:
    workspace = StubWorkspace({"pom.xml": "<project></project>"})
    log = JsonlEventLog(tmp_path / "events.jsonl")
    loop = AgentLoop(
        event_log=log,
        run_id="r1",
        instance_id="i1",
        tool_chooser=lambda view, tools, history: ToolCall(
            tool_name="read_file", arguments={"path": "pom.xml"}
        ),
    )

    loop.step(context=_ctx(workspace), objective="migrate")
    replay = replay_events(log.read_all())

    assert replay.counts_by_type[AGENT_TOOL_CALL_REQUESTED_EVENT] == 1
    assert replay.counts_by_type[TOOL_EXECUTED_EVENT] == 1


def test_s2_v12_budget_and_tool_registry_match() -> None:
    s2 = build_default_tool_registry()
    v12 = build_default_tool_registry()

    assert s2.names() == v12.names()
    assert "edit_file_guarded" in s2.names()


def test_tool_recommendation_metrics_track_follow_override_and_forbidden(tmp_path) -> None:
    workspace = StubWorkspace({"pom.xml": "<project/>"})
    log = JsonlEventLog(tmp_path / "events.jsonl")
    medium = V12StigmergicMedium()
    medium.update_from_feedback(
        FeedbackDigest(
            candidate_id="c1",
            failure_type="compile_error",
            severity="blocking",
            summary="cannot find symbol",
        )
    )
    choices = iter(
        (
            ToolCall(tool_name="read_file", arguments={"path": "pom.xml"}),
            ToolCall(tool_name="inspect_pom", arguments={"path": "pom.xml"}),
        )
    )
    loop = AgentLoop(
        medium=medium,
        event_log=log,
        run_id="r1",
        instance_id="i1",
        tool_chooser=lambda view, tools, history: next(choices),
    )

    loop.step(context=_ctx(workspace), objective="migrate")
    loop.step(context=_ctx(workspace), objective="migrate")
    metrics = summarize_tool_recommendation_metrics(log.read_all())

    assert metrics.tool_recommendation_follow_rate == 0.5
    assert metrics.tool_recommendation_override_rate == 0.5
    assert metrics.strongly_supported_tool_ignored_count == 1


def test_llm_traces_capture_full_tool_decisions_without_api_secrets() -> None:
    trace = build_llm_trace_payload(
        call=ToolCall(
            tool_name="read_file", arguments={"path": "pom.xml", "api_key": "secret"}
        ),
        raw_response='{"tool_name":"read_file","api_key":"raw-secret","authorization":"Bearer raw-token"}',
        available_tools=("read_file",),
        usage={"total_tokens": 12},
        metadata={"authorization": "Bearer secret"},
    )

    assert trace["tool_call"]["arguments"]["path"] == "pom.xml"
    assert trace["tool_call"]["arguments"]["api_key"] == "[REDACTED]"
    assert trace["usage"]["total_tokens"] == 12
    assert trace["metadata"]["authorization"] == "[REDACTED]"
    serialized = json.dumps(trace)
    assert "raw-secret" not in serialized
    assert "raw-token" not in serialized


def test_maven_tools_reject_shell_control_operators(monkeypatch, tmp_path) -> None:
    calls: list[str] = []

    def fake_run_maven(
        repo_dir, command: str, *, timeout_seconds: float
    ):  # noqa: ANN001
        calls.append(command)
        raise AssertionError("unsafe Maven command should be rejected before execution")

    monkeypatch.setattr("core_v12.tools.executor.run_maven_command", fake_run_maven)
    workspace = SimpleNamespace(metadata={"repo_dir": str(tmp_path)})
    context = ToolExecutionContext(workspace=workspace)
    executor = ToolExecutor(build_default_tool_registry())

    for tool_name in ("run_maven", "run_tests"):
        result = executor.execute(
            ToolCall(
                tool_name=tool_name, arguments={"command": "mvn test; touch injected"}
            ),
            context,
        )
        assert result.status == "rejected"

    assert calls == []
    assert not (tmp_path / "injected").exists()


def test_official_eval_command_must_come_from_workspace_metadata(tmp_path) -> None:
    executor = ToolExecutor(build_default_tool_registry())
    workspace_without_eval = SimpleNamespace(metadata={"repo_dir": str(tmp_path)})

    rejected = executor.execute(
        ToolCall(tool_name="run_official_eval", arguments={"command": "printf hacked"}),
        ToolExecutionContext(workspace=workspace_without_eval),
    )

    assert rejected.status == "rejected"
    assert rejected.summary == "official evaluator command unavailable"

    workspace_with_eval = SimpleNamespace(
        metadata={
            "repo_dir": str(tmp_path),
            "official_eval_command": "printf official",
        }
    )
    mismatch = executor.execute(
        ToolCall(tool_name="run_official_eval", arguments={"command": "printf hacked"}),
        ToolExecutionContext(workspace=workspace_with_eval),
    )

    assert mismatch.status == "rejected"
    assert (
        mismatch.summary
        == "official evaluator command not allowed by workspace metadata"
    )


def test_executor_enforces_registered_tool_contracts() -> None:
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="read_only_buggy_tool",
            description="Buggy handler that claims a mutation despite a read-only spec.",
        ),
        lambda context, call: ToolResult.success(
            tool_name=call.tool_name,
            workspace_mutated=True,
        ),
    )
    registry.register(
        ToolSpec(
            name="suggest_buggy_tool",
            description="Buggy proposal-only handler that mutates.",
            proposal_only=True,
        ),
        lambda context, call: ToolResult.success(
            tool_name=call.tool_name,
            workspace_mutated=True,
            candidate_created=True,
        ),
    )
    executor = ToolExecutor(registry)
    context = ToolExecutionContext(workspace=StubWorkspace({"pom.xml": "<project/>"}))

    read_only = executor.execute(ToolCall(tool_name="read_only_buggy_tool"), context)
    proposal_only = executor.execute(ToolCall(tool_name="suggest_buggy_tool"), context)

    assert read_only.status == "failed"
    assert read_only.summary == "tool contract violation"
    assert proposal_only.status == "failed"
    assert proposal_only.summary == "tool contract violation"


def test_agent_loop_logs_tool_choice_parse_failed(tmp_path) -> None:
    log = JsonlEventLog(tmp_path / "events.jsonl")
    loop = AgentLoop(
        event_log=log,
        run_id="r1",
        instance_id="i1",
        tool_chooser=lambda view, tools, history: (_ for _ in ()).throw(
            ToolChoiceError(
                "native tool parse failed",
                parse_errors=["no_tool_call"],
                raw_payload={"authorization": "Bearer secret"},
            )
        ),
    )

    with pytest.raises(ToolChoiceError):
        loop.step(
            context=_ctx(StubWorkspace({"pom.xml": "<project/>"})),
            objective="migrate",
        )

    events = log.read_all()
    assert any(
        event.event_type == AGENT_TOOL_CALL_PARSE_FAILED_EVENT for event in events
    )
    serialized = json.dumps([event.payload for event in events])
    assert "Bearer secret" not in serialized
