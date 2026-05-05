from __future__ import annotations

import json
from pathlib import Path

import pytest

from core_v10.event_log import JsonlEventLog
from scripts.bench.telemetry import (
    build_summary,
    read_events,
    replay_summary_from_dir,
    write_summary,
)


def _seed_events(path: Path, run_id: str, instance_id: str, *, strict: bool) -> None:
    log = JsonlEventLog(path)
    log.append(
        run_id=run_id,
        instance_id=instance_id,
        event_type="run.started",
        actor="strategy_runner",
        payload={"strategy": "agentless_basic"},
    )
    log.append(
        run_id=run_id,
        instance_id=instance_id,
        event_type="score.completed",
        actor="adapter",
        hypothesis_id="h1",
        payload={
            "score": {
                "metrics": {
                    "patch_delivered": True,
                    "patch_applies": True,
                    "compile_success": True,
                    "test_success": True,
                    "class_version_ok": True,
                    "official_success": strict,
                    "strict_success": strict,
                }
            },
            "strict_success": strict,
        },
    )
    log.append(
        run_id=run_id,
        instance_id=instance_id,
        event_type="run.completed",
        actor="strategy_runner",
        payload={
            "strategy": "agentless_basic",
            "stop_reason": "strict_success" if strict else "artifact_contract_failed",
            "candidate_count": 1,
            "selected_hypothesis_id": "h1",
        },
    )


def test_build_summary_counts_strict_success(tmp_path: Path) -> None:
    e_a = tmp_path / "events" / "a" / "eventlog.jsonl"
    e_b = tmp_path / "events" / "b" / "eventlog.jsonl"
    e_a.parent.mkdir(parents=True)
    e_b.parent.mkdir(parents=True)
    _seed_events(e_a, run_id="run:a", instance_id="a", strict=True)
    _seed_events(e_b, run_id="run:b", instance_id="b", strict=False)

    events = {
        "a": JsonlEventLog(e_a).read_all(),
        "b": JsonlEventLog(e_b).read_all(),
    }
    summary = build_summary(
        campaign_id="c1",
        adapter_name="toy",
        strategy_name="agentless_basic",
        instance_ids=["a", "b"],
        events_by_instance=events,
    )
    assert summary.instance_count == 2
    assert summary.strict_success_count == 1
    assert summary.by_signal["strict_success"] == 1
    assert summary.by_signal["compile_success"] == 2
    assert summary.instances[0].strict_success is True
    assert summary.instances[1].stop_reason == "artifact_contract_failed"


def test_build_summary_counts_partial_validations_without_score(tmp_path: Path) -> None:
    event_path = tmp_path / "events" / "partial" / "eventlog.jsonl"
    event_path.parent.mkdir(parents=True)
    log = JsonlEventLog(event_path)
    log.append(
        run_id="run:partial",
        instance_id="partial",
        event_type="run.started",
        actor="strategy_runner",
        payload={"strategy": "branching_repair"},
    )
    log.append(
        run_id="run:partial",
        instance_id="partial",
        event_type="candidate.applied",
        actor="adapter",
        hypothesis_id="h1",
        payload={"apply_result": {"applied": True}},
    )
    log.append(
        run_id="run:partial",
        instance_id="partial",
        event_type="validation.completed",
        actor="verifier",
        hypothesis_id="h1",
        payload={
            "validation": {
                "status": "partial",
                "signals": {
                    "compile_success": True,
                    "test_success": False,
                    "strict_success": False,
                },
                "summary": "test_failure",
            }
        },
    )
    log.append(
        run_id="run:partial",
        instance_id="partial",
        event_type="run.completed",
        actor="strategy_runner",
        payload={"strategy": "branching_repair", "stop_reason": "repair_exhausted"},
    )

    summary = build_summary(
        campaign_id="c1",
        adapter_name="migrationbench",
        strategy_name="branching_repair",
        instance_ids=["partial"],
        events_by_instance={"partial": log.read_all()},
    )

    assert summary.strict_success_count == 0
    assert summary.apply_ok_total == 1
    assert summary.validation_completed_total == 1
    assert summary.validation_partial_total == 1
    assert summary.instances[0].validation_partial_count == 1


def test_replay_summary_from_dir_matches_live_summary(tmp_path: Path) -> None:
    e_a = tmp_path / "events" / "a" / "eventlog.jsonl"
    e_a.parent.mkdir(parents=True)
    _seed_events(e_a, run_id="run:a", instance_id="a", strict=True)

    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "campaign_id": "c1",
                "adapter_name": "toy",
                "strategy_name": "agentless_basic",
                "subset_path": "synthetic",
                "instance_ids": ["a"],
                "out_dir": str(tmp_path),
                "seed": 42,
                "started_at": "2026-05-04T00:00:00+00:00",
                "extras": {},
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    live = build_summary(
        campaign_id="c1",
        adapter_name="toy",
        strategy_name="agentless_basic",
        instance_ids=["a"],
        events_by_instance={"a": JsonlEventLog(e_a).read_all()},
    )
    write_summary(tmp_path, live)

    replay = replay_summary_from_dir(tmp_path)
    assert replay.to_dict() == live.to_dict()


def test_read_events_returns_empty_when_path_missing(tmp_path: Path) -> None:
    assert read_events(tmp_path, "missing-instance") == []


def test_replay_summary_requires_manifest(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        replay_summary_from_dir(tmp_path)
