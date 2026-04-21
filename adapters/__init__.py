"""Domain adapter exports with lazy imports."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

__all__ = [
    "AssistantAdapter",
    "DomainAdapter",
    "LocalWorkspace",
    "Objective",
    "TravelPlannerAdapter",
    "TravelPlannerEvaluator",
    "TravelPlannerWorkspace",
    "Workspace",
    "WorkspacePathError",
]

if TYPE_CHECKING:
    from .assistant import AssistantAdapter, LocalWorkspace, WorkspacePathError
    from .base import DomainAdapter, Objective, Workspace
    from .travelplanner import (
        TravelPlannerAdapter,
        TravelPlannerEvaluator,
        TravelPlannerWorkspace,
    )


def __getattr__(name: str) -> Any:
    if name in {"DomainAdapter", "Objective", "Workspace"}:
        from .base import DomainAdapter, Objective, Workspace

        mapping = {
            "DomainAdapter": DomainAdapter,
            "Objective": Objective,
            "Workspace": Workspace,
        }
        return mapping[name]
    if name in {"AssistantAdapter", "LocalWorkspace", "WorkspacePathError"}:
        from .assistant import AssistantAdapter, LocalWorkspace, WorkspacePathError

        mapping = {
            "AssistantAdapter": AssistantAdapter,
            "LocalWorkspace": LocalWorkspace,
            "WorkspacePathError": WorkspacePathError,
        }
        return mapping[name]
    if name in {
        "TravelPlannerAdapter",
        "TravelPlannerEvaluator",
        "TravelPlannerWorkspace",
    }:
        from .travelplanner import (
            TravelPlannerAdapter,
            TravelPlannerEvaluator,
            TravelPlannerWorkspace,
        )

        mapping = {
            "TravelPlannerAdapter": TravelPlannerAdapter,
            "TravelPlannerEvaluator": TravelPlannerEvaluator,
            "TravelPlannerWorkspace": TravelPlannerWorkspace,
        }
        return mapping[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
