"""Strict V12 tool-use schemas.

The LLM may decide which tool to call and with which arguments. The medium and
the scheduler may recommend or inhibit tools, but they must not create patches.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


JsonDict = dict[str, Any]


class ToolCall(BaseModel):
    """One LLM-selected tool invocation."""

    model_config = ConfigDict(extra="forbid")

    tool_name: str
    arguments: JsonDict = Field(default_factory=dict)
    rationale: str = ""
    call_id: str | None = None

    @field_validator("tool_name")
    @classmethod
    def _tool_name_non_empty(cls, value: str) -> str:
        value = str(value).strip()
        if not value:
            raise ValueError("tool_name cannot be empty")
        return value


class ToolSpec(BaseModel):
    """Agent-facing tool description."""

    model_config = ConfigDict(extra="forbid")

    name: str
    description: str
    input_schema: JsonDict = Field(default_factory=dict)
    mutates_workspace: bool = False
    creates_candidate: bool = False
    proposal_only: bool = False
    tags: tuple[str, ...] = ()

    @field_validator("name")
    @classmethod
    def _name_non_empty(cls, value: str) -> str:
        value = str(value).strip()
        if not value:
            raise ValueError("tool spec name cannot be empty")
        return value


class ToolProposal(BaseModel):
    """A structured suggestion returned by a proposal-only tool."""

    model_config = ConfigDict(extra="forbid")

    proposal_id: str
    kind: str
    title: str
    rationale: str
    suggested_edits: list[JsonDict] = Field(default_factory=list)
    suggested_commands: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    applies_patch: bool = False
    metadata: JsonDict = Field(default_factory=dict)

    @model_validator(mode="after")
    def _proposal_must_not_apply(self) -> "ToolProposal":
        if self.applies_patch:
            raise ValueError("ToolProposal cannot apply a patch")
        return self


class ToolResult(BaseModel):
    """Result returned by deterministic tool execution."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    tool_name: str
    status: Literal["success", "failed", "rejected"]
    summary: str = ""
    output: JsonDict = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)
    proposal: ToolProposal | None = None
    workspace_mutated: bool = False
    candidate_created: bool = False
    metadata: JsonDict = Field(default_factory=dict)

    @property
    def ok(self) -> bool:
        """Return whether the tool completed successfully."""

        return self.status == "success"

    @classmethod
    def success(
        cls,
        *,
        tool_name: str,
        summary: str = "",
        output: JsonDict | None = None,
        proposal: ToolProposal | None = None,
        workspace_mutated: bool = False,
        candidate_created: bool = False,
        metadata: JsonDict | None = None,
    ) -> "ToolResult":
        return cls(
            tool_name=tool_name,
            status="success",
            summary=summary,
            output=output or {},
            proposal=proposal,
            workspace_mutated=workspace_mutated,
            candidate_created=candidate_created,
            metadata=metadata or {},
        )

    @classmethod
    def rejected(
        cls,
        *,
        tool_name: str,
        summary: str,
        errors: list[str] | None = None,
        metadata: JsonDict | None = None,
    ) -> "ToolResult":
        return cls(
            tool_name=tool_name,
            status="rejected",
            summary=summary,
            errors=errors or [],
            metadata=metadata or {},
        )

    @classmethod
    def failed(
        cls,
        *,
        tool_name: str,
        summary: str,
        errors: list[str] | None = None,
        metadata: JsonDict | None = None,
    ) -> "ToolResult":
        return cls(
            tool_name=tool_name,
            status="failed",
            summary=summary,
            errors=errors or [],
            metadata=metadata or {},
        )
