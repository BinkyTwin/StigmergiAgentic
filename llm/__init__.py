"""LLM package exports with lazy imports to keep prompt-only users lightweight."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

__all__ = [
    "LLMClient",
    "LLMResponse",
    "ModelPricing",
    "SYSTEM_PROTOCOL_COMPILER",
    "SYSTEM_STIGMERGIC_AGENT_PROMPT",
    "build_action_prompt",
    "build_protocol_compiler_prompt",
]

if TYPE_CHECKING:
    from .client import LLMClient, LLMResponse, ModelPricing
    from .prompts import (
        SYSTEM_PROTOCOL_COMPILER,
        SYSTEM_STIGMERGIC_AGENT_PROMPT,
        build_action_prompt,
        build_protocol_compiler_prompt,
    )


def __getattr__(name: str) -> Any:
    if name in {"LLMClient", "LLMResponse", "ModelPricing"}:
        from .client import LLMClient, LLMResponse, ModelPricing

        mapping = {
            "LLMClient": LLMClient,
            "LLMResponse": LLMResponse,
            "ModelPricing": ModelPricing,
        }
        return mapping[name]
    if name in {
        "SYSTEM_PROTOCOL_COMPILER",
        "SYSTEM_STIGMERGIC_AGENT_PROMPT",
        "build_action_prompt",
        "build_protocol_compiler_prompt",
    }:
        from .prompts import (
            SYSTEM_PROTOCOL_COMPILER,
            SYSTEM_STIGMERGIC_AGENT_PROMPT,
            build_action_prompt,
            build_protocol_compiler_prompt,
        )

        mapping = {
            "SYSTEM_PROTOCOL_COMPILER": SYSTEM_PROTOCOL_COMPILER,
            "SYSTEM_STIGMERGIC_AGENT_PROMPT": SYSTEM_STIGMERGIC_AGENT_PROMPT,
            "build_action_prompt": build_action_prompt,
            "build_protocol_compiler_prompt": build_protocol_compiler_prompt,
        }
        return mapping[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
