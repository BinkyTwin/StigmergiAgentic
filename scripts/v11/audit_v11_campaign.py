"""Audit V11 MigrationBench campaign artifacts.

The script is intentionally read-only for campaign data. It reconstructs
best-observed funnel progress, pairwise arm deltas, operator family coverage,
and LLM-call trace summaries from ``comparison.json``, EventLogs, summaries,
and ``llm_traces``.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence


FUNNEL_STAGES: tuple[tuple[str, int], ...] = (
    ("strict_success", 100),
    ("official_success", 80),
    ("test_success", 60),
    ("class_version_ok", 50),
    ("compile_success", 40),
    ("patch_applies", 20),
    ("patch_delivered", 10),
)


@dataclass(frozen=True)
class EventRow:
    arm_id: str
    instance_id: str
    sequence: int
    event_type: str
    hypothesis_id: str | None
    payload: dict[str, Any]


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as stream:
        for line in stream:
            stripped = line.strip()
            if stripped:
                yield json.loads(stripped)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _write_csv(
    path: Path, rows: Sequence[dict[str, Any]], fieldnames: Sequence[str]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _csv_cell(row.get(key)) for key in fieldnames})


def _csv_cell(value: Any) -> Any:
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, sort_keys=True)
    if value is None:
        return ""
    return value


def _campaign_arms(root: Path, comparison: dict[str, Any]) -> list[str]:
    arm_ids = [
        str(arm.get("arm_id"))
        for arm in comparison.get("arms", [])
        if arm.get("arm_id")
    ]
    if arm_ids:
        return arm_ids
    return sorted(
        child.name
        for child in root.iterdir()
        if child.is_dir() and (child / "summary.json").exists()
    )


def _load_events(root: Path, arm_ids: Sequence[str]) -> list[EventRow]:
    rows: list[EventRow] = []
    for arm_id in arm_ids:
        events_root = root / arm_id / "events"
        for path in sorted(events_root.glob("*/eventlog.jsonl")):
            instance_id = path.parent.name
            for item in _iter_jsonl(path):
                rows.append(
                    EventRow(
                        arm_id=arm_id,
                        instance_id=str(item.get("instance_id") or instance_id),
                        sequence=int(item.get("sequence") or 0),
                        event_type=str(item.get("type") or ""),
                        hypothesis_id=item.get("hypothesis_id"),
                        payload=dict(item.get("payload") or {}),
                    )
                )
    return rows


def _score_validation(validation: dict[str, Any]) -> tuple[int, str]:
    text = "\n".join(
        str(part)
        for part in (
            validation.get("summary"),
            validation.get("raw_output"),
            *(validation.get("errors") or []),
        )
        if part is not None
    )
    if "replacement_count_too_low" in text:
        return -20, "replacement_error"
    signals = dict(validation.get("signals") or {})
    for stage, score in FUNNEL_STAGES:
        if bool(signals.get(stage)):
            return score, stage
    if bool(signals.get("applied")):
        return 10, "patch_delivered"
    return 0, "none"


def _stage_flags(validations: Iterable[dict[str, Any]]) -> dict[str, bool]:
    flags = {f"best_{stage}": False for stage, _score in FUNNEL_STAGES}
    flags["best_patch_applies"] = False
    for validation in validations:
        signals = dict(validation.get("signals") or {})
        for stage, _score in FUNNEL_STAGES:
            key = f"best_{stage}"
            flags[key] = bool(flags[key] or signals.get(stage))
        flags["best_patch_applies"] = bool(
            flags["best_patch_applies"]
            or signals.get("patch_applies")
            or signals.get("applied")
        )
    return flags


def _brief_text(value: Any, *, limit: int = 240) -> str:
    if isinstance(value, list):
        value = " ".join(str(item) for item in value[:2])
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "..."


def _failure_family(*parts: Any) -> str:
    text = " ".join(str(part or "") for part in parts).lower()
    if "classify_missing_external_dependency" in text:
        return "missing_internal_or_snapshot_dependency"
    if "upgrade_bundle_plugin" in text:
        return "maven_bundle_felix"
    if "diagnose_bytecode_reader_incompatibility" in text:
        return "spring_asm_class_major"
    if "replace_sun_misc_base64" in text:
        return "removed_jdk_internal_api_sun_misc_base64"
    if "add_javafx_dependencies" in text:
        return "javafx_missing_dependencies"
    if "fix_official_test_summary" in text or "interpret_official_eval" in text:
        return "official_eval_summary_or_tests_minus2"
    if "upgrade_lombok_for_target_java" in text:
        return "lombok_or_javac_internal_api"
    if any(
        token in text
        for token in ("lombok", "delombok", "jdk.compiler", "com.sun.tools.javac")
    ):
        return "lombok_or_javac_internal_api"
    if any(
        token in text
        for token in (
            "spring",
            "asm",
            "classreader",
            "major version 61",
            "unsupported class file major",
            "cglib",
        )
    ):
        return "spring_asm_class_major"
    if any(
        token in text
        for token in (
            "#tests=-2",
            "test summary",
            "surefire summary",
            "official_eval_failed",
            "standard maven/surefire",
        )
    ):
        return "official_eval_summary_or_tests_minus2"
    if any(
        token in text
        for token in (
            "snapshot",
            "internal",
            "could not find artifact",
            "non-resolvable",
            "camunda",
            "hashids",
        )
    ):
        return "missing_internal_or_snapshot_dependency"
    if any(
        token in text
        for token in (
            "javafx",
            "openjfx",
            "textfield",
            "pane",
            "stage",
            "javafx.application",
        )
    ):
        return "javafx_missing_dependencies"
    if any(
        token in text
        for token in (
            "maven-bundle-plugin",
            "org.apache.felix",
            "bnd",
            "concurrentmodificationexception",
        )
    ):
        return "maven_bundle_felix"
    if any(token in text for token in ("sun.misc", "base64encoder", "base64decoder")):
        return "removed_jdk_internal_api_sun_misc_base64"
    if any(
        token in text
        for token in (
            "maven.compiler",
            "compiler release",
            "source/target",
            "class_version_error",
            "class version",
        )
    ):
        return "maven_compiler_release_or_class_version"
    if any(token in text for token in ("jfr", "add-exports", "module export")):
        return "jdk_internal_module_export_jfr"
    if "test" in text:
        return "test_failure_general"
    return "other"


def _index_events(events: Sequence[EventRow]) -> dict[str, Any]:
    validations: dict[tuple[str, str, str], dict[str, Any]] = {}
    feedbacks: dict[tuple[str, str, str], dict[str, Any]] = {}
    candidates: dict[tuple[str, str, str], dict[str, Any]] = {}
    affordances: dict[tuple[str, str, str], dict[str, Any]] = {}
    run_completed: dict[tuple[str, str], dict[str, Any]] = {}

    for event in events:
        key2 = (event.arm_id, event.instance_id)
        if event.event_type == "validation.completed":
            validation = dict(event.payload.get("validation") or {})
            candidate_id = str(
                validation.get("candidate_id") or event.hypothesis_id or ""
            )
            if candidate_id:
                validations[(*key2, candidate_id)] = validation
        elif event.event_type == "feedback.created":
            feedback = dict(event.payload.get("feedback") or {})
            candidate_id = str(
                feedback.get("candidate_id") or event.hypothesis_id or ""
            )
            if candidate_id:
                feedbacks[(*key2, candidate_id)] = feedback
        elif event.event_type == "candidate.created":
            candidate = dict(event.payload.get("candidate") or {})
            candidate_id = str(
                candidate.get("candidate_id") or event.hypothesis_id or ""
            )
            if candidate_id:
                candidates[(*key2, candidate_id)] = candidate
        elif event.event_type == "affordance.created":
            affordance = dict(event.payload.get("affordance") or event.payload)
            affordance_id = str(affordance.get("affordance_id") or "")
            if affordance_id:
                affordances[(*key2, affordance_id)] = affordance
        elif event.event_type == "run.completed":
            run_completed[key2] = dict(event.payload)
    return {
        "validations": validations,
        "feedbacks": feedbacks,
        "candidates": candidates,
        "affordances": affordances,
        "run_completed": run_completed,
    }


def _best_observed_rows(
    *,
    root: Path,
    arm_ids: Sequence[str],
    events: Sequence[EventRow],
    indexes: dict[str, Any],
) -> list[dict[str, Any]]:
    summary_by_instance: dict[tuple[str, str], dict[str, Any]] = {}
    for arm_id in arm_ids:
        summary = _load_json(root / arm_id / "summary.json")
        for inst in summary.get("instances", []):
            summary_by_instance[(arm_id, str(inst.get("instance_id")))] = dict(inst)

    validations_by_key: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for (arm_id, instance_id, _candidate_id), validation in indexes[
        "validations"
    ].items():
        validations_by_key[(arm_id, instance_id)].append(validation)

    all_keys = sorted(
        set(summary_by_instance)
        | set(validations_by_key)
        | set(indexes["run_completed"])
    )
    rows: list[dict[str, Any]] = []
    for arm_id, instance_id in all_keys:
        validations = validations_by_key.get((arm_id, instance_id), [])
        scored: list[tuple[int, str, str, dict[str, Any]]] = []
        for validation in validations:
            score, stage = _score_validation(validation)
            scored.append(
                (score, stage, str(validation.get("candidate_id") or ""), validation)
            )
        best_score, best_stage, best_candidate_id = 0, "none", ""
        if scored:
            best_score, best_stage, best_candidate_id, _validation = max(
                scored, key=lambda row: (row[0], row[2])
            )
        run_payload = indexes["run_completed"].get((arm_id, instance_id), {})
        summary_inst = summary_by_instance.get((arm_id, instance_id), {})
        flags = _stage_flags(validations)
        row = {
            "arm_id": arm_id,
            "instance_id": instance_id,
            "best_candidate_id": best_candidate_id,
            "best_stage": best_stage,
            "best_funnel_score": int(best_score),
            "run_completed_best_stage": (run_payload.get("best_observed") or {}).get(
                "best_stage"
            ),
            "run_completed_best_score": (run_payload.get("best_observed") or {}).get(
                "best_funnel_score"
            ),
            "selected_hypothesis_id": summary_inst.get("selected_hypothesis_id")
            or run_payload.get("selected_hypothesis_id"),
            "stop_reason": summary_inst.get("stop_reason")
            or run_payload.get("stop_reason"),
            "strict_success": bool(summary_inst.get("strict_success")),
            "validation_count": len(validations),
            **flags,
        }
        rows.append(row)
    return rows


def _pairwise_rows(best_rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    by_arm_instance = {
        (str(row["arm_id"]), str(row["instance_id"])): row for row in best_rows
    }
    comparisons = (
        ("B6_operator_search", "B5_stigmergic_scheduler"),
        ("B6_operator_search", "B2_branching_repair"),
        ("B5_stigmergic_scheduler", "B2_branching_repair"),
    )
    rows: list[dict[str, Any]] = []
    for treatment, control in comparisons:
        instance_ids = sorted(
            instance_id
            for arm_id, instance_id in by_arm_instance
            if arm_id == treatment and (control, instance_id) in by_arm_instance
        )
        for instance_id in instance_ids:
            t_row = by_arm_instance[(treatment, instance_id)]
            c_row = by_arm_instance[(control, instance_id)]
            delta = int(t_row["best_funnel_score"]) - int(c_row["best_funnel_score"])
            rows.append(
                {
                    "comparison": f"{treatment}_vs_{control}",
                    "instance_id": instance_id,
                    "treatment_arm": treatment,
                    "control_arm": control,
                    "treatment_best_score": int(t_row["best_funnel_score"]),
                    "control_best_score": int(c_row["best_funnel_score"]),
                    "delta": int(delta),
                    "relation": (
                        "better" if delta > 0 else "worse" if delta < 0 else "same"
                    ),
                    "treatment_best_stage": t_row["best_stage"],
                    "control_best_stage": c_row["best_stage"],
                    "treatment_strict_success": bool(t_row.get("strict_success")),
                    "control_strict_success": bool(c_row.get("strict_success")),
                    "strict_delta": int(bool(t_row.get("strict_success")))
                    - int(bool(c_row.get("strict_success"))),
                    "treatment_best_candidate_id": t_row.get("best_candidate_id"),
                    "control_best_candidate_id": c_row.get("best_candidate_id"),
                }
            )
    return rows


def _latest_feedback_before(
    events: Sequence[EventRow], event: EventRow
) -> dict[str, Any]:
    latest: dict[str, Any] = {}
    for prior in events:
        if prior.sequence >= event.sequence:
            break
        if prior.event_type == "feedback.created":
            latest = dict(prior.payload.get("feedback") or {})
    return latest


def _operator_audit_rows(
    events: Sequence[EventRow],
    indexes: dict[str, Any],
    best_rows: Sequence[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    by_instance_events: dict[tuple[str, str], list[EventRow]] = defaultdict(list)
    for event in sorted(events, key=lambda item: item.sequence):
        by_instance_events[(event.arm_id, event.instance_id)].append(event)

    best_by_key = {(row["arm_id"], row["instance_id"]): row for row in best_rows}
    applied_rows: list[dict[str, Any]] = []
    unavailable_rows: list[dict[str, Any]] = []
    helped_rows: list[dict[str, Any]] = []

    for key, instance_events in by_instance_events.items():
        arm_id, instance_id = key
        rejected_by_candidate = {
            str(event.payload.get("candidate_id") or ""): dict(event.payload)
            for event in instance_events
            if event.event_type == "operator.rejected"
            and event.payload.get("candidate_id")
        }
        for event in instance_events:
            if event.event_type == "operator.applied":
                invocation = dict(event.payload.get("operator_invocation") or {})
                params = dict(invocation.get("params") or {})
                source_affordance_id = str(invocation.get("source_affordance_id") or "")
                affordance = indexes["affordances"].get(
                    (arm_id, instance_id, source_affordance_id), {}
                )
                candidate_id = str(
                    event.payload.get("candidate_id") or event.hypothesis_id or ""
                )
                rejection = rejected_by_candidate.get(candidate_id, {})
                candidate = indexes["candidates"].get(
                    (arm_id, instance_id, candidate_id), {}
                )
                parent_id = str(candidate.get("parent_id") or "")
                parent_validation = indexes["validations"].get(
                    (arm_id, instance_id, parent_id), {}
                )
                op_validation = indexes["validations"].get(
                    (arm_id, instance_id, candidate_id), {}
                )
                parent_score, parent_stage = (
                    _score_validation(parent_validation)
                    if parent_validation
                    else (0, "none")
                )
                op_score, op_stage = (
                    _score_validation(op_validation) if op_validation else (0, "none")
                )
                delta = op_score - parent_score
                family = _failure_family(
                    invocation.get("operator_id"),
                    params.get("failure_type"),
                    params.get("action_type"),
                    affordance.get("reason"),
                    _brief_text(
                        (
                            indexes["feedbacks"].get(
                                (arm_id, instance_id, parent_id), {}
                            )
                            or {}
                        ).get("evidence")
                    ),
                )
                row = {
                    "arm_id": arm_id,
                    "instance_id": instance_id,
                    "operator_id": invocation.get("operator_id"),
                    "failure_family": family,
                    "failure_type": params.get("failure_type"),
                    "affordance_action_type": params.get("action_type")
                    or affordance.get("action_type"),
                    "source_affordance_id": source_affordance_id,
                    "candidate_id": candidate_id,
                    "parent_candidate_id": parent_id,
                    "parent_branch_id": (candidate.get("payload") or {}).get(
                        "parent_branch_id"
                    ),
                    "target_files": invocation.get("target_files") or [],
                    "applied": bool(event.payload.get("applied")),
                    "errors": event.payload.get("errors") or [],
                }
                applied_rows.append(row)
                helped_rows.append(
                    {
                        **row,
                        "parent_score": int(parent_score),
                        "operator_score": int(op_score),
                        "delta": int(delta),
                        "relation": (
                            "blocked_regression"
                            if rejection.get("reason") == "operator_regressed_funnel"
                            else (
                                "helped"
                                if delta > 0
                                else "harmed" if delta < 0 else "neutral"
                            )
                        ),
                        "rejection_reason": rejection.get("reason"),
                        "parent_stage": parent_stage,
                        "operator_stage": op_stage,
                    }
                )
            elif event.event_type == "operator.unavailable":
                payload = dict(event.payload)
                affordance_id = str(payload.get("affordance_id") or "")
                affordance = indexes["affordances"].get(
                    (arm_id, instance_id, affordance_id), {}
                )
                feedback = _latest_feedback_before(instance_events, event)
                summary = _brief_text(
                    feedback.get("summary")
                    or feedback.get("evidence")
                    or feedback.get("failure_type")
                )
                family = _failure_family(
                    feedback.get("failure_type"),
                    summary,
                    payload.get("action_type"),
                    affordance.get("reason"),
                    affordance.get("action_type"),
                )
                best = best_by_key.get((arm_id, instance_id), {})
                unavailable_rows.append(
                    {
                        "arm_id": arm_id,
                        "instance_id": instance_id,
                        "failure_family": family,
                        "failure_type": feedback.get("failure_type"),
                        "summary": summary,
                        "affordance_action_type": payload.get("action_type")
                        or affordance.get("action_type"),
                        "expected_worker_kind": affordance.get("expected_worker_kind"),
                        "worker_id": payload.get("worker_id"),
                        "source_affordance_id": affordance_id,
                        "operator_unavailable_reason": payload.get("reason"),
                        "fallback_policy": payload.get("fallback_policy"),
                        "best_observed_stage": best.get("best_stage"),
                        "best_observed_score": best.get("best_funnel_score"),
                    }
                )
    return applied_rows, unavailable_rows, helped_rows


def _llm_trace_rows(
    root: Path, arm_ids: Sequence[str]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    call_rows: list[dict[str, Any]] = []
    for arm_id in arm_ids:
        trace_path = root / arm_id / "llm_traces" / "calls.jsonl"
        for item in _iter_jsonl(trace_path):
            normalized_edits = item.get("normalized_edits") or []
            call_rows.append(
                {
                    "arm_id": arm_id,
                    "instance_id": item.get("instance_id"),
                    "call_kind": item.get("call_kind"),
                    "slot_index": item.get("slot_index"),
                    "candidate_id": item.get("candidate_id"),
                    "parent_candidate_id": item.get("parent_candidate_id"),
                    "candidate_emitted": bool(item.get("candidate_emitted")),
                    "dropped_reason": item.get("dropped_reason"),
                    "call_error": item.get("call_error"),
                    "parse_ok": item.get("parse_ok"),
                    "normalized_edit_count": item.get("normalized_edit_count"),
                    "normalization_issue_reasons": sorted(
                        {
                            str(issue.get("reason"))
                            for issue in (item.get("normalization_issues") or [])
                            if isinstance(issue, dict) and issue.get("reason")
                        }
                    ),
                    "paths": sorted(
                        {
                            str(edit.get("path"))
                            for edit in normalized_edits
                            if isinstance(edit, dict) and edit.get("path")
                        }
                    ),
                    "feedback_failure_type": item.get("feedback_failure_type"),
                    "provider": item.get("provider"),
                    "model": item.get("model"),
                    "duration_seconds": item.get("duration_seconds"),
                    "prompt_tokens": (item.get("usage") or {}).get("prompt_tokens"),
                    "completion_tokens": (item.get("usage") or {}).get(
                        "completion_tokens"
                    ),
                    "total_tokens": (item.get("usage") or {}).get("total_tokens"),
                    "system_prompt_chars": item.get("system_prompt_chars"),
                    "user_prompt_chars": item.get("user_prompt_chars"),
                    "raw_response_chars": item.get("raw_response_chars"),
                    "trace_file": str(trace_path),
                }
            )
    counters: dict[tuple[Any, ...], Counter[str]] = defaultdict(Counter)
    for row in call_rows:
        key = (row["arm_id"], row["call_kind"], row["model"])
        counters[key]["calls"] += 1
        counters[key]["candidate_emitted"] += int(bool(row["candidate_emitted"]))
        counters[key]["parse_failures"] += int(row["parse_ok"] is False)
        if row["call_error"]:
            counters[key]["call_errors"] += 1
        if row["dropped_reason"]:
            counters[key][f"dropped:{row['dropped_reason']}"] += 1
    aggregate_rows = [
        {
            "arm_id": arm_id,
            "call_kind": call_kind,
            "model": model,
            **dict(counter),
        }
        for (arm_id, call_kind, model), counter in sorted(counters.items())
    ]
    return call_rows, aggregate_rows


def _aggregate_counts(
    rows: Sequence[dict[str, Any]], keys: Sequence[str]
) -> list[dict[str, Any]]:
    counter: Counter[tuple[Any, ...]] = Counter()
    for row in rows:
        counter[tuple(row.get(key) for key in keys)] += 1
    return [
        {
            **{key: value for key, value in zip(keys, values, strict=False)},
            "count": count,
        }
        for values, count in sorted(
            counter.items(), key=lambda item: (-item[1], item[0])
        )
    ]


def _write_markdown_summary(
    path: Path,
    *,
    root: Path,
    best_rows: Sequence[dict[str, Any]],
    pairwise_rows: Sequence[dict[str, Any]],
    applied_rows: Sequence[dict[str, Any]],
    unavailable_rows: Sequence[dict[str, Any]],
    helped_rows: Sequence[dict[str, Any]],
    llm_calls: Sequence[dict[str, Any]],
) -> None:
    strict_by_arm = Counter()
    count_by_arm = Counter()
    best_score_by_arm: dict[str, list[int]] = defaultdict(list)
    for row in best_rows:
        arm = str(row["arm_id"])
        strict_by_arm[arm] += int(bool(row.get("strict_success")))
        count_by_arm[arm] += 1
        best_score_by_arm[arm].append(int(row.get("best_funnel_score") or 0))

    pairwise_counts = _aggregate_counts(pairwise_rows, ("comparison", "relation"))
    family_counts = _aggregate_counts(unavailable_rows, ("failure_family",))
    help_counts = _aggregate_counts(helped_rows, ("relation",))

    lines = [
        "# V11 Campaign Audit",
        "",
        f"Campaign root: `{root}`",
        "",
        "## Arm Overview",
        "",
        "| arm | instances | strict_success | avg_best_score |",
        "| --- | ---: | ---: | ---: |",
    ]
    for arm in sorted(count_by_arm):
        scores = best_score_by_arm[arm]
        avg = sum(scores) / len(scores) if scores else 0.0
        lines.append(
            f"| {arm} | {count_by_arm[arm]} | {strict_by_arm[arm]} | {avg:.1f} |"
        )
    lines.extend(
        [
            "",
            "## Pairwise Best-Observed",
            "",
            "| comparison | relation | count |",
            "| --- | --- | ---: |",
        ]
    )
    for row in pairwise_counts:
        lines.append(
            f"| {row.get('comparison')} | {row.get('relation')} | {row.get('count')} |"
        )
    lines.extend(["", "## Operator Coverage", ""])
    lines.append(f"- operator.applied rows: {len(applied_rows)}")
    lines.append(f"- operator.unavailable rows: {len(unavailable_rows)}")
    lines.append(f"- LLM trace calls: {len(llm_calls)}")
    lines.extend(
        [
            "",
            "### operator.unavailable by family",
            "",
            "| family | count |",
            "| --- | ---: |",
        ]
    )
    for row in family_counts:
        lines.append(f"| {row.get('failure_family')} | {row.get('count')} |")
    lines.extend(
        ["", "### operator effect", "", "| relation | count |", "| --- | ---: |"]
    )
    for row in help_counts:
        lines.append(f"| {row.get('relation')} | {row.get('count')} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def audit_campaign(root: Path) -> dict[str, Any]:
    comparison = _load_json(root / "comparison.json")
    arm_ids = _campaign_arms(root, comparison)
    events = _load_events(root, arm_ids)
    indexes = _index_events(events)
    audits_dir = root / "audits"

    best_rows = _best_observed_rows(
        root=root, arm_ids=arm_ids, events=events, indexes=indexes
    )
    pairwise_rows = _pairwise_rows(best_rows)
    applied_rows, unavailable_rows, helped_rows = _operator_audit_rows(
        events, indexes, best_rows
    )
    llm_calls, llm_aggregates = _llm_trace_rows(root, arm_ids)

    _write_csv(
        audits_dir / "best_observed_funnel.csv",
        best_rows,
        (
            "arm_id",
            "instance_id",
            "best_candidate_id",
            "best_stage",
            "best_funnel_score",
            "best_patch_applies",
            "best_compile_success",
            "best_test_success",
            "best_class_version_ok",
            "best_official_success",
            "best_strict_success",
            "run_completed_best_stage",
            "run_completed_best_score",
            "selected_hypothesis_id",
            "stop_reason",
            "strict_success",
            "validation_count",
        ),
    )
    _write_json(audits_dir / "best_observed_funnel.json", best_rows)

    _write_csv(
        audits_dir / "pairwise_best_observed.csv",
        pairwise_rows,
        (
            "comparison",
            "instance_id",
            "treatment_arm",
            "control_arm",
            "treatment_best_score",
            "control_best_score",
            "delta",
            "relation",
            "treatment_best_stage",
            "control_best_stage",
            "treatment_strict_success",
            "control_strict_success",
            "strict_delta",
            "treatment_best_candidate_id",
            "control_best_candidate_id",
        ),
    )
    _write_json(audits_dir / "pairwise_best_observed.json", pairwise_rows)

    _write_csv(
        audits_dir / "operator_applied_by_family.csv",
        applied_rows,
        (
            "arm_id",
            "instance_id",
            "failure_family",
            "operator_id",
            "failure_type",
            "affordance_action_type",
            "source_affordance_id",
            "candidate_id",
            "parent_candidate_id",
            "parent_branch_id",
            "target_files",
            "applied",
            "errors",
        ),
    )
    _write_json(audits_dir / "operator_applied_by_family.json", applied_rows)
    _write_json(
        audits_dir / "operator_applied_by_family_counts.json",
        _aggregate_counts(applied_rows, ("failure_family", "operator_id")),
    )

    _write_csv(
        audits_dir / "operator_unavailable_by_failure_family.csv",
        unavailable_rows,
        (
            "arm_id",
            "instance_id",
            "failure_family",
            "failure_type",
            "summary",
            "affordance_action_type",
            "expected_worker_kind",
            "worker_id",
            "source_affordance_id",
            "operator_unavailable_reason",
            "fallback_policy",
            "best_observed_stage",
            "best_observed_score",
        ),
    )
    _write_json(
        audits_dir / "operator_unavailable_by_failure_family.json", unavailable_rows
    )
    _write_json(
        audits_dir / "operator_unavailable_by_failure_family_counts.json",
        _aggregate_counts(
            unavailable_rows, ("failure_family", "affordance_action_type", "worker_id")
        ),
    )

    _write_csv(
        audits_dir / "operator_helped_harmed_by_instance.csv",
        helped_rows,
        (
            "arm_id",
            "instance_id",
            "failure_family",
            "operator_id",
            "candidate_id",
            "parent_candidate_id",
            "parent_score",
            "operator_score",
            "delta",
            "relation",
            "rejection_reason",
            "parent_stage",
            "operator_stage",
            "source_affordance_id",
            "affordance_action_type",
            "target_files",
        ),
    )
    _write_json(audits_dir / "operator_helped_harmed_by_instance.json", helped_rows)

    _write_csv(
        audits_dir / "llm_trace_calls.csv",
        llm_calls,
        (
            "arm_id",
            "instance_id",
            "call_kind",
            "slot_index",
            "candidate_id",
            "parent_candidate_id",
            "candidate_emitted",
            "dropped_reason",
            "call_error",
            "parse_ok",
            "normalized_edit_count",
            "normalization_issue_reasons",
            "paths",
            "feedback_failure_type",
            "provider",
            "model",
            "duration_seconds",
            "prompt_tokens",
            "completion_tokens",
            "total_tokens",
            "system_prompt_chars",
            "user_prompt_chars",
            "raw_response_chars",
            "trace_file",
        ),
    )
    _write_json(audits_dir / "llm_trace_calls.json", llm_calls)
    _write_json(audits_dir / "llm_trace_aggregate.json", llm_aggregates)

    _write_markdown_summary(
        audits_dir / "audit_summary.md",
        root=root,
        best_rows=best_rows,
        pairwise_rows=pairwise_rows,
        applied_rows=applied_rows,
        unavailable_rows=unavailable_rows,
        helped_rows=helped_rows,
        llm_calls=llm_calls,
    )

    result = {
        "campaign_root": str(root),
        "audits_dir": str(audits_dir),
        "arm_count": len(arm_ids),
        "event_count": len(events),
        "best_observed_rows": len(best_rows),
        "pairwise_rows": len(pairwise_rows),
        "operator_applied_rows": len(applied_rows),
        "operator_unavailable_rows": len(unavailable_rows),
        "operator_helped_harmed_rows": len(helped_rows),
        "llm_trace_calls": len(llm_calls),
    }
    _write_json(audits_dir / "audit_manifest.json", result)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-root", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = audit_campaign(args.campaign_root)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["audit_campaign", "build_parser", "main"]
