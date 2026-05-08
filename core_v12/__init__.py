"""V12 autonomous-agent runtime over a stigmergic medium.

Keep this package initializer light. Importing submodules such as
``core_v12.sd_feedback`` should not force the full agent loop, tool executor,
provider stack, or MigrationBench adapter tree to load.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any


_EXPORTS: dict[str, tuple[str, str]] = {
    "AgentLoop": ("core_v12.agent_loop", "AgentLoop"),
    "PatchProposal": ("core_v12.sd_feedback", "PatchProposal"),
    "ToolRecommendationMetrics": ("core_v12.metrics", "ToolRecommendationMetrics"),
    "V12_EXPERIMENTAL_ARMS": ("core_v12.agent_loop", "V12_EXPERIMENTAL_ARMS"),
    "V12_4_EXPERIMENTAL_ARMS": ("core_v12.sd_feedback", "V12_4_EXPERIMENTAL_ARMS"),
    "assert_same_tools_available_s2_and_v12": (
        "core_v12.agent_loop",
        "assert_same_tools_available_s2_and_v12",
    ),
    "guard_patch_proposal": ("core_v12.sd_feedback", "guard_patch_proposal"),
    "summarize_tool_recommendation_metrics": (
        "core_v12.metrics",
        "summarize_tool_recommendation_metrics",
    ),
}


def __getattr__(name: str) -> Any:
    try:
        module_name, attr_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(name) from exc
    module = import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


__all__ = sorted(_EXPORTS)
