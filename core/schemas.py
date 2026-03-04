"""Pydantic schemas for structured LLM/tool outputs."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ThinkOutput(BaseModel):
    """Structured response emitted by think prompts."""

    model_config = ConfigDict(extra="ignore")

    analysis: str
    next_action: str | None = None
    path: str | None = None
    command: str | None = None
    query: str | None = None
    write: dict[str, Any] | None = None


class SubtaskSpec(BaseModel):
    """One decomposed subtask plus dependency hints."""

    model_config = ConfigDict(extra="ignore")

    title: str
    description: str = ""
    depends_on_indices: list[int] = Field(default_factory=list)
    eligible_actions: list[str] = Field(default_factory=list)


class DecomposeOutput(BaseModel):
    """Structured decomposition output."""

    model_config = ConfigDict(extra="ignore")

    subtasks: list[SubtaskSpec] = Field(default_factory=list)


class ToolResult(BaseModel):
    """Generic structured output contract for tool-like responses."""

    model_config = ConfigDict(extra="ignore")

    success: bool
    output: str
    artifacts: dict[str, Any] = Field(default_factory=dict)


class LLMParsedResponse(BaseModel):
    """Wrapper that keeps both raw model output and parse status."""

    model_config = ConfigDict(extra="ignore")

    raw_content: str
    parsed: dict[str, Any] | None = None
    validation_error: str | None = None

    @property
    def is_valid(self) -> bool:
        return self.parsed is not None and not self.validation_error
