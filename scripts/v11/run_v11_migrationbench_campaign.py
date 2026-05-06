"""Run the V11 B2/B5/B6 MigrationBench ladder with readiness checks.

This is the launch path for controlled V11 MigrationBench smokes and main_30.
It runs the same subset across B2/B5/B6, verifies every arm by EventLog replay,
and writes a readiness report next to ``comparison.json``.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any, Sequence

from scripts.bench.compare_strategies import V11_ARMS, AblationArm, run_comparison
from scripts.bench.telemetry import replay_summary_from_dir


DEFAULT_SMOKE_SUBSET = Path("fixtures/migrationbench/subsets/smoke_5.jsonl")
DEFAULT_MAIN30_SUBSET = Path("fixtures/migrationbench/subsets/main_30.jsonl")


def _clean_path(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def _clean_dir_contents(path: Path) -> None:
    if not path.exists():
        return
    if not path.is_dir():
        path.unlink()
        return
    for child in path.iterdir():
        _clean_path(child)


def _count_jsonl(path: Path) -> int:
    with path.open("r", encoding="utf-8") as stream:
        return sum(1 for line in stream if line.strip())


def _selected_arms(
    *,
    max_candidates: int | None,
    max_repair_rounds: int | None,
    max_repairs_per_candidate: int | None,
) -> tuple[AblationArm, ...]:
    if (
        max_candidates is None
        and max_repair_rounds is None
        and max_repairs_per_candidate is None
    ):
        return V11_ARMS
    return tuple(
        replace(
            arm,
            max_candidates=(
                int(max_candidates) if max_candidates is not None else arm.max_candidates
            ),
            max_repair_rounds=(
                int(max_repair_rounds)
                if max_repair_rounds is not None
                else arm.max_repair_rounds
            ),
            max_repairs_per_candidate=(
                int(max_repairs_per_candidate)
                if max_repairs_per_candidate is not None
                else arm.max_repairs_per_candidate
            ),
        )
        for arm in V11_ARMS
    )


def _build_extras(args: argparse.Namespace) -> dict[str, Any]:
    extras: dict[str, Any] = {
        "workspace_root_root": str(args.workspace_root),
        "artifacts_root": str(args.out_dir / "artifacts"),
        "migrationbench_root": str(args.migrationbench_root),
        "official_eval": bool(args.official_eval),
        "official_timeout_seconds": float(args.official_timeout_seconds),
        "prepare": True,
        "out_dir": str(args.out_dir),
        "use_llm_providers": bool(args.use_llm_providers),
        "llm_initial_candidates": int(args.llm_initial_candidates),
        "llm_repair_candidates": int(args.llm_repair_candidates),
        "b6_fallback_policy": str(args.b6_fallback_policy),
    }
    if args.use_llm_providers:
        extras["llm"] = {
            "provider": args.llm_provider,
            "model": args.llm_model,
            "base_url": args.llm_base_url,
            "timeout_seconds": float(args.llm_timeout_seconds),
            "max_tokens": int(args.llm_max_tokens),
        }
    return extras


def _replay_parity(out_dir: Path, arm_ids: Sequence[str]) -> dict[str, Any]:
    by_arm: dict[str, bool] = {}
    errors: dict[str, str] = {}
    for arm_id in arm_ids:
        arm_dir = out_dir / arm_id
        try:
            live = json.loads((arm_dir / "summary.json").read_text(encoding="utf-8"))
            replay = replay_summary_from_dir(arm_dir).to_dict()
            by_arm[arm_id] = live == replay
            if live != replay:
                errors[arm_id] = "summary_mismatch"
        except Exception as exc:  # noqa: BLE001
            by_arm[arm_id] = False
            errors[arm_id] = f"{type(exc).__name__}:{exc}"
    return {
        "ok": all(by_arm.values()) if by_arm else False,
        "by_arm": by_arm,
        "errors": errors,
    }


def _pairwise_divergence(comparison: dict[str, Any]) -> list[dict[str, Any]]:
    arms = {arm["arm_id"]: arm for arm in comparison.get("arms", [])}
    control = arms.get("B2_branching_repair")
    if control is None:
        return []
    control_instances = {
        inst["instance_id"]: inst for inst in control.get("instances", [])
    }
    rows: list[dict[str, Any]] = []
    for treatment_id in ("B5_stigmergic_scheduler", "B6_operator_search"):
        treatment = arms.get(treatment_id)
        if treatment is None:
            continue
        diverged = 0
        instance_rows: list[dict[str, Any]] = []
        for inst in treatment.get("instances", []):
            control_inst = control_instances.get(inst["instance_id"])
            if control_inst is None:
                continue
            reasons: list[str] = []
            for key in ("selected_hypothesis_id", "stop_reason", "strict_success"):
                if control_inst.get(key) != inst.get(key):
                    reasons.append(key)
            if int(inst.get("decision_influenced_count") or 0) > 0:
                reasons.append("decision_influenced")
            if int(inst.get("operator_applied_count") or 0) > 0:
                reasons.append("operator_applied")
            is_diverged = bool(reasons)
            diverged += int(is_diverged)
            instance_rows.append(
                {
                    "instance_id": inst["instance_id"],
                    "diverged": is_diverged,
                    "reasons": reasons,
                    "control_selected": control_inst.get("selected_hypothesis_id"),
                    "treatment_selected": inst.get("selected_hypothesis_id"),
                    "control_strict_success": bool(control_inst.get("strict_success")),
                    "treatment_strict_success": bool(inst.get("strict_success")),
                }
            )
        total = len(instance_rows)
        rows.append(
            {
                "control_arm": "B2_branching_repair",
                "treatment_arm": treatment_id,
                "divergence_count": diverged,
                "instance_count": total,
                "divergence_rate": diverged / float(total) if total else 0.0,
                "instances": instance_rows,
            }
        )
    return rows


def _causal_activation_ok(arms: dict[str, dict[str, Any]]) -> bool:
    """Require causal activation only when B5/B6 encountered repairable failures."""

    for arm_id in ("B5_stigmergic_scheduler", "B6_operator_search"):
        arm = arms.get(arm_id, {})
        needs_repair = (
            int(arm.get("validation_failed_total") or 0)
            + int(arm.get("validation_error_total") or 0)
            + int(arm.get("validation_partial_total") or 0)
        ) > 0
        if not needs_repair:
            continue
        if int(arm.get("signal_read_total") or 0) <= 0:
            return False
        if int(arm.get("decision_influenced_total") or 0) <= 0:
            return False
    return True


def _readiness_report(
    *,
    comparison: dict[str, Any],
    out_dir: Path,
    subset_path: Path,
    limit: int | None,
    official_eval: bool,
    use_llm_providers: bool,
) -> dict[str, Any]:
    arm_ids = [arm["arm_id"] for arm in comparison.get("arms", [])]
    parity = _replay_parity(out_dir, arm_ids)
    expected_instances = min(_count_jsonl(subset_path), limit) if limit else _count_jsonl(subset_path)
    arms = {arm["arm_id"]: arm for arm in comparison.get("arms", [])}

    denominator_ok = all(
        int(arm.get("instance_count") or 0) == expected_instances
        for arm in comparison.get("arms", [])
    )
    b5 = arms.get("B5_stigmergic_scheduler", {})
    b6 = arms.get("B6_operator_search", {})
    causal_active = _causal_activation_ok(arms)
    operator_surface_present = "operator_invoked_total" in b6 and "operator_applied_total" in b6
    checks = {
        "replay_parity": bool(parity["ok"]),
        "full_denominator": bool(denominator_ok),
        "causal_activation": bool(causal_active),
        "operator_surface_present": bool(operator_surface_present),
    }
    ready = all(checks.values())
    return {
        "ready_for_main30_launch": bool(ready),
        "subset_path": str(subset_path),
        "expected_instances": int(expected_instances),
        "official_eval": bool(official_eval),
        "use_llm_providers": bool(use_llm_providers),
        "checks": checks,
        "replay_parity": parity,
        "pairwise_divergence": _pairwise_divergence(comparison),
        "arm_metrics": {
            arm_id: {
                "strict_success_count": int(arm.get("strict_success_count") or 0),
                "signal_read_total": int(arm.get("signal_read_total") or 0),
                "decision_influenced_total": int(
                    arm.get("decision_influenced_total") or 0
                ),
                "trajectory_divergence_total": int(
                    arm.get("trajectory_divergence_total") or 0
                ),
                "operator_invoked_total": int(arm.get("operator_invoked_total") or 0),
                "operator_applied_total": int(arm.get("operator_applied_total") or 0),
                "apply_ok_total": int(arm.get("apply_ok_total") or 0),
                "validation_completed_total": int(
                    arm.get("validation_completed_total") or 0
                ),
                "validation_passed_total": int(arm.get("validation_passed_total") or 0),
                "validation_partial_total": int(arm.get("validation_partial_total") or 0),
                "validation_failed_total": int(arm.get("validation_failed_total") or 0),
                "validation_error_total": int(arm.get("validation_error_total") or 0),
                "replacement_count_too_low_total": int(
                    arm.get("replacement_count_too_low_total") or 0
                ),
                "replacement_count_too_low_rate": float(
                    arm.get("replacement_count_too_low_rate") or 0.0
                ),
            }
            for arm_id, arm in arms.items()
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--subset",
        type=Path,
        default=DEFAULT_SMOKE_SUBSET,
        help="MigrationBench JSONL subset. Use --main30 for the registered main_30 subset.",
    )
    parser.add_argument(
        "--main30",
        action="store_true",
        help="Use fixtures/migrationbench/subsets/main_30.jsonl and main30 defaults.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("campaign_results/v11/migrationbench_smoke"),
    )
    parser.add_argument("--workspace-root", type=Path, default=Path("workspaces/migrationbench_v11"))
    parser.add_argument("--migrationbench-root", type=Path, default=Path("external/MigrationBench"))
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--official-eval", action="store_true")
    parser.add_argument("--official-timeout-seconds", type=float, default=1800.0)
    parser.add_argument("--use-llm-providers", action="store_true")
    parser.add_argument("--llm-provider", default="deepseek")
    parser.add_argument("--llm-model", default="deepseek-chat")
    parser.add_argument("--llm-base-url", default="https://api.deepseek.com/v1")
    parser.add_argument("--llm-timeout-seconds", type=float, default=180.0)
    parser.add_argument("--llm-max-tokens", type=int, default=3000)
    parser.add_argument("--llm-initial-candidates", type=int, default=2)
    parser.add_argument("--llm-repair-candidates", type=int, default=2)
    parser.add_argument(
        "--b6-fallback-policy",
        choices=("disabled", "guarded_only", "free_llm"),
        default="guarded_only",
        help="B6 LLM repair fallback policy. Scientific campaigns must not use free_llm.",
    )
    parser.add_argument("--max-candidates", type=int, default=None)
    parser.add_argument("--max-repair-rounds", type=int, default=None)
    parser.add_argument("--max-repairs-per-candidate", type=int, default=None)
    parser.add_argument("--no-clean", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.main30:
        args.subset = DEFAULT_MAIN30_SUBSET
        if args.out_dir == Path("campaign_results/v11/migrationbench_smoke"):
            args.out_dir = Path("campaign_results/v11/migrationbench_main30")
        args.official_eval = True if not args.official_eval else args.official_eval
        args.use_llm_providers = True if not args.use_llm_providers else args.use_llm_providers

    if not args.subset.exists():
        raise SystemExit(f"subset not found: {args.subset}")
    if args.official_eval and not (args.migrationbench_root / "src" / "migration_bench" / "run_eval.py").exists():
        raise SystemExit(
            "official evaluator missing; clone MigrationBench under "
            f"{args.migrationbench_root} or use Docker service"
        )

    if not args.no_clean:
        _clean_path(args.out_dir)
        _clean_dir_contents(args.workspace_root)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    args.workspace_root.mkdir(parents=True, exist_ok=True)

    arms = _selected_arms(
        max_candidates=args.max_candidates,
        max_repair_rounds=args.max_repair_rounds,
        max_repairs_per_candidate=args.max_repairs_per_candidate,
    )
    comparison = run_comparison(
        adapter_name="migrationbench",
        subset_path=args.subset,
        out_dir=args.out_dir,
        seed=int(args.seed),
        limit=args.limit,
        extras=_build_extras(args),
        arms=arms,
    )
    report = _readiness_report(
        comparison=comparison,
        out_dir=args.out_dir,
        subset_path=args.subset,
        limit=args.limit,
        official_eval=bool(args.official_eval),
        use_llm_providers=bool(args.use_llm_providers),
    )
    report_path = args.out_dir / "v11_readiness_report.json"
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": "ok" if report["ready_for_main30_launch"] else "needs_attention",
                "ready_for_main30_launch": report["ready_for_main30_launch"],
                "comparison_path": str(args.out_dir / "comparison.json"),
                "readiness_report": str(report_path),
            },
            sort_keys=True,
        )
    )
    return 0 if report["ready_for_main30_launch"] else 2


if __name__ == "__main__":
    sys.exit(main())


__all__ = [
    "DEFAULT_MAIN30_SUBSET",
    "DEFAULT_SMOKE_SUBSET",
    "build_parser",
    "main",
]
