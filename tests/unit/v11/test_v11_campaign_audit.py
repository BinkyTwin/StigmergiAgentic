"""Tests for V11 campaign audit artifacts."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from scripts.v11.audit_v11_campaign import audit_campaign


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _append_event(path: Path, *, sequence: int, event_type: str, payload: dict, hypothesis_id: str | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "event_id": f"evt_{sequence}",
        "sequence": sequence,
        "run_id": "run-1",
        "instance_id": path.parent.name,
        "timestamp": "2026-05-06T00:00:00+00:00",
        "type": event_type,
        "actor": "test",
        "hypothesis_id": hypothesis_id,
        "payload": payload,
        "cost": {},
        "links": {},
    }
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event, sort_keys=True) + "\n")


def _summary(root: Path, arm: str, *, strict: bool) -> None:
    _write_json(
        root / arm / "summary.json",
        {
            "instances": [
                {
                    "instance_id": "repo__demo",
                    "strict_success": strict,
                    "selected_hypothesis_id": "selected",
                    "stop_reason": "repair_exhausted",
                }
            ]
        },
    )


def test_audit_campaign_writes_pairwise_operator_and_llm_artifacts(tmp_path: Path) -> None:
    root = tmp_path / "campaign"
    arms = ["B2_branching_repair", "B5_stigmergic_scheduler", "B6_operator_search"]
    _write_json(root / "comparison.json", {"arms": [{"arm_id": arm} for arm in arms]})
    for arm in arms:
        _summary(root, arm, strict=(arm == "B6_operator_search"))

    for arm, stage in (
        ("B2_branching_repair", "compile_success"),
        ("B5_stigmergic_scheduler", "test_success"),
        ("B6_operator_search", "official_success"),
    ):
        eventlog = root / arm / "events" / "repo__demo" / "eventlog.jsonl"
        _append_event(
            eventlog,
            sequence=1,
            event_type="validation.completed",
            hypothesis_id="parent",
            payload={"validation": {"candidate_id": "parent", "signals": {stage: True}}},
        )
        _append_event(
            eventlog,
            sequence=2,
            event_type="run.completed",
            payload={"best_observed": {"best_stage": stage, "best_funnel_score": 80}},
        )

    b6_log = root / "B6_operator_search" / "events" / "repo__demo" / "eventlog.jsonl"
    _append_event(
        b6_log,
        sequence=3,
        event_type="affordance.created",
        payload={
            "affordance": {
                "affordance_id": "aff-1",
                "action_type": "upgrade_lombok_for_target_java",
                "expected_worker_kind": "maven_compiler_operator",
            }
        },
    )
    _append_event(
        b6_log,
        sequence=4,
        event_type="feedback.created",
        hypothesis_id="parent",
        payload={"feedback": {"candidate_id": "parent", "failure_type": "compile_error", "evidence": ["lombok IllegalAccessError"]}},
    )
    _append_event(
        b6_log,
        sequence=5,
        event_type="candidate.created",
        hypothesis_id="op",
        payload={
            "candidate": {
                "candidate_id": "op",
                "parent_id": "parent",
                "payload": {"parent_branch_id": "c1"},
            }
        },
    )
    _append_event(
        b6_log,
        sequence=6,
        event_type="validation.completed",
        hypothesis_id="op",
        payload={"validation": {"candidate_id": "op", "signals": {"official_success": True}}},
    )
    invocation = {
        "operator_id": "MavenUpgradeLombokForTargetJava",
        "source_affordance_id": "aff-1",
        "params": {"failure_type": "compile_error", "action_type": "upgrade_lombok_for_target_java"},
        "target_files": ["pom.xml"],
    }
    _append_event(
        b6_log,
        sequence=7,
        event_type="operator.applied",
        hypothesis_id="op",
        payload={"candidate_id": "op", "applied": True, "operator_invocation": invocation},
    )
    _append_event(
        b6_log,
        sequence=8,
        event_type="operator.unavailable",
        payload={
            "affordance_id": "aff-1",
            "action_type": "upgrade_lombok_for_target_java",
            "worker_id": "maven_compiler_operator",
            "reason": "no_operator_candidate",
            "fallback_policy": "guarded_only",
        },
    )
    _append_event(
        b6_log,
        sequence=9,
        event_type="run.completed",
        payload={"best_observed": {"best_stage": "official_success", "best_funnel_score": 80}},
    )
    trace_dir = root / "B6_operator_search" / "llm_traces"
    _append_trace = {
        "instance_id": "repo__demo",
        "call_kind": "initial",
        "slot_index": 0,
        "candidate_id": "c1",
        "candidate_emitted": True,
        "parse_ok": True,
        "normalized_edit_count": 1,
        "normalized_edits": [{"path": "pom.xml"}],
        "provider": "deepseek",
        "model": "deepseek-chat",
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }
    trace_dir.mkdir(parents=True, exist_ok=True)
    (trace_dir / "calls.jsonl").write_text(json.dumps(_append_trace) + "\n", encoding="utf-8")

    manifest = audit_campaign(root)

    assert manifest["pairwise_rows"] == 3
    assert manifest["operator_applied_rows"] == 1
    assert manifest["operator_unavailable_rows"] == 1
    assert manifest["llm_trace_calls"] == 1

    with (root / "audits" / "pairwise_best_observed.csv").open(encoding="utf-8") as stream:
        pairwise = list(csv.DictReader(stream))
    assert any(row["comparison"] == "B6_operator_search_vs_B5_stigmergic_scheduler" and row["relation"] == "better" for row in pairwise)

    with (root / "audits" / "operator_unavailable_by_failure_family.csv").open(encoding="utf-8") as stream:
        unavailable = list(csv.DictReader(stream))
    assert unavailable[0]["failure_family"] == "lombok_or_javac_internal_api"
