"""Unit tests for metrics collection and export."""

from __future__ import annotations

import json
from pathlib import Path

from metrics.collector import MetricsCollector
from metrics.export import write_manifest_json, write_summary_json, write_ticks_csv


def test_metrics_collector_retry_resolution_and_summary(tmp_path: Path) -> None:
    audit_log = tmp_path / "audit_log.jsonl"
    audit_log.write_text(
        json.dumps(
            {
                "timestamp": "2026-02-12T10:00:00Z",
                "agent": "scout",
                "pheromone_type": "tasks",
                "file_key": "module.py",
                "action": "write",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    collector = MetricsCollector(audit_log_path=audit_log)

    collector.record_tick(
        tick=0,
        agents_acted={"scout": True, "transformer": False, "tester": False, "validator": False},
        status_entries={"module.py": {"status": "retry"}},
        total_tokens=10,
    )
    collector.record_tick(
        tick=1,
        agents_acted={"scout": False, "transformer": True, "tester": True, "validator": True},
        status_entries={"module.py": {"status": "validated"}},
        total_tokens=20,
    )

    summary = collector.build_summary(stop_reason="all_terminal")
    assert summary["retry_resolution_rate"] == 1.0
    assert summary["success_rate"] == 1.0
    assert summary["stop_reason"] == "all_terminal"


def test_metrics_collector_starvation_and_audit_completeness(tmp_path: Path) -> None:
    audit_log = tmp_path / "audit_log.jsonl"
    audit_log.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "timestamp": "2026-02-12T10:00:00Z",
                        "agent": "scout",
                        "pheromone_type": "tasks",
                        "file_key": "a.py",
                        "action": "write",
                    }
                ),
                json.dumps({"timestamp": "2026-02-12T10:00:01Z", "agent": "scout"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    collector = MetricsCollector(audit_log_path=audit_log, starvation_threshold=2)

    for tick in range(4):
        collector.record_tick(
            tick=tick,
            agents_acted={"scout": False, "transformer": False, "tester": False, "validator": False},
            status_entries={"a.py": {"status": "pending"}},
            total_tokens=0,
        )

    last = collector.tick_rows[-1]
    assert last["starvation_count"] == 1
    assert last["audit_completeness"] == 0.5


def test_metrics_export_writes_expected_files(tmp_path: Path) -> None:
    ticks_path = tmp_path / "run_x_ticks.csv"
    summary_path = tmp_path / "run_x_summary.json"
    manifest_path = tmp_path / "run_x_manifest.json"

    write_ticks_csv(
        path=ticks_path,
        tick_rows=[
            {
                "tick": 0,
                "any_agent_acted": True,
                "acted_scout": True,
                "acted_transformer": False,
                "acted_tester": False,
                "acted_validator": False,
                "files_total": 1,
                "files_migrated": 1,
                "files_validated": 0,
                "files_failed": 0,
                "files_needs_review": 0,
                "total_tokens": 12,
                "total_ticks": 1,
                "tokens_per_file": 12.0,
                "success_rate": 0.0,
                "rollback_rate": 0.0,
                "human_escalation_rate": 0.0,
                "retry_resolution_rate": 0.0,
                "starvation_count": 0,
                "audit_completeness": 1.0,
            }
        ],
    )
    write_summary_json(path=summary_path, summary={"stop_reason": "idle_cycles"})
    write_manifest_json(path=manifest_path, manifest={"run_id": "x"})

    assert ticks_path.exists()
    assert summary_path.exists()
    assert manifest_path.exists()
