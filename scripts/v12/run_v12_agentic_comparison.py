"""Run V12.3 agentic MigrationBench comparison arms.

V12.3 compares:

- S1_sd_feedback_like: free LLM patch baseline plus verifier feedback.
- S2_tool_feedback_agent: autonomous LLM over the V12 tool registry, no medium.
- V12_stigmergic_tool_agent: same tools and budgets as S2 plus local guidance.

The scientific invariant is enforced in code: S2 and V12 expose the same tool
registry and the medium never creates patches.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence

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
from core_v10.hypothesis_graph import HypothesisGraph, HypothesisScore
from core_v10.verifier import FinalizationReport, VerifierReport
from core_v12.agent_loop import (
    AgentLoop,
    V12_EXPERIMENTAL_ARMS,
    assert_same_tools_available_s2_and_v12,
)
from core_v12.medium.local_view import V12StigmergicMedium
from core_v12.metrics import summarize_tool_recommendation_metrics
from core_v12.tools.executor import build_default_tool_registry
from core_v12.tools.registry import ToolExecutionContext, ToolRegistry
from core_v12.tools.schema import ToolCall
from scripts.bench.artifacts import (
    Manifest,
    RunRow,
    load_subset,
    write_manifest,
    write_runs_jsonl,
)
from scripts.bench.harness import (
    BenchHarness,
    HarnessOptions,
    HarnessRegistry,
    default_registry,
)
from scripts.bench.telemetry import build_summary, write_summary
from scripts.bench.providers_v12_llm import V12LLMConfig, V12NativeToolClient


V12_TOOL_STRATEGY_NAME = "v12_agentic_tool_loop"
V12_DEFAULT_SUBSET = Path("fixtures/migrationbench/subsets/targeted_v12_agentic_5.jsonl")


@dataclass(frozen=True)
class V12AgenticOptions:
    """Options for one V12.3 comparison campaign."""

    adapter_name: str
    subset_path: Path
    out_dir: Path
    seed: int = 42
    limit: int | None = None
    max_steps: int = 6
    extras: dict[str, Any] | None = None
    clean: bool = False


@dataclass
class _BestObserved:
    """Best funnel point observed by one agentic arm on one instance."""

    report: VerifierReport | None = None
    score: int = 0
    stage: str = "none"

    def update(self, report: VerifierReport) -> None:
        score, stage = _funnel_score(report.validation)
        if self.report is None or (score, report.hypothesis_id) > (
            self.score,
            self.report.hypothesis_id,
        ):
            self.report = report
            self.score = score
            self.stage = stage

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


ToolChooserFactory = Callable[
    [
        MigrationBenchAdapterV10,
        dict[str, Any],
        RunInstance,
        Any,
    ],
    Callable[[Any, tuple[Any, ...], tuple[Any, ...]], ToolCall],
]


def run_v12_agentic_comparison(
    *,
    adapter_name: str,
    subset_path: Path,
    out_dir: Path,
    seed: int = 42,
    limit: int | None = None,
    max_steps: int = 6,
    extras: dict[str, Any] | None = None,
    registry: HarnessRegistry | None = None,
    clean: bool = False,
) -> dict[str, Any]:
    """Run S1/S2/V12 on the same subset and write comparison artifacts."""

    options = V12AgenticOptions(
        adapter_name=adapter_name,
        subset_path=Path(subset_path),
        out_dir=Path(out_dir),
        seed=int(seed),
        limit=limit,
        max_steps=int(max_steps),
        extras=dict(extras or {}),
        clean=bool(clean),
    )
    used_registry = registry or default_registry()
    options.out_dir.mkdir(parents=True, exist_ok=True)
    assert_same_tools_available_s2_and_v12()
    arms_payload: list[dict[str, Any]] = []
    summaries_by_arm: dict[str, Any] = {}

    for arm in V12_EXPERIMENTAL_ARMS:
        arm_dir = options.out_dir / arm.arm_id
        if clean and arm_dir.exists():
            shutil.rmtree(arm_dir)
        if arm.free_patch_baseline:
            summary = _run_s1_arm(options, arm_dir=arm_dir, registry=used_registry)
        else:
            summary = _run_tool_agent_arm(
                options,
                arm_id=arm.arm_id,
                uses_medium=arm.uses_medium,
                arm_dir=arm_dir,
                registry=used_registry,
            )
        summaries_by_arm[arm.arm_id] = summary
        arms_payload.append(
            _arm_payload(
                arm_id=arm.arm_id,
                description=arm.description,
                summary=summary,
                arm_dir=arm_dir,
            )
        )

    comparison = {
        "schema_version": "v12.3.agentic_comparison.v1",
        "subset_path": str(options.subset_path),
        "adapter_name": options.adapter_name,
        "out_dir": str(options.out_dir),
        "seed": int(options.seed),
        "limit": int(options.limit) if options.limit is not None else None,
        "max_steps": int(options.max_steps),
        "scientific_invariants": {
            "medium_guides_never_patches": True,
            "s2_v12_same_tools": True,
            "suggest_tools_proposal_only": True,
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


def _run_s1_arm(
    options: V12AgenticOptions,
    *,
    arm_dir: Path,
    registry: HarnessRegistry,
):
    extras = _arm_extras(options, arm_id="S1_sd_feedback_like", arm_dir=arm_dir)
    extras.setdefault("use_llm_providers", True)
    harness_options = HarnessOptions(
        adapter_name=options.adapter_name,
        strategy_name="branching_repair",
        subset_path=options.subset_path,
        out_dir=arm_dir,
        seed=options.seed,
        limit=options.limit,
        max_candidates=1,
        max_repair_rounds=max(0, options.max_steps - 1),
        max_repairs_per_candidate=1,
        extras=extras,
    )
    return BenchHarness(harness_options, registry).run()


def _run_tool_agent_arm(
    options: V12AgenticOptions,
    *,
    arm_id: str,
    uses_medium: bool,
    arm_dir: Path,
    registry: HarnessRegistry,
):
    if options.adapter_name != "migrationbench":
        raise ValueError("V12.3 tool-agent arms currently require adapter=migrationbench")
    if options.adapter_name not in registry.adapter_factories:
        raise KeyError(f"unknown adapter: {options.adapter_name}")
    if options.adapter_name not in registry.run_instance_factories:
        raise KeyError(f"missing run instance factory: {options.adapter_name}")

    records = load_subset(options.subset_path)
    if options.limit is not None:
        records = records[: int(options.limit)]
    instance_ids = [str(record["instance_id"]) for record in records]
    campaign_id = uuid.uuid4().hex
    arm_dir.mkdir(parents=True, exist_ok=True)
    tool_registry = build_default_tool_registry()
    extras = _arm_extras(options, arm_id=arm_id, arm_dir=arm_dir)
    extras["v12_tool_registry"] = list(tool_registry.names())
    extras["v12_uses_medium"] = bool(uses_medium)
    write_manifest(
        arm_dir,
        Manifest(
            campaign_id=campaign_id,
            adapter_name=options.adapter_name,
            strategy_name=V12_TOOL_STRATEGY_NAME,
            subset_path=str(options.subset_path),
            instance_ids=instance_ids,
            out_dir=str(arm_dir),
            seed=options.seed,
            extras=extras,
        ),
    )

    rows: list[RunRow] = []
    events_by_instance = {}
    for record in records:
        instance = registry.run_instance_factories[options.adapter_name](record, extras)
        adapter = registry.adapter_factories[options.adapter_name](extras)
        if not isinstance(adapter, MigrationBenchAdapterV10):
            raise TypeError("V12.3 tool-agent runner requires MigrationBenchAdapterV10")
        run_id = f"{campaign_id}:{instance.instance_id}"
        event_log = JsonlEventLog(
            arm_dir / "events" / instance.instance_id / "eventlog.jsonl"
        )
        graph = HypothesisGraph()
        outcome = _run_tool_agent_instance(
            adapter=adapter,
            instance=instance,
            event_log=event_log,
            graph=graph,
            run_id=run_id,
            arm_id=arm_id,
            uses_medium=uses_medium,
            registry=tool_registry,
            max_steps=options.max_steps,
            extras=extras,
        )
        _persist_graph(arm_dir, instance.instance_id, graph)
        rows.append(
            RunRow(
                instance_id=instance.instance_id,
                strategy_name=V12_TOOL_STRATEGY_NAME,
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
        strategy_name=V12_TOOL_STRATEGY_NAME,
        instance_ids=instance_ids,
        events_by_instance=events_by_instance,
    )
    write_summary(arm_dir, summary)
    return summary


def _run_tool_agent_instance(
    *,
    adapter: MigrationBenchAdapterV10,
    instance: RunInstance,
    event_log: JsonlEventLog,
    graph: HypothesisGraph,
    run_id: str,
    arm_id: str,
    uses_medium: bool,
    registry: ToolRegistry,
    max_steps: int,
    extras: dict[str, Any],
) -> dict[str, Any]:
    event_log.append(
        run_id=run_id,
        instance_id=instance.instance_id,
        event_type="run.started",
        actor="v12_runner",
        payload={
            "strategy": V12_TOOL_STRATEGY_NAME,
            "arm_id": arm_id,
            "uses_medium": bool(uses_medium),
            "max_steps": int(max_steps),
            "tool_registry": list(registry.names()),
        },
    )
    base_workspace = adapter.setup(instance)
    observation = adapter.observe(base_workspace)
    event_log.append(
        run_id=run_id,
        instance_id=instance.instance_id,
        event_type="observation.created",
        actor="adapter",
        payload={"observation": observation},
    )

    migration_context = (
        observation.data.get("migration_context")
        or base_workspace.metadata.get("migration_context")
        or {}
    )
    medium = V12StigmergicMedium() if uses_medium else None
    prepared_contexts: dict[int, ToolExecutionContext] = {}
    active_workspace = base_workspace
    active_parent_hypothesis_id: str | None = None
    active_parent_branch_id: str | None = None
    best = _BestObserved()
    finalization: FinalizationReport | None = None
    reports: list[VerifierReport] = []
    chooser = _tool_chooser_for_instance(
        adapter=adapter,
        extras=extras,
        instance=instance,
        observation=observation,
    )

    def prepare_context(
        call: ToolCall,
        context: ToolExecutionContext,
        step_index: int,
    ) -> ToolExecutionContext:
        spec = registry.get(call.tool_name).spec
        if not spec.mutates_workspace:
            prepared = ToolExecutionContext(
                workspace=active_workspace,
                migration_context=context.migration_context,
                objective=context.objective,
                timeout_seconds=context.timeout_seconds,
                metadata={
                    "workspace_role": active_workspace.metadata.get("role", "base"),
                    "parent_hypothesis_id": active_parent_hypothesis_id,
                    "parent_branch_id": active_parent_branch_id,
                },
            )
            prepared_contexts[step_index] = prepared
            return prepared
        candidate_id = _candidate_id(instance.instance_id, step_index, call.tool_name)
        branch_id = _branch_id(candidate_id)
        branch_handle = _open_agent_branch(
            adapter=adapter,
            branch_id=branch_id,
            parent_branch_id=active_parent_branch_id,
            base_workspace=base_workspace,
        )
        prepared = ToolExecutionContext(
            workspace=branch_handle,
            migration_context=context.migration_context,
            objective=context.objective,
            timeout_seconds=context.timeout_seconds,
            metadata={
                "candidate_id": candidate_id,
                "branch_id": branch_id,
                "parent_hypothesis_id": active_parent_hypothesis_id,
                "parent_branch_id": active_parent_branch_id,
                "workspace_role": "agent_candidate_branch",
            },
        )
        prepared_contexts[step_index] = prepared
        return prepared

    loop = AgentLoop(
        registry=registry,
        tool_chooser=chooser,
        medium=medium,
        event_log=event_log,
        run_id=run_id,
        instance_id=instance.instance_id,
        actor=arm_id,
        context_preparer=prepare_context,
        forbidden_tools=_forbidden_tools(extras),
    )

    for step_index in range(int(max_steps)):
        step = loop.step(
            context=ToolExecutionContext(
                workspace=active_workspace,
                migration_context=migration_context,
                objective=instance.objective,
                timeout_seconds=float(extras.get("workspace_timeout_seconds", 600.0)),
            ),
            objective=instance.objective,
            migration_context=migration_context,
            current_best=best.snapshot(),
        )
        if not step.result.candidate_created:
            if step.result.status in {"failed", "rejected"}:
                loop.record_verifier_feedback(
                    _feedback_from_tool_result(instance, step.call, step.result)
                )
            continue

        prepared = prepared_contexts.get(step_index)
        if prepared is None or not isinstance(prepared.workspace, WorkspaceHandle):
            raise RuntimeError("candidate-creating tool did not prepare a workspace")
        candidate = _candidate_from_step(
            instance=instance,
            step_index=step_index,
            call=step.call,
            result_metadata=step.result.metadata,
            parent_hypothesis_id=active_parent_hypothesis_id,
        )
        report = _validate_agent_candidate(
            adapter=adapter,
            event_log=event_log,
            graph=graph,
            run_id=run_id,
            instance_id=instance.instance_id,
            candidate=candidate,
            workspace=prepared.workspace,
        )
        reports.append(report)
        best.update(report)
        loop.record_verifier_feedback(report.feedback)
        active_workspace = prepared.workspace
        active_parent_hypothesis_id = report.hypothesis_id
        active_parent_branch_id = str(
            prepared.workspace.metadata.get("branch_id") or ""
        ) or active_parent_branch_id
        if report.passed:
            finalization = _finalize_agent_candidate(
                adapter=adapter,
                event_log=event_log,
                graph=graph,
                run_id=run_id,
                instance_id=instance.instance_id,
                hypothesis_id=report.hypothesis_id,
                workspace=prepared.workspace,
            )
            break

    stop_reason = _stop_reason(finalization=finalization, reports=reports)
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
            actor="v12_runner",
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
    medium_created_patch_count = medium.created_patch_count if medium else 0
    suggest_tool_applied_patch_count = _suggest_tool_applied_patch_count(event_log.for_run(run_id))
    event_log.append(
        run_id=run_id,
        instance_id=instance.instance_id,
        event_type="run.completed",
        actor="v12_runner",
        payload={
            "strategy": V12_TOOL_STRATEGY_NAME,
            "arm_id": arm_id,
            "stop_reason": stop_reason,
            "candidate_count": len(reports),
            "selected_hypothesis_id": selected_hypothesis_id,
            "best_observed": best.snapshot(),
            "medium_created_patch_count": int(medium_created_patch_count),
            "suggest_tool_applied_patch_count": int(suggest_tool_applied_patch_count),
            "tool_recommendation_metrics": (
                summarize_tool_recommendation_metrics(event_log.for_run(run_id)).to_dict()
            ),
        },
    )
    score = finalization.score if finalization is not None else None
    artifact = finalization.artifact if finalization is not None else None
    return {
        "stop_reason": stop_reason,
        "strict_success": bool(finalization and finalization.strict_success),
        "selected_hypothesis_id": selected_hypothesis_id,
        "candidate_count": len(reports),
        "signals": dict(score.metrics) if score is not None else {},
        "artifact_paths": _artifact_paths(artifact),
    }


def _tool_chooser_for_instance(
    *,
    adapter: MigrationBenchAdapterV10,
    extras: dict[str, Any],
    instance: RunInstance,
    observation: Any,
):
    injected = extras.get("v12_tool_chooser")
    if callable(injected):
        return injected
    config = V12LLMConfig.from_extras(extras)
    if config is None:
        raise RuntimeError("V12.3 tool-agent arm requires a configured V12 LLM provider")
    client = V12NativeToolClient(config)

    def choose(local_view, tools, history):
        return client.choose_tool(
            local_view,
            tools,
            history,
            instance=instance,
            observation=observation,
            prompt_kind="migrationbench_v12_3_tool_step",
        )

    return choose


def _validate_agent_candidate(
    *,
    adapter: MigrationBenchAdapterV10,
    event_log: JsonlEventLog,
    graph: HypothesisGraph,
    run_id: str,
    instance_id: str,
    candidate: Candidate,
    workspace: WorkspaceHandle,
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
        actor="v12_agent",
        hypothesis_id=node.hypothesis_id,
        payload={"candidate": candidate},
    )
    apply_result = ApplyResult(
        candidate_id=candidate.candidate_id,
        applied=True,
        workspace=workspace,
        summary="workspace mutated by explicit V12 agent tool",
        metadata={
            "applied_by": "v12_agent_tool",
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
        actor="v12_tool_executor",
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
        event_ids=(
            created.event_id,
            applied.event_id,
            validated.event_id,
            feedback_event.event_id,
        ),
    )


def _finalize_agent_candidate(
    *,
    adapter: MigrationBenchAdapterV10,
    event_log: JsonlEventLog,
    graph: HypothesisGraph,
    run_id: str,
    instance_id: str,
    hypothesis_id: str,
    workspace: WorkspaceHandle,
) -> FinalizationReport:
    node = graph.get(hypothesis_id)
    artifact = adapter.finalize(node.candidate, workspace)
    artifact_errors = adapter.artifact_contract.validate_artifact(artifact)
    score = adapter.score(artifact)
    score_errors = adapter.artifact_contract.validate_score(score)
    contract_errors = tuple(artifact_errors + score_errors)
    graph.select_best([hypothesis_id])
    finalized = event_log.append(
        run_id=run_id,
        instance_id=instance_id,
        event_type="artifact.finalized",
        actor="adapter",
        hypothesis_id=hypothesis_id,
        payload={"artifact": artifact, "contract_errors": contract_errors},
    )
    scored = event_log.append(
        run_id=run_id,
        instance_id=instance_id,
        event_type="score.completed",
        actor="adapter",
        hypothesis_id=hypothesis_id,
        payload={
            "score": score,
            "strict_success": score.strict_success and not contract_errors,
        },
    )
    return FinalizationReport(
        hypothesis_id=hypothesis_id,
        artifact=artifact,
        score=score,
        contract_errors=contract_errors,
        event_ids=(finalized.event_id, scored.event_id),
    )


def _open_agent_branch(
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
        role="v12_agent_candidate",
        artifacts_dir=base_workspace.metadata.get("artifacts_dir"),
        official_eval_command=base_workspace.metadata.get("official_eval_command"),
    )


def _candidate_from_step(
    *,
    instance: RunInstance,
    step_index: int,
    call: ToolCall,
    result_metadata: dict[str, Any],
    parent_hypothesis_id: str | None,
) -> Candidate:
    context = dict(result_metadata.get("execution_context") or {})
    candidate_id = str(context.get("candidate_id") or _candidate_id(instance.instance_id, step_index, call.tool_name))
    branch_id = str(context.get("branch_id") or _branch_id(candidate_id))
    parent_branch_id = context.get("parent_branch_id")
    payload: dict[str, Any] = {
        "branch_id": branch_id,
        "parent_branch_id": parent_branch_id,
        "created_by_tool": call.tool_name,
    }
    if call.tool_name == "edit_file_guarded":
        payload["edit_set"] = {
            "edits": call.arguments.get("edits") or [],
            "rationale": call.arguments.get("rationale") or call.rationale,
            "expected_build_command": call.arguments.get("expected_build_command"),
        }
    elif call.tool_name == "apply_patch":
        payload["patch_source"] = "v12_apply_patch_tool"
    return Candidate(
        candidate_id=candidate_id,
        kind=CandidateKind.PATCH,
        payload=payload,
        origin=f"v12_agent_tool:{call.tool_name}",
        parent_id=parent_hypothesis_id,
        metadata={
            "tool_call": call.model_dump(mode="json"),
            "branch_id": branch_id,
            "parent_branch_id": parent_branch_id,
        },
    )


def _feedback_from_tool_result(instance: RunInstance, call: ToolCall, result) -> FeedbackDigest:
    return FeedbackDigest(
        candidate_id=f"{instance.instance_id}:{call.call_id or call.tool_name}",
        failure_type=f"tool_{result.status}",
        severity="blocking",
        summary=f"{call.tool_name}: {result.summary}",
        evidence=list(result.errors or []),
        recommended_next_actions=[{"action": "choose_different_tool_or_parameters"}],
        anti_actions=[f"repeat_failed_tool:{call.tool_name}"],
        metadata={"tool_name": call.tool_name, "tool_result": result.model_dump(mode="json")},
    )


def _score_from_validation(validation: ValidationResult) -> HypothesisScore:
    score, _stage = _funnel_score(validation)
    if score:
        return HypothesisScore(
            quality=max(0.0, score / 100.0),
            confidence=1.0 if validation.status == ValidationStatus.PASSED else 0.0,
            risk=0.0 if score > 0 else 0.2,
        )
    return HypothesisScore(risk=1.0)


def _funnel_score(validation: ValidationResult) -> tuple[int, str]:
    haystack = "\n".join([validation.summary or "", *map(str, validation.errors)])
    if "replacement_count_too_low" in haystack:
        return -20, "replacement_error"
    signals = dict(validation.signals or {})
    for stage, score in (
        ("strict_success", 100),
        ("official_success", 80),
        ("test_success", 60),
        ("class_version_ok", 50),
        ("compile_success", 40),
        ("patch_applies", 20),
        ("patch_delivered", 10),
        ("applied", 10),
    ):
        if bool(signals.get(stage)):
            return score, stage
    return 0, "none"


def _report_competitor(report: VerifierReport) -> dict[str, Any]:
    score, stage = _funnel_score(report.validation)
    return {
        "hypothesis_id": report.hypothesis_id,
        "candidate_id": report.candidate_id,
        "funnel_score": int(score),
        "funnel_stage": stage,
        "validation_status": report.validation.status.value,
    }


def _suggest_tool_applied_patch_count(events: Sequence[Any]) -> int:
    count = 0
    for event in events:
        if event.event_type != "tool.executed":
            continue
        result = event.payload.get("result") or {}
        tool_name = str(result.get("tool_name") or "")
        if tool_name.startswith("suggest_") and (
            result.get("workspace_mutated") or result.get("candidate_created")
        ):
            count += 1
    return count


def _forbidden_tools(extras: dict[str, Any]) -> dict[str, str]:
    forbidden: dict[str, str] = {}
    if not bool(extras.get("official_eval", True)):
        forbidden["run_official_eval"] = "official_eval disabled by campaign config"
    return forbidden


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
        return "agent_steps_exhausted"
    return "no_candidate_created"


def _artifact_paths(artifact: ArtifactResult | None) -> dict[str, str]:
    if artifact is None:
        return {}
    return {str(key): str(value) for key, value in artifact.artifacts.items()}


def _candidate_id(instance_id: str, step_index: int, tool_name: str) -> str:
    return f"{_safe_id(instance_id)}-v12-step{step_index:02d}-{_safe_id(tool_name)}"


def _branch_id(candidate_id: str) -> str:
    return f"branch-{_safe_id(candidate_id)}"


def _safe_id(value: str) -> str:
    import re

    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value))[:120]


def _arm_extras(
    options: V12AgenticOptions,
    *,
    arm_id: str,
    arm_dir: Path,
) -> dict[str, Any]:
    extras = dict(options.extras or {})
    extras["out_dir"] = str(arm_dir)
    extras.setdefault("llm_trace_enabled", True)
    extras.setdefault("use_llm_providers", True)
    for key in ("workspace_root_root", "artifacts_root"):
        if extras.get(key):
            extras[key] = str(Path(str(extras[key])) / arm_id)
    return extras


def _arm_payload(*, arm_id: str, description: str, summary: Any, arm_dir: Path) -> dict[str, Any]:
    payload = summary.to_dict()
    events = _read_arm_events(arm_dir)
    tool_metrics = summarize_tool_recommendation_metrics(events).to_dict()
    payload.update(
        {
            "arm_id": arm_id,
            "description": description,
            "tool_recommendation_metrics": tool_metrics,
            "medium_created_patch_count": _run_completed_sum(events, "medium_created_patch_count"),
            "suggest_tool_applied_patch_count": _run_completed_sum(events, "suggest_tool_applied_patch_count"),
            "tool_call_total": sum(1 for event in events if event.event_type == "agent.tool_call.requested"),
            "tool_success_rate": _tool_success_rate(events),
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


def _tool_success_rate(events: Sequence[Any]) -> float:
    tool_events = [event for event in events if event.event_type == "tool.executed"]
    if not tool_events:
        return 0.0
    success = sum(
        1
        for event in tool_events
        if (event.payload.get("result") or {}).get("status") == "success"
    )
    return success / float(len(tool_events))


def _persist_graph(out_dir: Path, instance_id: str, graph: HypothesisGraph) -> None:
    target = out_dir / "hypotheses" / instance_id / "graph.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(graph.to_json() + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="scripts.v12.run_v12_agentic_comparison",
        description=__doc__,
    )
    parser.add_argument("--adapter", default="migrationbench")
    parser.add_argument("--subset", type=Path, default=V12_DEFAULT_SUBSET)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--max-steps", type=int, default=6)
    parser.add_argument("--extras", default="{}")
    parser.add_argument("--clean", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    comparison = run_v12_agentic_comparison(
        adapter_name=args.adapter,
        subset_path=args.subset,
        out_dir=args.out_dir,
        seed=int(args.seed),
        limit=args.limit,
        max_steps=int(args.max_steps),
        extras=json.loads(args.extras or "{}"),
        clean=bool(args.clean),
    )
    print(json.dumps(comparison, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())


__all__ = [
    "V12_DEFAULT_SUBSET",
    "V12_TOOL_STRATEGY_NAME",
    "V12AgenticOptions",
    "build_parser",
    "main",
    "run_v12_agentic_comparison",
]
