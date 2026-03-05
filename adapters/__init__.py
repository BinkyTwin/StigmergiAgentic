"""Domain adapter contracts and implementations."""

from .assistant import AssistantAdapter, LocalWorkspace, WorkspacePathError
from .base import DomainAdapter, Objective, Workspace
from .travelplanner import TravelPlannerAdapter, TravelPlannerEvaluator, TravelPlannerWorkspace

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
