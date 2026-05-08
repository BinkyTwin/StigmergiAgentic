"""V12 autonomous LLM tool loop.

The loop records decisions and tool outputs. It does not route domain-specific
operators; the LLM chooses tools and parameters from the registry.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable

from core_v10.contracts import FeedbackDigest, to_jsonable
from core_v10.event_log import JsonlEventLog
from core_v12.medium.local_view import AgentLocalView, V12StigmergicMedium
from core_v12.tools.executor import ToolExecutor, build_default_tool_registry
from core_v12.tools.registry import ToolExecutionContext, ToolRegistry
from core_v12.tools.schema import ToolCall, ToolResult, ToolSpec


AGENT_TOOL_CALL_REQUESTED_EVENT = "agent.tool_call.requested"
TOOL_EXECUTED_EVENT = "tool.executed"
TOOL_PROPOSAL_RETURNED_EVENT = "tool.proposal.returned"
CANDIDATE_CREATED_BY_AGENT_EVENT = "candidate.created_by_agent"
VERIFIER_FEEDBACK_EVENT = "verifier.feedback"
AGENT_TOOL_CALL_PARSE_FAILED_EVENT = "agent.tool_call.parse_failed"


ToolChooser = Callable[
    [AgentLocalView, tuple[ToolSpec, ...], tuple["AgentStep", ...]],
    ToolCall | dict[str, Any],
]
ToolContextPreparer = Callable[
    [ToolCall, ToolExecutionContext, int],
    ToolExecutionContext,
]


@dataclass(frozen=True)
class V12ExperimentalArm:
    """One V12 experimental arm definition."""

    arm_id: str
    description: str
    uses_tools: bool
    uses_medium: bool
    tool_registry_profile: str
    free_patch_baseline: bool = False


V12_EXPERIMENTAL_ARMS: tuple[V12ExperimentalArm, ...] = (
    V12ExperimentalArm(
        arm_id="S1_sd_feedback_like",
        description="LLM free patch plus verifier feedback, no V12 medium.",
        uses_tools=False,
        uses_medium=False,
        tool_registry_profile="none",
        free_patch_baseline=True,
    ),
    V12ExperimentalArm(
        arm_id="S2_tool_feedback_agent",
        description="LLM uses the V12 tools with verifier feedback, no stigmergic local view.",
        uses_tools=True,
        uses_medium=False,
        tool_registry_profile="v12_default",
    ),
    V12ExperimentalArm(
        arm_id="V12_stigmergic_tool_agent",
        description="Same tools as S2 plus the stigmergic AgentLocalView.",
        uses_tools=True,
        uses_medium=True,
        tool_registry_profile="v12_default",
    ),
)


class ToolChoiceError(RuntimeError):
    """Raised when a provider cannot produce a valid V12 ToolCall."""

    def __init__(
        self,
        message: str,
        *,
        parse_errors: Iterable[str] | None = None,
        raw_payload: Any | None = None,
    ) -> None:
        super().__init__(message)
        self.parse_errors = tuple(parse_errors or (message,))
        self.raw_payload = raw_payload

    def to_dict(self) -> dict[str, Any]:
        return {
            "message": str(self),
            "parse_errors": list(self.parse_errors),
            "raw_payload": redact_secrets(self.raw_payload),
        }


@dataclass(frozen=True)
class AgentStep:
    """One tool-use step in the V12 loop."""

    step_index: int
    call: ToolCall
    result: ToolResult

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_index": self.step_index,
            "call": self.call.model_dump(mode="json"),
            "result": self.result.model_dump(mode="json"),
        }


@dataclass
class AgentLoop:
    """Autonomous agent loop over a shared tool registry and optional medium."""

    registry: ToolRegistry = field(default_factory=build_default_tool_registry)
    tool_chooser: ToolChooser | None = None
    medium: V12StigmergicMedium | None = None
    event_log: JsonlEventLog | None = None
    run_id: str = "v12"
    instance_id: str = "unknown"
    actor: str = "v12_agent"
    context_preparer: ToolContextPreparer | None = None
    forbidden_tools: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.executor = ToolExecutor(self.registry)
        self.history: list[AgentStep] = []

    def step(
        self,
        *,
        context: ToolExecutionContext,
        objective: str,
        migration_context: Any | None = None,
        current_best: dict[str, Any] | None = None,
    ) -> AgentStep:
        """Run one local-view -> tool-choice -> tool-execution step."""

        view = self._local_view(
            objective=objective,
            migration_context=migration_context or context.migration_context or {},
            current_best=current_best,
        )
        if self.tool_chooser is None:
            raise ValueError("AgentLoop requires a tool_chooser for execution")
        try:
            raw_call = self.tool_chooser(view, self.registry.specs(), tuple(self.history))
            call = (
                raw_call
                if isinstance(raw_call, ToolCall)
                else ToolCall.model_validate(raw_call)
            )
        except ToolChoiceError as exc:
            self._emit_tool_choice_failure(exc)
            raise
        except Exception as exc:  # noqa: BLE001
            error = ToolChoiceError(
                "tool choice failed",
                parse_errors=[str(exc)],
                raw_payload={"exception_type": type(exc).__name__},
            )
            self._emit_tool_choice_failure(error)
            raise error from exc
        self._append(
            AGENT_TOOL_CALL_REQUESTED_EVENT,
            {
                "tool_call": redact_secrets(call.model_dump(mode="json")),
                "available_tools": self.registry.names(),
                "visible_tool_registry": list(view.tool_registry),
                "forbidden_tools": view.forbidden_tools,
                "tool_annotation": view.tool_annotations.get(call.tool_name),
                "tool_recommendation_context": _tool_recommendation_context(
                    view=view,
                    selected_tool=call.tool_name,
                ),
            },
        )
        execution_context = context
        if call.tool_name not in view.forbidden_tools and self.context_preparer is not None:
            execution_context = self.context_preparer(
                call,
                context,
                len(self.history),
            )

        if call.tool_name in view.forbidden_tools:
            result = ToolResult.rejected(
                tool_name=call.tool_name,
                summary="forbidden tool",
                errors=[view.forbidden_tools[call.tool_name]],
                metadata={"forbidden_tool": True},
            )
        else:
            result = self.executor.execute(call, execution_context)
            result = _with_execution_context_metadata(result, execution_context)
        self._append(
            TOOL_EXECUTED_EVENT,
            {
                "tool_call": redact_secrets(call.model_dump(mode="json")),
                "result": redact_secrets(result.model_dump(mode="json")),
            },
        )
        if self.medium is not None:
            self.medium.record_tool_outcome(
                {
                    "tool_name": call.tool_name,
                    "status": result.status,
                    "summary": result.summary,
                    "step_index": len(self.history),
                    "candidate_created": result.candidate_created,
                    "workspace_mutated": result.workspace_mutated,
                    "proposal_kind": result.proposal.kind
                    if result.proposal is not None
                    else None,
                }
            )
        if result.proposal is not None:
            self._append(
                TOOL_PROPOSAL_RETURNED_EVENT,
                {"proposal": result.proposal.model_dump(mode="json")},
            )
        if result.candidate_created:
            self._append(
                CANDIDATE_CREATED_BY_AGENT_EVENT,
                {
                    "tool_name": call.tool_name,
                    "workspace_mutated": result.workspace_mutated,
                    "medium_created_patch_count": (
                        self.medium.created_patch_count if self.medium else 0
                    ),
                },
            )
            if self.medium is not None:
                self.medium.record_candidate(
                    {
                        "tool_name": call.tool_name,
                        "summary": result.summary,
                        "step_index": len(self.history),
                    }
                )
        step = AgentStep(step_index=len(self.history), call=call, result=result)
        self.history.append(step)
        return step

    def record_verifier_feedback(
        self, feedback: FeedbackDigest | dict[str, Any]
    ) -> None:
        """Record verifier feedback and update the medium if present."""

        payload = to_jsonable(feedback)
        self._append(VERIFIER_FEEDBACK_EVENT, {"feedback": payload})
        if self.medium is not None:
            self.medium.update_from_feedback(
                feedback,
                event_log=self.event_log,
                run_id=self.run_id,
                instance_id=self.instance_id,
                actor="v12_medium",
            )

    def _local_view(
        self,
        *,
        objective: str,
        migration_context: Any,
        current_best: dict[str, Any] | None,
    ) -> AgentLocalView:
        if self.medium is not None:
            kwargs = {
                "objective": objective,
                "migration_context": migration_context,
                "current_best": current_best,
                "tool_registry": self.registry.names(),
                "event_log": self.event_log,
                "run_id": self.run_id,
                "instance_id": self.instance_id,
                "actor": self.actor,
            }
            if self.forbidden_tools:
                kwargs["forbidden_tools"] = self.forbidden_tools
            return self.medium.local_view(**kwargs)
        context_payload = (
            migration_context.to_dict()
            if hasattr(migration_context, "to_dict")
            else dict(migration_context or {})
        )
        return AgentLocalView(
            objective=objective,
            migration_context=context_payload,
            current_best=current_best,
            tool_registry=self.registry.names(),
            forbidden_tools=dict(self.forbidden_tools),
        )

    def _append(self, event_type: str, payload: dict[str, Any]) -> None:
        if self.event_log is None:
            return
        self.event_log.append(
            run_id=self.run_id,
            instance_id=self.instance_id,
            event_type=event_type,
            actor=self.actor,
            payload=payload,
        )

    def _emit_tool_choice_failure(self, error: ToolChoiceError) -> None:
        self._append(AGENT_TOOL_CALL_PARSE_FAILED_EVENT, {"error": error.to_dict()})


def assert_same_tools_available_s2_and_v12(
    s2_registry: ToolRegistry | None = None,
    v12_registry: ToolRegistry | None = None,
) -> None:
    """Raise if S2 and V12 do not expose identical tool names."""

    s2 = s2_registry or build_default_tool_registry()
    v12 = v12_registry or build_default_tool_registry()
    if s2.names() != v12.names():
        raise AssertionError(f"S2/V12 tool mismatch: {s2.names()} != {v12.names()}")


def _tool_recommendation_context(
    *,
    view: AgentLocalView,
    selected_tool: str,
) -> dict[str, Any]:
    annotations = view.tool_annotations or {}
    strong = tuple(
        tool
        for tool, annotation in annotations.items()
        if annotation.get("recommendation") == "strong_support"
    )
    selected_annotation = annotations.get(selected_tool) or {}
    selected_recommendation = str(
        selected_annotation.get("recommendation") or "unannotated"
    )
    return {
        "strongly_supported_tools": list(sorted(strong)),
        "selected_recommendation": selected_recommendation,
        "selected_is_inhibited": selected_recommendation in {"caution", "inhibited"}
        or float(selected_annotation.get("inhibition") or 0.0) > 0.0,
        "selected_is_forbidden": selected_tool in view.forbidden_tools,
        "ignored_strongly_supported_tools": [
            tool for tool in sorted(strong) if tool != selected_tool
        ],
    }


def _with_execution_context_metadata(
    result: ToolResult,
    context: ToolExecutionContext,
) -> ToolResult:
    metadata = dict(result.metadata or {})
    if context.metadata:
        metadata["execution_context"] = redact_secrets(dict(context.metadata))
    return result.model_copy(update={"metadata": metadata})


def redact_secrets(value: Any) -> Any:
    """Return a trace-safe copy with common secret-bearing fields redacted."""

    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            if _is_secret_key(str(key)):
                redacted[str(key)] = "[REDACTED]"
            else:
                redacted[str(key)] = redact_secrets(item)
        return redacted
    if isinstance(value, list):
        return [redact_secrets(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_secrets(item) for item in value)
    if isinstance(value, str):
        return _redact_secret_string(value)
    return value


def _is_secret_key(key: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]+", "_", key.lower()).strip("_")
    if normalized in {"authorization", "bearer", "secret", "password", "token"}:
        return True
    if normalized.endswith("_secret") or normalized.endswith("_password"):
        return True
    if normalized.endswith("_api_key") or normalized == "api_key":
        return True
    if normalized in {"access_token", "refresh_token", "id_token"}:
        return True
    return False


def _redact_secret_string(value: str) -> str:
    redacted = re.sub(
        r"""(?ix)
        \b(authorization\b\s*[:=]\s*)Bearer\s+[^\s"',;}\]]+
        """,
        r"\1[REDACTED]",
        value,
    )
    redacted = re.sub(
        r"""(?ix)\b(Bearer\s+)[^\s"',;}\]]+""",
        r"\1[REDACTED]",
        redacted,
    )
    redacted = re.sub(
        r"""(?ix)
        (
            ["']?
            (?:api[_-]?key|authorization|secret|password|access[_-]?token|refresh[_-]?token|id[_-]?token|token)
            ["']?
            \s*[:=]\s*
            ["']
        )
        [^"']*
        (["'])
        """,
        r"\1[REDACTED]\2",
        redacted,
    )
    redacted = re.sub(
        r"""(?ix)
        (
            \b(?:api[_-]?key|authorization|secret|password|access[_-]?token|refresh[_-]?token|id[_-]?token|token)
            \b\s*[:=]\s*
            (?!["'])
        )
        [^\s,;}\]]+
        """,
        r"\1[REDACTED]",
        redacted,
    )
    return re.sub(r"\[REDACTED\]\]+", "[REDACTED]", redacted)


def build_llm_trace_payload(
    *,
    call: ToolCall,
    raw_response: str,
    available_tools: Iterable[str],
    usage: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a complete local LLM trace payload with secret redaction."""

    return redact_secrets(
        {
            "schema_version": "v12.llm_tool_trace.v1",
            "raw_response": raw_response,
            "tool_call": call.model_dump(mode="json"),
            "available_tools": list(available_tools),
            "usage": usage or {},
            "metadata": metadata or {},
        }
    )


__all__ = [
    "AGENT_TOOL_CALL_PARSE_FAILED_EVENT",
    "AGENT_TOOL_CALL_REQUESTED_EVENT",
    "CANDIDATE_CREATED_BY_AGENT_EVENT",
    "TOOL_EXECUTED_EVENT",
    "TOOL_PROPOSAL_RETURNED_EVENT",
    "VERIFIER_FEEDBACK_EVENT",
    "AgentLoop",
    "AgentStep",
    "ToolChoiceError",
    "ToolContextPreparer",
    "V12_EXPERIMENTAL_ARMS",
    "V12ExperimentalArm",
    "assert_same_tools_available_s2_and_v12",
    "build_llm_trace_payload",
    "redact_secrets",
]
