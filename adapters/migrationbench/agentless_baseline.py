"""Agentless/self-debug fallback baseline for MigrationBench."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from llm.client import LLMClient

from .evaluator import MigrationBenchEvaluator
from .schemas import MigrationBenchInstance
from .scientific_baselines import run_llm_patch_baseline


def run_agentless_self_debug(
    *,
    instance: MigrationBenchInstance,
    workspace_root: Path,
    output_dir: Path,
    evaluator: MigrationBenchEvaluator,
    llm_client: LLMClient | None,
    seed: int = 42,
    force: bool = False,
    max_iterations: int = 3,
) -> dict[str, Any]:
    """Local fallback when official SD-Feedback cannot run."""
    return run_llm_patch_baseline(
        instance=instance,
        workspace_root=workspace_root,
        output_dir=output_dir,
        evaluator=evaluator,
        llm_client=llm_client,
        framework="agentless_self_debug",
        strategy=(
            "agentless self-debug baseline: inspect repository, propose typed edits, "
            "run build/test feedback, repair only concrete failures"
        ),
        seed=seed,
        force=force,
        repair_cycles=max(0, int(max_iterations) - 1),
    )
