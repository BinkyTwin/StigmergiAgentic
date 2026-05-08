"""Run V12.4 SD-Feedback exact/stigmergic MigrationBench campaign.

V12.4 compares:

- S1_sd_feedback_exact: official JavaMigration SD-Feedback protocol.
- S2_sd_feedback_readonly_tools: same SD loop plus shared read-only perception.
- V12_stigmergic_sd_feedback: same tools/budget plus compact stigmergic context.

The LLM always proposes patches through the official SD-Feedback text format;
the medium never creates or applies a patch.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from adapters_v10.migrationbench.adapter import MigrationBenchAdapterV10
from core_v10.contracts import (
    ApplyResult,
    ArtifactResult,
    Candidate,
    CandidateKind,
    FeedbackDigest,
    RunInstance,
    ValidationResult,
    ValidationStatus,
    WorkspaceHandle,
    to_jsonable,
)
from core_v10.event_log import JsonlEventLog
from core_v10.hypothesis_graph import HypothesisGraph
from core_v10.verifier import FinalizationReport, VerifierReport
from core_v12.agent_loop import AgentStep, ToolChoiceError
from core_v12.medium.local_view import AgentLocalView, V12StigmergicMedium
from core_v12.metrics import tool_recommendation_context_from_annotations
from core_v12.sd_feedback import (
    V12_4_EXPERIMENTAL_ARMS,
    funnel_point_from_validation,
    stigmergic_feedback_block_from_view,
)
from core_v12.sd_feedback_exact import (
    OFFICIAL_BUILD_ERRORS_DO_NOT_CHANGE_AS_FEEDBACK,
    OFFICIAL_SD_FEEDBACK_SOURCE_URL,
    OFFICIAL_TARGET_JAVA,
    apply_official_jdk17_seed,
    apply_official_sd_groups,
    build_data_from_validation,
    build_sd_feedback_extra_context,
    parse_official_sd_response,
    prepare_official_sd_prompt,
    signature_from_validation,
)
from core_v12.tools.executor import ToolExecutor, build_sd_feedback_readonly_tool_registry
from core_v12.tools.registry import ToolExecutionContext
from core_v12.tools.schema import ToolCall, ToolResult
from scripts.bench.artifacts import (
    Manifest,
    RunRow,
    load_subset,
    write_manifest,
    write_runs_jsonl,
)
from scripts.bench.harness import HarnessRegistry, default_registry
from scripts.bench.providers_v12_llm import V12LLMConfig, V12NativeToolClient
from scripts.bench.providers_v12_sd_feedback import (
    SDFeedbackLLMConfig,
    SDFeedbackTextClient,
)
from scripts.bench.telemetry import build_summary, write_summary
from scripts.v12.run_v12_agentic_comparison import (
    _artifact_paths,
    _finalize_agent_candidate,
    _persist_graph,
    _score_from_validation,
)


V12_4_STRATEGY_NAME = "v12_4_sd_feedback"
V12_4_DEFAULT_SUBSET = Path("fixtures/migrationbench/subsets/targeted_v12_agentic_5.jsonl")


@dataclass(frozen=True)
class V12_4Options:
    adapter_name: str
    subset_path: Path
    out_dir: Path
    seed: int = 42
    limit: int | None = None
    max_iterations: int = 6
    inspection_steps: int = 1
    extras: dict[str, Any] | None = None
    clean: bool = False


@dataclass
class _BestObserved:
    report: VerifierReport | None = None
    score: int = 0
    stage: str = "none"

    def update(self, report: VerifierReport) -> None:
        point = funnel_point_from_validation(report.validation)
        if self.report is None or (point.score, report.hypothesis_id) > (
            self.score,
            self.report.hypothesis_id,
        ):
            self.report = report
            self.score = point.score
            self.stage = point.stage

    def snapshot(self) -> dict[str, Any]:
        if self.report is None:
            return {
                "best_candidate_id": None,
                "best_hypothesis_id": None,
                "best_funnel_score": 0,
                "best_stage": "none",
                "best_signals": {},
            }
        return {
            "best_candidate_id": self.report.candidate_id,
            "best_hypothesis_id": self.report.hypothesis_id,
            "best_funnel_score": int(self.score),
            "best_stage": self.stage,
            "best_validation_status": self.report.validation.status.value,
            "best_signals": dict(self.report.validation.signals or {}),
            "best_feedback": to_jsonable(self.report.feedback),
        }


def run_v12_4_sd_feedback_campaign(
    *,
    adapter_name: str,
    subset_path: Path,
    out_dir: Path,
    seed: int = 42,
    limit: int | None = None,
    max_iterations: int = 6,
    inspection_steps: int = 1,
    extras: dict[str, Any] | None = None,
    registry: HarnessRegistry | None = None,
    clean: bool = False,
) -> dict[str, Any]:
    """Run S1/S2/V12 V12.4 arms and write comparison artifacts."""

    options = V12_4Options(
        adapter_name=adapter_name,
        subset_path=Path(subset_path),
        out_dir=Path(out_dir),
        seed=int(seed),
        limit=limit,
        max_iterations=int(max_iterations),
        inspection_steps=int(inspection_steps),
        extras=dict(extras or {}),
        clean=bool(clean),
    )
    used_registry = registry or default_registry()
    if clean and options.out_dir.exists():
        shutil.rmtree(options.out_dir)
    options.out_dir.mkdir(parents=True, exist_ok=True)
    arms_payload: list[dict[str, Any]] = []

    for arm in V12_4_EXPERIMENTAL_ARMS:
        arm_dir = options.out_dir / arm.arm_id
        if clean and arm_dir.exists():
            shutil.rmtree(arm_dir)
        summary = _run_arm(
            options,
            arm_id=arm.arm_id,
            description=arm.description,
            uses_readonly_tools=arm.uses_readonly_tools,
            uses_medium=arm.uses_medium,
            arm_dir=arm_dir,
            registry=used_registry,
        )
        arms_payload.append(_arm_payload(arm_id=arm.arm_id, description=arm.description, summary=summary, arm_dir=arm_dir))

    comparison = {
        "schema_version": "v12_4.sd_feedback_comparison.v1",
        "subset_path": str(options.subset_path),
        "adapter_name": options.adapter_name,
        "out_dir": str(options.out_dir),
        "seed": int(options.seed),
        "limit": int(options.limit) if options.limit is not None else None,
        "max_iterations": int(options.max_iterations),
        "inspection_steps": int(options.inspection_steps),
        "official_sd_feedback_source": OFFICIAL_SD_FEEDBACK_SOURCE_URL,
        "scientific_invariants": {
            "medium_guides_never_patches": True,
            "patch_channel": "official_sd_feedback_find_replace",
            "s2_v12_same_readonly_tools": True,
            "verifier_runs_automatically_after_patch": True,
            "official_sd_feedback_target_java": OFFICIAL_TARGET_JAVA,
        },
        "arms": arms_payload,
    }
    (options.out_dir / "comparison.json").write_text(
        json.dumps(to_jsonable(comparison), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    from scripts.v12.audit_v12_campaign import audit_v12_campaign

    audit_v12_campaign(options.out_dir)
    return comparison


def _run_arm(
    options: V12_4Options,
    *,
    arm_id: str,
    description: str,
    uses_readonly_tools: bool,
    uses_medium: bool,
    arm_dir: Path,
    registry: HarnessRegistry,
):
    if options.adapter_name != "migrationbench":
        raise ValueError("V12.4 SD-Feedback currently requires adapter=migrationbench")
    records = load_subset(options.subset_path)
    if options.limit is not None:
        records = records[: int(options.limit)]
    instance_ids = [str(record["instance_id"]) for record in records]
    campaign_id = uuid.uuid4().hex
    arm_dir.mkdir(parents=True, exist_ok=True)
    extras = _arm_extras(options, arm_id=arm_id, arm_dir=arm_dir)
    readonly_registry = build_sd_feedback_readonly_tool_registry()
    if uses_readonly_tools:
        extras["sd_feedback_readonly_tool_registry"] = list(readonly_registry.names())
    write_manifest(
        arm_dir,
        Manifest(
            campaign_id=campaign_id,
            adapter_name=options.adapter_name,
            strategy_name=V12_4_STRATEGY_NAME,
            subset_path=str(options.subset_path),
            instance_ids=instance_ids,
            out_dir=str(arm_dir),
            seed=options.seed,
            extras={
                **extras,
                "arm_id": arm_id,
                "description": description,
                "uses_readonly_tools": bool(uses_readonly_tools),
                "uses_medium": bool(uses_medium),
                "official_sd_feedback_source": OFFICIAL_SD_FEEDBACK_SOURCE_URL,
            },
        ),
    )

    rows: list[RunRow] = []
    events_by_instance: dict[str, list[Any]] = {}
    for record in records:
        instance = registry.run_instance_factories[options.adapter_name](record, extras)
        adapter = registry.adapter_factories[options.adapter_name](extras)
        if not isinstance(adapter, MigrationBenchAdapterV10):
            raise TypeError("V12.4 runner requires MigrationBenchAdapterV10")
        event_log = JsonlEventLog(
            arm_dir / "events" / instance.instance_id / "eventlog.jsonl"
        )
        graph = HypothesisGraph()
        run_id = f"{campaign_id}:{instance.instance_id}"
        outcome = _run_instance(
            adapter=adapter,
            instance=instance,
            event_log=event_log,
            graph=graph,
            run_id=run_id,
            arm_id=arm_id,
            uses_readonly_tools=uses_readonly_tools,
            uses_medium=uses_medium,
            max_iterations=options.max_iterations,
            inspection_steps=options.inspection_steps,
            readonly_registry=readonly_registry,
            extras=extras,
        )
        _persist_graph(arm_dir, instance.instance_id, graph)
        rows.append(
            RunRow(
                instance_id=instance.instance_id,
                strategy_name=V12_4_STRATEGY_NAME,
                stop_reason=str(outcome["stop_reason"]),
                strict_success=bool(outcome["strict_success"]),
                selected_hypothesis_id=outcome.get("selected_hypothesis_id"),
                candidate_count=int(outcome["candidate_count"]),
                signals=dict(outcome.get("signals") or {}),
                artifact_paths=dict(outcome.get("artifact_paths") or {}),
            )
        )
        events_by_instance[instance.instance_id] = event_log.for_run(run_id)
    write_runs_jsonl(arm_dir, rows)
    summary = build_summary(
        campaign_id=campaign_id,
        adapter_name=options.adapter_name,
        strategy_name=V12_4_STRATEGY_NAME,
        instance_ids=instance_ids,
        events_by_instance=events_by_instance,
    )
    write_summary(arm_dir, summary)
    return summary


def _run_instance(
    *,
    adapter: MigrationBenchAdapterV10,
    instance: RunInstance,
    event_log: JsonlEventLog,
    graph: HypothesisGraph,
    run_id: str,
    arm_id: str,
    uses_readonly_tools: bool,
    uses_medium: bool,
    max_iterations: int,
    inspection_steps: int,
    readonly_registry: Any,
    extras: dict[str, Any],
) -> dict[str, Any]:
    event_log.append(
        run_id=run_id,
        instance_id=instance.instance_id,
        event_type="run.started",
        actor="v12_4_runner",
        payload={
            "strategy": V12_4_STRATEGY_NAME,
            "arm_id": arm_id,
            "uses_readonly_tools": bool(uses_readonly_tools),
            "uses_medium": bool(uses_medium),
            "max_iterations": int(max_iterations),
        },
    )
    base_workspace = adapter.setup(instance)
    observation = adapter.observe(base_workspace)
    migration_context = (
        observation.data.get("migration_context")
        or base_workspace.metadata.get("migration_context")
        or {}
    )
    event_log.append(
        run_id=run_id,
        instance_id=instance.instance_id,
        event_type="observation.created",
        actor="adapter",
        payload={"observation": observation},
    )
    text_config = SDFeedbackLLMConfig.from_extras(extras)
    if text_config is None:
        raise RuntimeError("V12.4 SD-Feedback requires a configured LLM provider")
    text_client = SDFeedbackTextClient(text_config)
    tool_client = _tool_client_for(extras) if uses_readonly_tools else None
    tool_executor = ToolExecutor(readonly_registry)
    medium = V12StigmergicMedium() if uses_medium else None
    history: list[AgentStep] = []
    reports: list[VerifierReport] = []
    best = _BestObserved()
    finalization: FinalizationReport | None = None

    seed_branch_id = f"{_safe_id(instance.instance_id)}-{_safe_id(arm_id)}-sd-seed"
    seed_workspace = _open_branch(
        adapter=adapter,
        branch_id=seed_branch_id,
        parent_branch_id=None,
        base_workspace=base_workspace,
    )
    seed_modified = apply_official_jdk17_seed(seed_workspace)
    seed_candidate = _branch_candidate(
        instance=instance,
        candidate_id=f"{_safe_id(instance.instance_id)}-{_safe_id(arm_id)}-seed",
        branch_id=seed_branch_id,
        parent_branch_id=None,
        parent_hypothesis_id=None,
        origin="official_sdfeedback_seed_jdk17",
        metadata={"modified_poms": list(seed_modified)},
    )
    seed_report = _validate_branch_candidate(
        adapter=adapter,
        event_log=event_log,
        graph=graph,
        run_id=run_id,
        instance_id=instance.instance_id,
        candidate=seed_candidate,
        workspace=seed_workspace,
        applied_summary="official SD-Feedback mandatory JDK17 seed applied",
    )
    reports.append(seed_report)
    best.update(seed_report)
    current_report = seed_report
    current_workspace = seed_workspace
    current_branch_id = seed_branch_id
    current_hypothesis_id = seed_report.hypothesis_id
    current_signature = signature_from_validation(
        seed_report.validation,
        repo_dir=_repo_dir(seed_workspace),
    )
    if medium is not None:
        medium.update_from_feedback(
            seed_report.feedback,
            event_log=event_log,
            run_id=run_id,
            instance_id=instance.instance_id,
            actor="v12_4_medium",
        )
    if seed_report.passed:
        finalization = _finalize_agent_candidate(
            adapter=adapter,
            event_log=event_log,
            graph=graph,
            run_id=run_id,
            instance_id=instance.instance_id,
            hypothesis_id=seed_report.hypothesis_id,
            workspace=seed_workspace,
        )

    feedback_messages: list[str] = []
    last_prompt_messages: list[dict[str, str]] = []
    last_llm_response = ""

    for iteration in range(int(max_iterations)):
        if finalization is not None:
            break
        read_only_context = _run_readonly_inspections(
            adapter=adapter,
            instance=instance,
            event_log=event_log,
            run_id=run_id,
            arm_id=arm_id,
            uses_medium=uses_medium,
            medium=medium,
            tool_client=tool_client,
            tool_executor=tool_executor,
            registry=readonly_registry,
            history=history,
            workspace=current_workspace,
            validation=current_report.validation,
            feedback=current_report.feedback,
            migration_context=migration_context,
            current_best=best.snapshot(),
            inspection_steps=inspection_steps if uses_readonly_tools else 0,
        )
        extra_context = build_sd_feedback_extra_context(
            read_only_context=read_only_context,
            stigmergic_context=(
                stigmergic_feedback_block_from_view(
                    medium.local_view(
                        objective=instance.objective,
                        migration_context=migration_context,
                        current_best=best.snapshot(),
                        tool_registry=readonly_registry.names(),
                    )
                )
                if medium is not None
                else None
            ),
        )
        build_data = build_data_from_validation(
            current_report.validation,
            repo_dir=_repo_dir(current_workspace),
        )
        prompt_request = prepare_official_sd_prompt(
            repo_dir=_repo_dir(current_workspace),
            project_path=_repo_dir(current_workspace) / "pom.xml",
            build_data=build_data,
            last_prompt_messages=last_prompt_messages,
            last_llm_response=last_llm_response,
            feedback=feedback_messages,
            extra_context=extra_context,
        )
        response = text_client.complete(
            prompt=prompt_request.prompt,
            messages=prompt_request.messages,
            instance_id=instance.instance_id,
            arm_id=arm_id,
            iteration=iteration,
            prompt_kind=prompt_request.prompt_kind,
            metadata={
                "current_candidate_id": current_report.candidate_id,
                "current_signature": current_signature.to_dict(),
                "read_only_context_count": len(read_only_context),
                "uses_medium": bool(uses_medium),
            },
        )
        last_prompt_messages = [*list(prompt_request.messages), {"role": "user", "content": prompt_request.prompt}]
        last_llm_response = response.content
        event_log.append(
            run_id=run_id,
            instance_id=instance.instance_id,
            event_type="sd_feedback.llm.response",
            actor=arm_id,
            payload={
                "iteration": int(iteration),
                "prompt_kind": prompt_request.prompt_kind,
                "ok": response.ok,
                "error": response.error,
                "finish_reason": response.finish_reason,
                "usage": response.usage or {},
            },
        )
        if not response.ok:
            feedback_messages = [response.error or "LLM API call failed"]
            continue

        parsed = parse_official_sd_response(response.content)
        event_log.append(
            run_id=run_id,
            instance_id=instance.instance_id,
            event_type="sd_feedback.response.parsed",
            actor="official_sd_feedback_parser",
            payload={
                "iteration": int(iteration),
                "ok": parsed.ok,
                "group_count": len(parsed.groups),
                "feedback": list(parsed.feedback),
            },
        )
        if parsed.feedback:
            feedback_messages = list(parsed.feedback)
            continue

        branch_id = f"{_safe_id(instance.instance_id)}-{_safe_id(arm_id)}-iter{iteration:02d}"
        branch_workspace = _open_branch(
            adapter=adapter,
            branch_id=branch_id,
            parent_branch_id=current_branch_id,
            base_workspace=base_workspace,
        )
        patch_result = apply_official_sd_groups(parsed.groups, branch_workspace)
        event_log.append(
            run_id=run_id,
            instance_id=instance.instance_id,
            event_type=(
                "sd_feedback.patch.applied"
                if patch_result.any_patched
                else "sd_feedback.patch.rejected"
            ),
            actor="official_sd_feedback_writer",
            payload={
                "iteration": int(iteration),
                "patched": patch_result.patched,
                "feedback": list(patch_result.feedback),
                "files_modified": list(patch_result.files_modified),
            },
        )
        if not patch_result.any_patched:
            feedback_messages = list(patch_result.feedback) or [
                "Unable to parse the response and patch relevant files."
            ]
            continue

        candidate_id = f"{_safe_id(instance.instance_id)}-{_safe_id(arm_id)}-iter{iteration:02d}"
        candidate = _branch_candidate(
            instance=instance,
            candidate_id=candidate_id,
            branch_id=branch_id,
            parent_branch_id=current_branch_id,
            parent_hypothesis_id=current_hypothesis_id,
            origin="official_sdfeedback_llm_patch",
            metadata={
                "iteration": int(iteration),
                "parsed_content": parsed.parsed_content,
                "files_modified": list(patch_result.files_modified),
            },
        )
        report = _validate_branch_candidate(
            adapter=adapter,
            event_log=event_log,
            graph=graph,
            run_id=run_id,
            instance_id=instance.instance_id,
            candidate=candidate,
            workspace=branch_workspace,
            applied_summary="official SD-Feedback LLM patch applied",
        )
        reports.append(report)
        best.update(report)
        new_signature = signature_from_validation(
            report.validation,
            repo_dir=_repo_dir(branch_workspace),
        )
        changed = new_signature != current_signature
        event_log.append(
            run_id=run_id,
            instance_id=instance.instance_id,
            event_type=(
                "sd_feedback.patch.accepted"
                if changed or report.passed
                else "sd_feedback.patch.reverted"
            ),
            actor="official_sd_feedback_policy",
            hypothesis_id=report.hypothesis_id,
            payload={
                "iteration": int(iteration),
                "reason": "build_errors_changed"
                if changed or report.passed
                else "build_errors_same_as_before",
                "previous_signature": current_signature.to_dict(),
                "observed_signature": new_signature.to_dict(),
            },
        )
        if medium is not None:
            medium.update_from_feedback(
                report.feedback,
                event_log=event_log,
                run_id=run_id,
                instance_id=instance.instance_id,
                actor="v12_4_medium",
            )
            medium.record_candidate(
                {
                    "candidate_id": candidate_id,
                    "tool_name": "official_sd_feedback_patch_channel",
                    "status": "accepted" if changed or report.passed else "reverted",
                    "summary": report.validation.summary,
                }
            )
        if report.passed:
            finalization = _finalize_agent_candidate(
                adapter=adapter,
                event_log=event_log,
                graph=graph,
                run_id=run_id,
                instance_id=instance.instance_id,
                hypothesis_id=report.hypothesis_id,
                workspace=branch_workspace,
            )
            current_report = report
            current_workspace = branch_workspace
            current_branch_id = branch_id
            current_hypothesis_id = report.hypothesis_id
            break
        if changed:
            feedback_messages = []
            last_prompt_messages = []
            current_report = report
            current_workspace = branch_workspace
            current_branch_id = branch_id
            current_hypothesis_id = report.hypothesis_id
            current_signature = new_signature
        else:
            feedback_messages = [
                OFFICIAL_BUILD_ERRORS_DO_NOT_CHANGE_AS_FEEDBACK,
                *list(report.feedback.evidence or [])[:1],
            ]

    selected_hypothesis_id = (
        finalization.hypothesis_id
        if finalization is not None
        else best.snapshot().get("best_hypothesis_id")
    )
    if selected_hypothesis_id:
        event_log.append(
            run_id=run_id,
            instance_id=instance.instance_id,
            event_type="selection.completed",
            actor="v12_4_runner",
            hypothesis_id=str(selected_hypothesis_id),
            payload={
                "rationale": {
                    "selected_hypothesis_id": selected_hypothesis_id,
                    "reason": "strict_success"
                    if finalization and finalization.strict_success
                    else "best_observed_partial",
                    "selected_score": best.snapshot().get("best_funnel_score"),
                    "competitors": [_report_competitor(report) for report in reports],
                }
            },
        )
    event_log.append(
        run_id=run_id,
        instance_id=instance.instance_id,
        event_type="run.completed",
        actor="v12_4_runner",
        payload={
            "strategy": V12_4_STRATEGY_NAME,
            "arm_id": arm_id,
            "stop_reason": _stop_reason(finalization=finalization, reports=reports),
            "candidate_count": len(reports),
            "selected_hypothesis_id": selected_hypothesis_id,
            "best_observed": best.snapshot(),
            "medium_created_patch_count": medium.created_patch_count if medium else 0,
            "suggest_tool_applied_patch_count": 0,
            "sd_feedback_exact_protocol": True,
            "official_sd_feedback_source": OFFICIAL_SD_FEEDBACK_SOURCE_URL,
        },
    )
    score = finalization.score if finalization is not None else None
    artifact = finalization.artifact if finalization is not None else None
    return {
        "stop_reason": _stop_reason(finalization=finalization, reports=reports),
        "strict_success": bool(finalization and finalization.strict_success),
        "selected_hypothesis_id": selected_hypothesis_id,
        "candidate_count": len(reports),
        "signals": dict(score.metrics) if score is not None else dict(best.snapshot().get("best_signals") or {}),
        "artifact_paths": _artifact_paths(artifact),
    }


def _run_readonly_inspections(
    *,
    adapter: MigrationBenchAdapterV10,
    instance: RunInstance,
    event_log: JsonlEventLog,
    run_id: str,
    arm_id: str,
    uses_medium: bool,
    medium: V12StigmergicMedium | None,
    tool_client: V12NativeToolClient | None,
    tool_executor: ToolExecutor,
    registry: Any,
    history: list[AgentStep],
    workspace: WorkspaceHandle,
    validation: ValidationResult,
    feedback: FeedbackDigest,
    migration_context: Any,
    current_best: dict[str, Any],
    inspection_steps: int,
) -> list[dict[str, Any]]:
    if tool_client is None or inspection_steps <= 0:
        return []
    rows: list[dict[str, Any]] = []
    for _ in range(int(inspection_steps)):
        if medium is not None:
            view = medium.local_view(
                objective=instance.objective,
                migration_context=migration_context,
                current_best=current_best,
                tool_registry=registry.names(),
                event_log=event_log,
                run_id=run_id,
                instance_id=instance.instance_id,
                actor=arm_id,
            )
        else:
            view = AgentLocalView(
                objective=instance.objective,
                migration_context=dict(migration_context or {}),
                current_best=current_best,
                recent_failures=(to_jsonable(feedback),),
                tool_registry=registry.names(),
            )
        try:
            call = tool_client.choose_tool(
                view,
                registry.specs(),
                tuple(history),
                instance=instance,
                observation=None,
                prompt_kind="v12_4_sd_feedback_readonly_inspection",
            )
        except ToolChoiceError as exc:
            event_log.append(
                run_id=run_id,
                instance_id=instance.instance_id,
                event_type="agent.tool_call.parse_failed",
                actor=arm_id,
                payload={"error": exc.to_dict()},
            )
            break
        event_log.append(
            run_id=run_id,
            instance_id=instance.instance_id,
            event_type="agent.tool_call.requested",
            actor=arm_id,
            payload={
                "tool_call": call.model_dump(mode="json"),
                "available_tools": registry.names(),
                "visible_tool_registry": list(view.tool_registry),
                "tool_annotation": view.tool_annotations.get(call.tool_name),
                "tool_recommendation_context": tool_recommendation_context_from_annotations(
                    annotations={
                        str(name): dict(annotation or {})
                        for name, annotation in view.tool_annotations.items()
                    },
                    selected_tool=call.tool_name,
                    forbidden_tools=view.forbidden_tools.keys(),
                ),
            },
        )
        result = tool_executor.execute(
            call,
            ToolExecutionContext(
                workspace=workspace,
                migration_context=migration_context,
                objective=instance.objective,
                timeout_seconds=float(_extras_timeout(adapter)),
                metadata=_artifact_log_metadata(validation),
            ),
        )
        event_log.append(
            run_id=run_id,
            instance_id=instance.instance_id,
            event_type="tool.executed",
            actor=arm_id,
            payload={
                "tool_call": call.model_dump(mode="json"),
                "result": result.model_dump(mode="json"),
            },
        )
        if medium is not None:
            medium.record_tool_outcome(
                {
                    "tool_name": call.tool_name,
                    "status": result.status,
                    "summary": result.summary,
                    "candidate_created": False,
                    "workspace_mutated": False,
                    "step_index": len(history),
                }
            )
        step = AgentStep(step_index=len(history), call=call, result=result)
        history.append(step)
        rows.append(_tool_context_row(call, result))
    return rows


def _tool_context_row(call: ToolCall, result: ToolResult) -> dict[str, Any]:
    output = result.output or {}
    if "content" in output:
        output = {**output, "content": str(output.get("content") or "")[:8000]}
    if "log_excerpt" in output:
        output = {**output, "log_excerpt": str(output.get("log_excerpt") or "")[:8000]}
    return {
        "tool_name": call.tool_name,
        "rationale": call.rationale,
        "status": result.status,
        "summary": result.summary,
        "output": to_jsonable(output),
        "errors": list(result.errors or []),
    }


def _validate_branch_candidate(
    *,
    adapter: MigrationBenchAdapterV10,
    event_log: JsonlEventLog,
    graph: HypothesisGraph,
    run_id: str,
    instance_id: str,
    candidate: Candidate,
    workspace: WorkspaceHandle,
    applied_summary: str,
) -> VerifierReport:
    node = graph.add_candidate(
        candidate,
        hypothesis_id=candidate.candidate_id,
        parent_id=candidate.parent_id,
    )
    created = event_log.append(
        run_id=run_id,
        instance_id=instance_id,
        event_type="candidate.created",
        actor="v12_4_agent",
        hypothesis_id=node.hypothesis_id,
        payload={"candidate": candidate},
    )
    apply_result = ApplyResult(
        candidate_id=candidate.candidate_id,
        applied=True,
        workspace=workspace,
        summary=applied_summary,
        metadata={
            "applied_by": "official_sd_feedback_patch_channel",
            "branch_id": workspace.metadata.get("branch_id"),
            "parent_branch_id": workspace.metadata.get("parent_branch_id"),
        },
    )
    graph.attach_workspace(node.hypothesis_id, workspace)
    graph.mark_applied(node.hypothesis_id)
    applied = event_log.append(
        run_id=run_id,
        instance_id=instance_id,
        event_type="candidate.applied",
        actor="v12_4_runner",
        hypothesis_id=node.hypothesis_id,
        payload={"apply_result": apply_result},
    )
    validation = adapter.validate(candidate, workspace)
    graph.attach_validation(
        node.hypothesis_id,
        validation,
        score=_score_from_validation(validation),
    )
    validated = event_log.append(
        run_id=run_id,
        instance_id=instance_id,
        event_type="validation.completed",
        actor="verifier",
        hypothesis_id=node.hypothesis_id,
        payload={"validation": validation},
    )
    feedback = adapter.diagnose(validation, workspace)
    graph.attach_feedback(node.hypothesis_id, feedback)
    feedback_event = event_log.append(
        run_id=run_id,
        instance_id=instance_id,
        event_type="feedback.created",
        actor="diagnoser",
        hypothesis_id=node.hypothesis_id,
        payload={"feedback": feedback},
    )
    return VerifierReport(
        hypothesis_id=node.hypothesis_id,
        candidate_id=candidate.candidate_id,
        apply_result=apply_result,
        validation=validation,
        feedback=feedback,
        event_ids=(created.event_id, applied.event_id, validated.event_id, feedback_event.event_id),
    )


def _open_branch(
    *,
    adapter: MigrationBenchAdapterV10,
    branch_id: str,
    parent_branch_id: str | None,
    base_workspace: WorkspaceHandle,
) -> WorkspaceHandle:
    base = adapter._require_base_workspace()  # noqa: SLF001
    if parent_branch_id:
        branch = base.fork_branch_workspace(
            source_branch_id=parent_branch_id,
            branch_id=branch_id,
            force=True,
        )
    else:
        branch = base.branch_workspace(branch_id, force=True)
    return branch.as_handle(
        branch_id=branch_id,
        parent_branch_id=parent_branch_id,
        role="v12_4_sd_feedback_branch",
        artifacts_dir=base_workspace.metadata.get("artifacts_dir"),
        official_eval_command=base_workspace.metadata.get("official_eval_command"),
    )


def _branch_candidate(
    *,
    instance: RunInstance,
    candidate_id: str,
    branch_id: str,
    parent_branch_id: str | None,
    parent_hypothesis_id: str | None,
    origin: str,
    metadata: dict[str, Any],
) -> Candidate:
    return Candidate(
        candidate_id=candidate_id,
        kind=CandidateKind.PATCH,
        payload={
            "branch_id": branch_id,
            "parent_branch_id": parent_branch_id,
            "patch_source": "official_sd_feedback_branch",
        },
        origin=origin,
        parent_id=parent_hypothesis_id,
        metadata={
            "instance_id": instance.instance_id,
            "branch_id": branch_id,
            "parent_branch_id": parent_branch_id,
            **dict(metadata or {}),
        },
    )


def _tool_client_for(extras: dict[str, Any]) -> V12NativeToolClient | None:
    config = V12LLMConfig.from_extras({**extras, "use_v12_llm_provider": True})
    if config is None:
        return None
    return V12NativeToolClient(config)


def _repo_dir(workspace: WorkspaceHandle) -> Path:
    return Path(str(workspace.metadata["repo_dir"])).expanduser().resolve()


def _artifact_log_metadata(validation: ValidationResult) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    official = validation.metadata.get("official")
    if isinstance(official, dict) and official.get("log_path"):
        metadata["artifact_logs"] = {"official_eval_log": official["log_path"]}
        metadata["official_eval_log"] = official["log_path"]
    return metadata


def _extras_timeout(adapter: MigrationBenchAdapterV10) -> float:
    return float(getattr(adapter, "timeout_seconds", 600.0))


def _report_competitor(report: VerifierReport) -> dict[str, Any]:
    point = funnel_point_from_validation(report.validation)
    return {
        "hypothesis_id": report.hypothesis_id,
        "candidate_id": report.candidate_id,
        "funnel_score": int(point.score),
        "funnel_stage": point.stage,
        "validation_status": report.validation.status.value,
    }


def _stop_reason(
    *,
    finalization: FinalizationReport | None,
    reports: Sequence[VerifierReport],
) -> str:
    if finalization is not None and finalization.strict_success:
        return "strict_success"
    if finalization is not None:
        return "validated_but_not_strict"
    if reports:
        return "iterations_exhausted"
    return "no_candidate_created"


def _arm_payload(*, arm_id: str, description: str, summary: Any, arm_dir: Path) -> dict[str, Any]:
    payload = summary.to_dict()
    events = _read_arm_events(arm_dir)
    payload.update(
        {
            "arm_id": arm_id,
            "description": description,
            "medium_created_patch_count": _run_completed_sum(events, "medium_created_patch_count"),
            "suggest_tool_applied_patch_count": _run_completed_sum(events, "suggest_tool_applied_patch_count"),
            "tool_call_total": sum(1 for event in events if event.event_type == "agent.tool_call.requested"),
            "sd_feedback_patch_accepted": sum(1 for event in events if event.event_type == "sd_feedback.patch.accepted"),
            "sd_feedback_patch_reverted": sum(1 for event in events if event.event_type == "sd_feedback.patch.reverted"),
            "sd_feedback_patch_rejected": sum(1 for event in events if event.event_type == "sd_feedback.patch.rejected"),
            "medium_pheromone_reads": sum(1 for event in events if event.event_type == "pheromone.read"),
        }
    )
    return payload


def _read_arm_events(arm_dir: Path) -> list[Any]:
    manifest_path = arm_dir / "manifest.json"
    if not manifest_path.exists():
        return []
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    events: list[Any] = []
    for instance_id in manifest.get("instance_ids") or []:
        path = arm_dir / "events" / str(instance_id) / "eventlog.jsonl"
        if path.exists():
            events.extend(JsonlEventLog(path).read_all())
    return events


def _run_completed_sum(events: Sequence[Any], key: str) -> int:
    return sum(
        int(event.payload.get(key) or 0)
        for event in events
        if event.event_type == "run.completed"
    )


def _arm_extras(options: V12_4Options, *, arm_id: str, arm_dir: Path) -> dict[str, Any]:
    extras = dict(options.extras or {})
    extras["out_dir"] = str(arm_dir)
    extras.setdefault("llm_trace_enabled", True)
    extras.setdefault("use_llm_providers", True)
    for key in ("workspace_root_root", "artifacts_root"):
        if extras.get(key):
            extras[key] = str(Path(str(extras[key])) / arm_id)
    return extras


def _safe_id(value: str) -> str:
    import re

    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value))[:120]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="scripts.v12.run_v12_4_sd_feedback_campaign",
        description=__doc__,
    )
    parser.add_argument("--adapter", default="migrationbench")
    parser.add_argument("--subset", type=Path, default=V12_4_DEFAULT_SUBSET)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--max-iterations", type=int, default=6)
    parser.add_argument("--inspection-steps", type=int, default=1)
    parser.add_argument("--extras", default="{}")
    parser.add_argument("--clean", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    comparison = run_v12_4_sd_feedback_campaign(
        adapter_name=args.adapter,
        subset_path=args.subset,
        out_dir=args.out_dir,
        seed=int(args.seed),
        limit=args.limit,
        max_iterations=int(args.max_iterations),
        inspection_steps=int(args.inspection_steps),
        extras=json.loads(args.extras or "{}"),
        clean=bool(args.clean),
    )
    print(json.dumps(comparison, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())


__all__ = [
    "V12_4_DEFAULT_SUBSET",
    "V12_4_STRATEGY_NAME",
    "V12_4Options",
    "build_parser",
    "main",
    "run_v12_4_sd_feedback_campaign",
]
