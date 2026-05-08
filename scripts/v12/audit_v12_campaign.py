"""Audit V12 agentic and SD-Feedback comparison campaigns."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any, Iterable, Sequence

from core_v10.event_log import EventRecord, JsonlEventLog
from core_v12.metrics import (
    summarize_tool_recommendation_metrics,
    tool_recommendation_context_from_annotations,
)


ARM_IDS_V12_3 = (
    "S1_sd_feedback_like",
    "S2_tool_feedback_agent",
    "V12_stigmergic_tool_agent",
)
ARM_IDS_V12_4 = (
    "S1_sd_feedback_exact",
    "S2_sd_feedback_readonly_tools",
    "V12_stigmergic_sd_feedback",
)
ARM_IDS = (*ARM_IDS_V12_3, *ARM_IDS_V12_4)


def audit_v12_campaign(campaign_root: Path | str) -> dict[str, Any]:
    """Write V12 audit CSVs and a readiness report."""

    root = Path(campaign_root)
    audits_dir = root / "audits"
    audits_dir.mkdir(parents=True, exist_ok=True)
    arm_ids = _detect_arm_ids(root)
    arm_events = {arm: _read_arm_events(root / arm) for arm in arm_ids}
    best_rows = _best_observed_rows(arm_events)
    _write_csv(audits_dir / "best_observed_funnel.csv", best_rows)
    pairwise_rows = _pairwise_best_observed(best_rows)
    _write_csv(audits_dir / "pairwise_best_observed.csv", pairwise_rows)
    tool_trace_rows = _tool_trace_rows(arm_events)
    _write_csv(audits_dir / "tool_trace_calls.csv", tool_trace_rows)
    attribution_rows = _medium_effect_rows(arm_events, pairwise_rows)
    _write_csv(audits_dir / "medium_effect_attribution.csv", attribution_rows)
    readiness = _readiness_report(
        campaign_root=root,
        arm_ids=arm_ids,
        arm_events=arm_events,
        pairwise_rows=pairwise_rows,
        tool_trace_rows=tool_trace_rows,
    )
    (root / "v12_readiness_report.json").write_text(
        json.dumps(readiness, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return readiness


def _read_arm_events(arm_dir: Path) -> list[EventRecord]:
    manifest_path = arm_dir / "manifest.json"
    if not manifest_path.exists():
        return []
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    events: list[EventRecord] = []
    for instance_id in manifest.get("instance_ids") or []:
        path = arm_dir / "events" / str(instance_id) / "eventlog.jsonl"
        if path.exists():
            events.extend(JsonlEventLog(path).read_all())
    return events


def _best_observed_rows(arm_events: dict[str, list[EventRecord]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for arm_id, events in arm_events.items():
        by_instance: dict[str, list[EventRecord]] = {}
        for event in events:
            by_instance.setdefault(event.instance_id, []).append(event)
        for instance_id, instance_events in sorted(by_instance.items()):
            best = _best_for_instance(instance_events)
            final_score = _last_score(instance_events)
            rows.append(
                {
                    "arm_id": arm_id,
                    "instance_id": instance_id,
                    "best_stage": best["stage"],
                    "best_score": best["score"],
                    "best_candidate_id": best["candidate_id"],
                    "best_hypothesis_id": best["hypothesis_id"],
                    "best_patch_applies": best["signals"].get("patch_applies", False),
                    "best_compile_success": best["signals"].get("compile_success", False),
                    "best_test_success": best["signals"].get("test_success", False),
                    "best_class_version_ok": best["signals"].get("class_version_ok", False),
                    "best_official_success": best["signals"].get("official_success", False),
                    "best_strict_success": best["signals"].get("strict_success", False),
                    "final_strict_success": bool(final_score.get("strict_success", False)),
                }
            )
    return rows


def _best_for_instance(events: Sequence[EventRecord]) -> dict[str, Any]:
    best = {
        "score": 0,
        "stage": "none",
        "candidate_id": None,
        "hypothesis_id": None,
        "signals": {},
    }
    for event in events:
        if event.event_type != "validation.completed":
            continue
        validation = event.payload.get("validation") or {}
        signals = dict(validation.get("signals") or {})
        score, stage = _stage_score(signals, validation)
        if score > int(best["score"]):
            best = {
                "score": score,
                "stage": stage,
                "candidate_id": validation.get("candidate_id"),
                "hypothesis_id": event.hypothesis_id,
                "signals": signals,
            }
    score = _last_score(events)
    if score:
        signals = dict(score.get("metrics") or {})
        strict = bool(score.get("strict_success") or signals.get("strict_success"))
        final_score, final_stage = _stage_score(signals, {"summary": "score"})
        if strict and final_score < 100:
            final_score, final_stage = 100, "strict_success"
        if final_score > int(best["score"]):
            best = {
                "score": final_score,
                "stage": final_stage,
                "candidate_id": score.get("candidate_id"),
                "hypothesis_id": score.get("hypothesis_id"),
                "signals": signals,
            }
    return best


def _last_score(events: Sequence[EventRecord]) -> dict[str, Any]:
    for event in reversed(events):
        if event.event_type == "score.completed":
            score = dict(event.payload.get("score") or {})
            score["strict_success"] = bool(event.payload.get("strict_success"))
            score["hypothesis_id"] = event.hypothesis_id
            return score
    return {}


def _stage_score(signals: dict[str, Any], validation: dict[str, Any]) -> tuple[int, str]:
    haystack = "\n".join(
        [
            str(validation.get("summary") or ""),
            *[str(item) for item in validation.get("errors") or []],
        ]
    )
    if "replacement_count_too_low" in haystack:
        return -20, "replacement_error"
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


def _pairwise_best_observed(best_rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    by_instance_arm = {
        (str(row["instance_id"]), str(row["arm_id"])): row for row in best_rows
    }
    instance_ids = sorted({str(row["instance_id"]) for row in best_rows})
    pairs = _pairwise_pairs({str(row["arm_id"]) for row in best_rows})
    rows: list[dict[str, Any]] = []
    for instance_id in instance_ids:
        for treatment, control in pairs:
            t = by_instance_arm.get((instance_id, treatment))
            c = by_instance_arm.get((instance_id, control))
            if not t or not c:
                continue
            delta = int(t["best_score"]) - int(c["best_score"])
            rows.append(
                {
                    "instance_id": instance_id,
                    "treatment_arm": treatment,
                    "control_arm": control,
                    "treatment_best_stage": t["best_stage"],
                    "control_best_stage": c["best_stage"],
                    "treatment_best_score": t["best_score"],
                    "control_best_score": c["best_score"],
                    "delta": delta,
                    "relation": "better" if delta > 0 else ("worse" if delta < 0 else "same"),
                }
            )
    return rows


def _tool_trace_rows(arm_events: dict[str, list[EventRecord]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for arm_id, events in arm_events.items():
        pending: dict[tuple[str, int], dict[str, Any]] = {}
        local_view_by_instance: dict[str, dict[str, Any]] = {}
        for event in events:
            if event.event_type == "agent.local_view.created":
                local_view_by_instance[event.instance_id] = dict(
                    event.payload.get("local_view") or {}
                )
            elif event.event_type == "agent.tool_call.requested":
                call = event.payload.get("tool_call") or {}
                context = event.payload.get("tool_recommendation_context") or {}
                if not context:
                    local_view = local_view_by_instance.get(event.instance_id) or {}
                    annotations = {
                        str(name): dict(annotation or {})
                        for name, annotation in (
                            local_view.get("tool_annotations") or {}
                        ).items()
                    }
                    selected = str(call.get("tool_name") or "")
                    if not annotations and event.payload.get("tool_annotation"):
                        annotations = {
                            selected: dict(event.payload.get("tool_annotation") or {})
                        }
                    context = tool_recommendation_context_from_annotations(
                        annotations=annotations,
                        selected_tool=selected,
                        forbidden_tools=(local_view.get("forbidden_tools") or {}).keys(),
                    )
                key = (event.instance_id, event.sequence)
                pending[key] = {
                    "arm_id": arm_id,
                    "instance_id": event.instance_id,
                    "sequence": event.sequence,
                    "tool_name": call.get("tool_name"),
                    "rationale": call.get("rationale", ""),
                    "selected_recommendation": context.get("selected_recommendation"),
                    "selected_is_inhibited": context.get("selected_is_inhibited", False),
                    "ignored_strongly_supported_tools": "|".join(
                        context.get("ignored_strongly_supported_tools") or []
                    ),
                    "status": "",
                    "summary": "",
                    "workspace_mutated": False,
                    "candidate_created": False,
                }
            elif event.event_type == "tool.executed":
                call = event.payload.get("tool_call") or {}
                result = event.payload.get("result") or {}
                row = None
                for key in sorted(pending, key=lambda item: item[1], reverse=True):
                    if key[0] == event.instance_id and not pending[key]["status"]:
                        row = pending[key]
                        break
                if row is None:
                    row = {
                        "arm_id": arm_id,
                        "instance_id": event.instance_id,
                        "sequence": event.sequence,
                        "tool_name": call.get("tool_name"),
                        "rationale": call.get("rationale", ""),
                        "selected_recommendation": "",
                        "selected_is_inhibited": False,
                        "ignored_strongly_supported_tools": "",
                    }
                row.update(
                    {
                        "status": result.get("status", ""),
                        "summary": result.get("summary", ""),
                        "workspace_mutated": bool(result.get("workspace_mutated")),
                        "candidate_created": bool(result.get("candidate_created")),
                    }
                )
                rows.append(row)
    return rows


def _medium_effect_rows(
    arm_events: dict[str, list[EventRecord]],
    pairwise_rows: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    treatment_arm, control_arm = _medium_pair_for(set(arm_events))
    deltas = {
        row["instance_id"]: row
        for row in pairwise_rows
        if row["treatment_arm"] == treatment_arm and row["control_arm"] == control_arm
    }
    rows: list[dict[str, Any]] = []
    events = arm_events.get(treatment_arm, [])
    by_instance: dict[str, list[EventRecord]] = {}
    for event in events:
        by_instance.setdefault(event.instance_id, []).append(event)
    for instance_id, instance_events in sorted(by_instance.items()):
        metrics = summarize_tool_recommendation_metrics(instance_events).to_dict()
        delta = deltas.get(instance_id, {})
        rows.append(
            {
                "instance_id": instance_id,
                "medium_pheromone_reads": sum(
                    1 for event in instance_events if event.event_type == "pheromone.read"
                ),
                "local_view_created": sum(
                    1
                    for event in instance_events
                    if event.event_type == "agent.local_view.created"
                ),
                "best_delta_vs_s2": delta.get("delta", ""),
                "relation_vs_s2": delta.get("relation", ""),
                **metrics,
            }
        )
    return rows


def _readiness_report(
    *,
    campaign_root: Path,
    arm_ids: Sequence[str],
    arm_events: dict[str, list[EventRecord]],
    pairwise_rows: Sequence[dict[str, Any]],
    tool_trace_rows: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    manifests = {
        arm: _read_manifest(campaign_root / arm / "manifest.json") for arm in arm_ids
    }
    treatment_arm, control_arm = _medium_pair_for(set(arm_ids))
    s2_tools = tuple(
        (manifests.get(control_arm) or {}).get("extras", {}).get("v12_tool_registry")
        or (manifests.get(control_arm) or {}).get("extras", {}).get("sd_feedback_readonly_tool_registry")
        or ()
    )
    v12_tools = tuple(
        (manifests.get(treatment_arm) or {}).get("extras", {}).get("v12_tool_registry")
        or (manifests.get(treatment_arm) or {}).get("extras", {}).get("sd_feedback_readonly_tool_registry")
        or ()
    )
    medium_created = _run_completed_sum(
        arm_events.get(treatment_arm, []),
        "medium_created_patch_count",
    )
    suggest_applied = sum(
        _run_completed_sum(events, "suggest_tool_applied_patch_count")
        for events in arm_events.values()
    )
    v12_vs_s2 = [
        row
        for row in pairwise_rows
        if row["treatment_arm"] == treatment_arm and row["control_arm"] == control_arm
    ]
    readiness = {
        "schema_version": "v12.readiness_report.v2",
        "campaign_root": str(campaign_root),
        "arm_ids": list(arm_ids),
        "arms_present": {
            arm: bool((campaign_root / arm / "manifest.json").exists())
            for arm in arm_ids
        },
        "gates": {
            "s2_v12_same_tool_registry": bool(s2_tools and s2_tools == v12_tools),
            "medium_created_patch_count_zero": medium_created == 0,
            "suggest_tool_applied_patch_count_zero": suggest_applied == 0,
            "tool_traces_present": bool(tool_trace_rows),
        },
        "metrics": {
            "medium_created_patch_count": int(medium_created),
            "suggest_tool_applied_patch_count": int(suggest_applied),
            "v12_better_than_s2_count": sum(
                1 for row in v12_vs_s2 if int(row.get("delta") or 0) > 0
            ),
            "v12_worse_than_s2_count": sum(
                1 for row in v12_vs_s2 if int(row.get("delta") or 0) < 0
            ),
            "v12_same_as_s2_count": sum(
                1 for row in v12_vs_s2 if int(row.get("delta") or 0) == 0
            ),
            "tool_call_total": len(tool_trace_rows),
        },
    }
    readiness["ready_for_targeted_campaign_analysis"] = all(readiness["gates"].values())
    return readiness


def _detect_arm_ids(root: Path) -> tuple[str, ...]:
    v12_4_present = [arm for arm in ARM_IDS_V12_4 if (root / arm / "manifest.json").exists()]
    if v12_4_present:
        return tuple(v12_4_present)
    v12_3_present = [arm for arm in ARM_IDS_V12_3 if (root / arm / "manifest.json").exists()]
    if v12_3_present:
        return tuple(v12_3_present)
    return tuple(arm for arm in ARM_IDS if (root / arm).exists())


def _pairwise_pairs(arm_ids: set[str]) -> tuple[tuple[str, str], ...]:
    if {"S2_sd_feedback_readonly_tools", "V12_stigmergic_sd_feedback"}.issubset(arm_ids):
        return (
            ("V12_stigmergic_sd_feedback", "S2_sd_feedback_readonly_tools"),
            ("V12_stigmergic_sd_feedback", "S1_sd_feedback_exact"),
            ("S2_sd_feedback_readonly_tools", "S1_sd_feedback_exact"),
        )
    return (
        ("V12_stigmergic_tool_agent", "S2_tool_feedback_agent"),
        ("V12_stigmergic_tool_agent", "S1_sd_feedback_like"),
        ("S2_tool_feedback_agent", "S1_sd_feedback_like"),
    )


def _medium_pair_for(arm_ids: set[str]) -> tuple[str, str]:
    if {"S2_sd_feedback_readonly_tools", "V12_stigmergic_sd_feedback"}.issubset(arm_ids):
        return "V12_stigmergic_sd_feedback", "S2_sd_feedback_readonly_tools"
    return "V12_stigmergic_tool_agent", "S2_tool_feedback_agent"


def _read_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _run_completed_sum(events: Sequence[EventRecord], key: str) -> int:
    return sum(
        int(event.payload.get(key) or 0)
        for event in events
        if event.event_type == "run.completed"
    )


def _write_csv(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    rows = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted({key for row in rows for key in row})
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _csv_value(row.get(key)) for key in fieldnames})


def _csv_value(value: Any) -> Any:
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="scripts.v12.audit_v12_campaign",
        description=__doc__,
    )
    parser.add_argument("--campaign-root", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = audit_v12_campaign(args.campaign_root)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())


__all__ = [
    "ARM_IDS",
    "ARM_IDS_V12_3",
    "ARM_IDS_V12_4",
    "audit_v12_campaign",
    "build_parser",
    "main",
]
