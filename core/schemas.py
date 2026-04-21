"""Pydantic schemas for structured LLM/tool outputs."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


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


class ProtocolMarkerSpec(BaseModel):
    """One compiled protocol marker proposal."""

    model_config = ConfigDict(extra="ignore")

    id: str
    target: str
    eligible_actions: list[str] = Field(default_factory=list)
    intensity: float = 0.8
    depends_on: list[str] = Field(default_factory=list)
    priority: str | None = None
    marker_type: str = "task"
    payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("id", "target", "marker_type", mode="before")
    @classmethod
    def _require_non_empty_text(cls, value: Any) -> str:
        text = str(value or "").strip()
        if not text:
            raise ValueError("value cannot be empty")
        return text

    @field_validator("eligible_actions", "depends_on", mode="before")
    @classmethod
    def _normalize_string_list(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError("value must be a list")
        return [str(item).strip() for item in value if str(item).strip()]

    @field_validator("intensity", mode="before")
    @classmethod
    def _validate_intensity(cls, value: Any) -> float:
        intensity = float(value)
        if intensity < 0.1 or intensity > 1.0:
            raise ValueError("intensity must be in [0.1, 1.0]")
        return intensity


class ProtocolSpec(BaseModel):
    """Structured protocol topology emitted by the protocol compiler."""

    model_config = ConfigDict(extra="ignore")

    markers: list[ProtocolMarkerSpec] = Field(default_factory=list)


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


class TravelDayPlan(BaseModel):
    """One TravelPlanner day plan row."""

    model_config = ConfigDict(extra="ignore")

    current_city: str
    transportation: str
    breakfast: str
    attraction: str
    lunch: str
    dinner: str
    accommodation: str

    @field_validator(
        "current_city",
        "transportation",
        "breakfast",
        "attraction",
        "lunch",
        "dinner",
        "accommodation",
        mode="before",
    )
    @classmethod
    def _coerce_null_string_fields(cls, value: Any) -> Any:
        if value is None:
            return "-"
        return value


class TravelItineraryOutput(BaseModel):
    """Structured TravelPlanner itinerary output."""

    model_config = ConfigDict(extra="ignore")

    plan: list[TravelDayPlan] = Field(default_factory=list)
