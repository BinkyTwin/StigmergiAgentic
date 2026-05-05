"""Scientific baselines for MigrationBench using the shared patch contract."""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any

from llm.client import LLMClient

from .evaluator import MigrationBenchEvaluator, build_strict_contract
from .schemas import MigrationBenchInstance, PatchStats, TypedEditSet, empty_output_contract
from .tools import (
    SYSTEM_MIGRATION_EDIT,
    build_edit_prompt,
    deterministic_java17_pom_edits,
    parse_typed_edit_set,
)
from .workspace import MigrationBenchWorkspace


def run_no_change(
    *,
    instance: MigrationBenchInstance,
    workspace_root: Path,
    output_dir: Path,
    evaluator: MigrationBenchEvaluator,
    framework: str = "no_change",
    provider: str = "",
    model: str = "",
    seed: int = 42,
    force: bool = False,
) -> dict[str, Any]:
    """Baseline that intentionally emits no patch; strict success must be false."""
    started = time.perf_counter()
    workspace = MigrationBenchWorkspace(instance=instance, root_dir=workspace_root)
    workspace.prepare(force=force)
    patch_path = output_dir / "patch.diff"
    patch_path.parent.mkdir(parents=True, exist_ok=True)
    patch_path.write_text("", encoding="utf-8")
    stats = PatchStats(patch_delivered=False)
    official = evaluator.evaluate_patch(
        instance=instance,
        patch_path=patch_path,
        output_dir=output_dir / "official",
        patch_stats=stats,
        patch_applies=False,
        patch_apply_reason="empty_patch",
    )
    return build_strict_contract(
        instance=instance,
        framework=framework,
        provider=provider,
        model=model,
        seed=seed,
        patch_path=patch_path,
        patch_stats=stats,
        patch_applies=False,
        patch_apply_reason="empty_patch",
        official=official,
        runtime_seconds=time.perf_counter() - started,
        extra={"baseline_note": "No-change baseline; empty patch cannot pass strict success."},
    )


def run_dependency_only_script(
    *,
    instance: MigrationBenchInstance,
    workspace_root: Path,
    output_dir: Path,
    evaluator: MigrationBenchEvaluator,
    framework: str = "dependency_only_script",
    provider: str = "",
    model: str = "",
    seed: int = 42,
    force: bool = False,
) -> dict[str, Any]:
    """Deterministic Maven Java-version edit baseline."""
    started = time.perf_counter()
    workspace = MigrationBenchWorkspace(instance=instance, root_dir=workspace_root)
    workspace.prepare(force=force)
    edits = deterministic_java17_pom_edits(workspace)
    application = workspace.apply_typed_edits(edits)
    patch_path = output_dir / "patch.diff"
    stats = workspace.export_patch(patch_path)
    patch_applies, patch_reason = workspace.verify_patch_applies(
        patch_path=patch_path,
        verification_root=workspace_root / "verification",
        force=True,
    )
    official = evaluator.evaluate_patch(
        instance=instance,
        patch_path=patch_path,
        output_dir=output_dir / "official",
        patch_stats=stats,
        patch_applies=patch_applies,
        patch_apply_reason=patch_reason,
    )
    return build_strict_contract(
        instance=instance,
        framework=framework,
        provider=provider,
        model=model,
        seed=seed,
        patch_path=patch_path,
        patch_stats=stats,
        patch_applies=patch_applies,
        patch_apply_reason=patch_reason,
        official=official,
        runtime_seconds=time.perf_counter() - started,
        extra={
            "typed_edits": edits.model_dump(),
            "edit_application": application.model_dump(),
        },
    )


def run_llm_patch_baseline(
    *,
    instance: MigrationBenchInstance,
    workspace_root: Path,
    output_dir: Path,
    evaluator: MigrationBenchEvaluator,
    llm_client: LLMClient | None,
    framework: str,
    strategy: str,
    seed: int = 42,
    force: bool = False,
    repair_cycles: int = 0,
) -> dict[str, Any]:
    """Generic LLM baseline using typed edits and optional build-feedback cycles."""
    started = time.perf_counter()
    workspace = MigrationBenchWorkspace(instance=instance, root_dir=workspace_root)
    workspace.prepare(force=force)
    provider = getattr(llm_client, "provider", "") if llm_client is not None else ""
    model = getattr(llm_client, "model", "") if llm_client is not None else ""
    if llm_client is None:
        return empty_output_contract(
            instance=instance,
            framework=framework,
            provider=provider,
            model=model,
            seed=seed,
            failure_reason="llm_unavailable",
        )

    llm_calls = 0
    feedback = ""
    application_payloads: list[dict[str, Any]] = []
    edits_payloads: list[dict[str, Any]] = []
    for cycle in range(max(1, int(repair_cycles) + 1)):
        prompt = build_edit_prompt(
            workspace=workspace,
            strategy=f"{strategy}; cycle={cycle}",
            feedback=feedback,
        )
        try:
            response = llm_client.call(
                prompt=prompt,
                system=SYSTEM_MIGRATION_EDIT,
                response_schema=TypedEditSet,
            )
            llm_calls += 1
            parsed = response.parsed if response.parsed is not None else response.content
            edits = parse_typed_edit_set(parsed)
        except Exception as exc:  # noqa: BLE001
            edits = TypedEditSet(edits=[], rationale=f"llm_error:{type(exc).__name__}:{exc}")
        edits_payloads.append(edits.model_dump())
        application = workspace.apply_typed_edits(edits)
        application_payloads.append(application.model_dump())
        build = workspace.run_maven("mvn clean verify", timeout_seconds=1800)
        feedback = (build.stdout + "\n" + build.stderr)[-20000:]
        if build.ok:
            break

    patch_path = output_dir / "patch.diff"
    stats = workspace.export_patch(patch_path)
    patch_applies, patch_reason = workspace.verify_patch_applies(
        patch_path=patch_path,
        verification_root=workspace_root / "verification",
        force=True,
    )
    official = evaluator.evaluate_patch(
        instance=instance,
        patch_path=patch_path,
        output_dir=output_dir / "official",
        patch_stats=stats,
        patch_applies=patch_applies,
        patch_apply_reason=patch_reason,
    )
    return build_strict_contract(
        instance=instance,
        framework=framework,
        provider=provider,
        model=model,
        seed=seed,
        patch_path=patch_path,
        patch_stats=stats,
        patch_applies=patch_applies,
        patch_apply_reason=patch_reason,
        official=official,
        tokens_total=int(getattr(llm_client, "total_tokens_used", 0)),
        cost_total_usd=float(getattr(llm_client, "total_cost_usd", 0.0)),
        runtime_seconds=time.perf_counter() - started,
        repair_cycles=max(0, int(repair_cycles)),
        llm_calls=llm_calls,
        extra={
            "typed_edits_by_cycle": edits_payloads,
            "edit_application_by_cycle": application_payloads,
        },
    )


def run_sd_feedback_wrapper(
    *,
    instance: MigrationBenchInstance,
    workspace_root: Path,
    output_dir: Path,
    command_template: str | None,
    framework: str = "sd_feedback",
    provider: str = "",
    model: str = "",
    seed: int = 42,
) -> dict[str, Any]:
    """Run official SD-Feedback when explicitly configured; otherwise fail honestly."""
    if not command_template:
        return empty_output_contract(
            instance=instance,
            framework=framework,
            provider=provider,
            model=model,
            seed=seed,
            failure_reason="sd_feedback_not_configured",
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    command = command_template.format(
        repo_url=instance.repo_url,
        base_commit=instance.base_commit,
        workspace_root=workspace_root,
        output_dir=output_dir,
        instance_id=instance.instance_id,
    )
    started = time.perf_counter()
    completed = subprocess.run(
        ["bash", "-lc", command],
        text=True,
        capture_output=True,
        check=False,
    )
    (output_dir / "sd_feedback.log").write_text(
        (completed.stdout or "") + "\n" + (completed.stderr or ""),
        encoding="utf-8",
    )
    patch_path = output_dir / "patch.diff"
    if not patch_path.exists():
        payload = empty_output_contract(
            instance=instance,
            framework=framework,
            provider=provider,
            model=model,
            seed=seed,
            failure_reason="sd_feedback_no_patch_artifact",
        )
        payload["runtime_seconds"] = round(time.perf_counter() - started, 4)
        payload["returncode"] = completed.returncode
        return payload
    text = patch_path.read_text(encoding="utf-8")
    stats = PatchStats(
        patch_delivered=bool(text.strip()),
        patch_lines_added=sum(1 for line in text.splitlines() if line.startswith("+") and not line.startswith("+++")),
        patch_lines_deleted=sum(1 for line in text.splitlines() if line.startswith("-") and not line.startswith("---")),
        files_modified_count=sum(1 for line in text.splitlines() if line.startswith("diff --git ")),
    )
    workspace = MigrationBenchWorkspace(instance=instance, root_dir=workspace_root)
    patch_applies, patch_reason = workspace.verify_patch_applies(
        patch_path=patch_path,
        verification_root=workspace_root / "verification",
        force=True,
    )
    evaluator = MigrationBenchEvaluator()
    official = evaluator.evaluate_patch(
        instance=instance,
        patch_path=patch_path,
        output_dir=output_dir / "official",
        patch_stats=stats,
        patch_applies=patch_applies,
        patch_apply_reason=patch_reason,
    )
    return build_strict_contract(
        instance=instance,
        framework=framework,
        provider=provider,
        model=model,
        seed=seed,
        patch_path=patch_path,
        patch_stats=stats,
        patch_applies=patch_applies,
        patch_apply_reason=patch_reason,
        official=official,
        runtime_seconds=time.perf_counter() - started,
        extra={"sd_feedback_command": command, "returncode": completed.returncode},
    )


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
