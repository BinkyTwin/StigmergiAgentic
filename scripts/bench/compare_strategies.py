"""V10 ablation harness — compare A1/A2/A3 on the same subset.

This script runs the unified :mod:`scripts.bench.harness` once per ablation arm
on the same JSONL subset and aggregates a ``comparison.json`` with strict
success counts, dedup/suppression totals, and selection rationales.

The arms are configured to isolate the contribution of branching and
verifier-driven repair on top of the verifier-first baseline:

- A1 ``agentless_basic``: single candidate, no repair (verifier-first only).
- A2 ``branching_repair`` with ``max_candidates=1`` and one repair round:
  linear single-track repair without fan-out (placeholder for the typed
  blackboard arm pending its Phase 3 capability matching follow-up).
- A3 ``branching_repair`` with branching enabled (``max_candidates>=2``,
  ``max_repairs_per_candidate>=2``): parallel branches with signature dedup,
  repeated-failure suppression, and explainable selection.

Each arm writes a self-contained campaign tree under ``out_dir/<arm_name>``
with its own manifest, EventLog, hypotheses graph, runs.jsonl, and
summary.json. The ``comparison.json`` summarizes every arm side-by-side.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from scripts.bench.harness import (
    BenchHarness,
    HarnessOptions,
    HarnessRegistry,
    default_registry,
)
from scripts.bench.telemetry import Summary


@dataclass(frozen=True)
class AblationArm:
    """One leg of the A1/A2/A3 comparison."""

    arm_id: str
    strategy_name: str
    max_candidates: int
    max_repair_rounds: int
    max_repairs_per_candidate: int
    description: str = ""

    def options(
        self,
        *,
        adapter_name: str,
        subset_path: Path,
        out_dir: Path,
        seed: int,
        limit: int | None,
        extras: dict[str, Any] | None,
    ) -> HarnessOptions:
        """Materialize :class:`HarnessOptions` for this arm under ``out_dir``."""

        return HarnessOptions(
            adapter_name=adapter_name,
            strategy_name=self.strategy_name,
            subset_path=subset_path,
            out_dir=out_dir / self.arm_id,
            seed=seed,
            limit=limit,
            max_candidates=self.max_candidates,
            max_repair_rounds=self.max_repair_rounds,
            max_repairs_per_candidate=self.max_repairs_per_candidate,
            extras=dict(extras or {}),
        )


DEFAULT_ARMS: tuple[AblationArm, ...] = (
    AblationArm(
        arm_id="A1_agentless_basic",
        strategy_name="agentless_basic",
        max_candidates=1,
        max_repair_rounds=0,
        max_repairs_per_candidate=1,
        description="A1 — verifier-first single shot, no repair.",
    ),
    AblationArm(
        arm_id="A2_linear_repair",
        strategy_name="branching_repair",
        max_candidates=1,
        max_repair_rounds=1,
        max_repairs_per_candidate=1,
        description="A2 — linear single-track verifier-driven repair (no fan-out).",
    ),
    AblationArm(
        arm_id="A3_branching_repair",
        strategy_name="branching_repair",
        max_candidates=2,
        max_repair_rounds=1,
        max_repairs_per_candidate=2,
        description=(
            "A3 — branching parallel repair with signature dedup, "
            "repeated-failure suppression, explainable selection."
        ),
    ),
    AblationArm(
        arm_id="A4_stigmergic_blackboard",
        strategy_name="stigmergic_blackboard",
        max_candidates=2,
        max_repair_rounds=1,
        max_repairs_per_candidate=2,
        description=(
            "A4 — A3 + active stigmergic signal layer "
            "(support/inhibit/reinforce/decay/novelty)."
        ),
    ),
)


def run_comparison(
    *,
    adapter_name: str,
    subset_path: Path,
    out_dir: Path,
    seed: int = 42,
    limit: int | None = None,
    extras: dict[str, Any] | None = None,
    arms: Sequence[AblationArm] = DEFAULT_ARMS,
    registry: HarnessRegistry | None = None,
) -> dict[str, Any]:
    """Run each arm sequentially and aggregate a comparison.json document."""

    out_dir.mkdir(parents=True, exist_ok=True)
    used_registry = registry or default_registry()
    arm_summaries: dict[str, Summary] = {}
    arm_payloads: list[dict[str, Any]] = []

    for arm in arms:
        options = arm.options(
            adapter_name=adapter_name,
            subset_path=subset_path,
            out_dir=out_dir,
            seed=seed,
            limit=limit,
            extras=extras,
        )
        summary = BenchHarness(options, used_registry).run()
        arm_summaries[arm.arm_id] = summary
        arm_payloads.append(_arm_payload(arm, summary))

    comparison = {
        "subset_path": str(subset_path),
        "adapter_name": adapter_name,
        "out_dir": str(out_dir),
        "seed": int(seed),
        "limit": int(limit) if limit is not None else None,
        "arms": arm_payloads,
    }
    target = out_dir / "comparison.json"
    target.write_text(
        json.dumps(comparison, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return comparison


def _arm_payload(arm: AblationArm, summary: Summary) -> dict[str, Any]:
    instances = [
        {
            "instance_id": inst.instance_id,
            "strict_success": bool(inst.strict_success),
            "stop_reason": inst.stop_reason,
            "candidate_count": int(inst.candidate_count),
            "dedup_skipped": int(inst.dedup_skipped),
            "repeat_failure_suppressed": int(inst.repeat_failure_suppressed),
            "selected_hypothesis_id": inst.selected_hypothesis_id,
            "selection_rationale": inst.selection_rationale,
            "signal_emitted_count": int(inst.signal_emitted_count),
            "signal_applied_count": int(inst.signal_applied_count),
            "pheromone_hit_rate": float(inst.pheromone_hit_rate),
            "feedback_reuse_rate": float(inst.feedback_reuse_rate),
            "repeated_failure_suppression": int(inst.repeated_failure_suppression),
        }
        for inst in summary.instances
    ]
    return {
        "arm_id": arm.arm_id,
        "strategy_name": arm.strategy_name,
        "description": arm.description,
        "config": {
            "max_candidates": int(arm.max_candidates),
            "max_repair_rounds": int(arm.max_repair_rounds),
            "max_repairs_per_candidate": int(arm.max_repairs_per_candidate),
        },
        "campaign_id": summary.campaign_id,
        "instance_count": int(summary.instance_count),
        "strict_success_count": int(summary.strict_success_count),
        "by_signal": dict(summary.by_signal),
        "dedup_skipped_total": int(summary.dedup_skipped_total),
        "repeat_failure_suppressed_total": int(summary.repeat_failure_suppressed_total),
        "signal_emitted_total": int(summary.signal_emitted_total),
        "signal_applied_total": int(summary.signal_applied_total),
        "pheromone_hit_rate": float(summary.pheromone_hit_rate),
        "feedback_reuse_rate": float(summary.feedback_reuse_rate),
        "repeated_failure_suppression_total": int(
            summary.repeated_failure_suppression_total
        ),
        "instances": instances,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="scripts.bench.compare_strategies",
        description=__doc__,
    )
    parser.add_argument(
        "--adapter",
        required=True,
        help="Adapter name registered in the bench harness registry.",
    )
    parser.add_argument(
        "--subset",
        required=True,
        type=Path,
        help="Path to a JSONL subset reused by every arm.",
    )
    parser.add_argument(
        "--out-dir",
        required=True,
        type=Path,
        help="Comparison output directory (one campaign tree per arm).",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--extras",
        default="{}",
        help="JSON dict forwarded to each arm's adapter factory.",
    )
    parser.add_argument(
        "--arms",
        nargs="*",
        default=None,
        help="Optional whitelist of arm_ids to run (default: all DEFAULT_ARMS).",
    )
    parser.add_argument(
        "--max-candidates",
        type=int,
        default=None,
        help="Override max_candidates on every selected arm.",
    )
    parser.add_argument(
        "--max-repair-rounds",
        type=int,
        default=None,
        help="Override max_repair_rounds on every selected arm.",
    )
    parser.add_argument(
        "--max-repairs-per-candidate",
        type=int,
        default=None,
        help="Override max_repairs_per_candidate on every selected arm.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    extras = json.loads(args.extras or "{}")
    arms = DEFAULT_ARMS
    if args.arms:
        wanted = set(args.arms)
        unknown = wanted - {arm.arm_id for arm in DEFAULT_ARMS}
        if unknown:
            raise SystemExit(f"unknown arm_ids: {sorted(unknown)}")
        arms = tuple(arm for arm in DEFAULT_ARMS if arm.arm_id in wanted)
    if (
        args.max_candidates is not None
        or args.max_repair_rounds is not None
        or args.max_repairs_per_candidate is not None
    ):
        from dataclasses import replace as _dc_replace
        arms = tuple(
            _dc_replace(
                arm,
                max_candidates=(
                    int(args.max_candidates)
                    if args.max_candidates is not None
                    else arm.max_candidates
                ),
                max_repair_rounds=(
                    int(args.max_repair_rounds)
                    if args.max_repair_rounds is not None
                    else arm.max_repair_rounds
                ),
                max_repairs_per_candidate=(
                    int(args.max_repairs_per_candidate)
                    if args.max_repairs_per_candidate is not None
                    else arm.max_repairs_per_candidate
                ),
            )
            for arm in arms
        )
    comparison = run_comparison(
        adapter_name=args.adapter,
        subset_path=Path(args.subset),
        out_dir=Path(args.out_dir),
        seed=int(args.seed),
        limit=args.limit,
        extras=extras,
        arms=arms,
    )
    print(json.dumps(comparison, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())


__all__ = [
    "AblationArm",
    "DEFAULT_ARMS",
    "build_parser",
    "main",
    "run_comparison",
]
