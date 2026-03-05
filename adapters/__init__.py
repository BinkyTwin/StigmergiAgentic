"""Domain adapter contracts and implementations."""

from .assistant import AssistantAdapter, LocalWorkspace, WorkspacePathError
from .base import DomainAdapter, Objective, Workspace

__all__ = [
    "AssistantAdapter",
    "DomainAdapter",
    "LocalWorkspace",
    "Objective",
    "Workspace",
    "WorkspacePathError",
]
