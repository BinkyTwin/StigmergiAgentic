"""Unit tests for TravelPlanner benchmark runner helpers."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess

import scripts.run_travelplanner_framework_benchmark as benchmark_runner
from scripts.run_travelplanner_framework_benchmark import (
    augment_payload,
    build_benchmark_summary,
    build_query_indices,
    execute_query_export,
    infer_failure_reason,
)


def test_infer_failure_reason_prefers_nested_evaluation_value() -> None:
    payload = {
        "status": "ok",
        "evaluation": {
            "failure_reason": "empty_plan_after_max_attempts",
        },
        "summary": {
            "stop_reason": "all_terminal",
        },
    }

    assert infer_failure_reason(payload) == "empty_plan_after_max_attempts"


def test_augment_payload_promotes_failure_reason_to_top_level() -> None:
    payload = augment_payload(
        framework="stigmergiagentic",
        payload={
            "status": "ok",
            "evaluation": {"failure_reason": "schema_parse_failed"},
            "summary": {"stop_reason": "idle_cycles"},
        },
        runtime_seconds=1.25,
        seed=42,
    )

    assert payload["failure_reason"] == "schema_parse_failed"
    assert payload["summary"]["failure_reason"] == "schema_parse_failed"


def test_build_benchmark_summary_counts_failure_reason_distribution() -> None:
    summary = build_benchmark_summary(
        framework="stigmergiagentic",
        run_tag_dir=Path("/tmp/fake-run"),
        runs=[
            {
                "final_pass": False,
                "failure_reason": "empty_plan_after_max_attempts",
                "summary": {
                    "tokens_used": 10,
                    "cost_used": 0.01,
                    "runtime_seconds": 1.0,
                    "coordination_overhead": 2,
                },
            },
            {
                "final_pass": True,
                "failure_reason": "ok",
                "summary": {
                    "tokens_used": 12,
                    "cost_used": 0.02,
                    "runtime_seconds": 1.5,
                    "coordination_overhead": 3,
                },
            },
        ],
        queries_requested=2,
        runs_json=Path("/tmp/fake-run/runs.json"),
        official_eval_json=Path("/tmp/fake-run/official_eval.json"),
        total_runtime_seconds=3.0,
    )

    assert summary["failed_queries"] == 1
    assert summary["queries_requested"] == 2
    assert summary["queries_succeeded"] == 1
    assert summary["success_rate"] == 0.5
    assert summary["failure_reasons"] == {
        "empty_plan_after_max_attempts": 1,
        "ok": 1,
    }
    assert summary["official_eval_semantics"]["missing_query_prediction"] == "treated_as_empty_plan"


def test_execute_query_export_returns_failed_payload_on_nonzero_exit(
    tmp_path: Path,
    monkeypatch,
) -> None:
    args = argparse.Namespace(seed=42, query_timeout_seconds=None)
    log_path = tmp_path / "query_000.log"

    def fake_run(command, **_kwargs) -> subprocess.CompletedProcess[str]:  # type: ignore[no-untyped-def]
        return subprocess.CompletedProcess(
            args=command,
            returncode=7,
            stdout="partial stdout\n",
            stderr="boom on stderr\ntrace\n",
        )

    monkeypatch.setattr(benchmark_runner.subprocess, "run", fake_run)

    payload = execute_query_export(
        framework="solo_direct",
        args=args,
        query_idx=0,
        command=["python", "fake_exporter.py"],
        log_path=log_path,
    )

    assert payload["status"] == "failed"
    assert payload["failure_reason"] == "returncode_nonzero"
    assert payload["returncode"] == 7
    assert "boom on stderr" in payload["stderr_tail"]
    assert payload["summary"]["run_status"] == "failed"


def test_main_continues_after_invalid_json_and_writes_failure_checkpoint(
    tmp_path: Path,
    monkeypatch,
) -> None:
    out_dir = tmp_path / "benchmark"

    def fake_run(command, **kwargs):  # type: ignore[no-untyped-def]
        del kwargs
        query_idx = int(command[command.index("--query-idx") + 1])
        if query_idx == 0:
            return subprocess.CompletedProcess(
                args=command,
                returncode=0,
                stdout="not json at all\n",
                stderr="truncated output\n",
            )
        return subprocess.CompletedProcess(
            args=command,
            returncode=0,
            stdout='noise\n{"query_idx": 1, "final_pass": true, "summary": {"tokens_used": 12}}\n',
            stderr="",
        )

    def fake_run_official_eval(
        *,
        runs_json: Path,
        database_root: str,
        split: str,
        official_eval_json: Path,
        official_eval_log: Path,
        start_index: int | None = None,
        end_index: int | None = None,
    ) -> None:
        del runs_json, database_root, split, start_index, end_index
        official_eval_json.write_text('{"scores": {"final_pass_rate": 0.5}}\n', encoding="utf-8")
        official_eval_log.write_text("official ok\n", encoding="utf-8")

    monkeypatch.setattr(benchmark_runner.subprocess, "run", fake_run)
    monkeypatch.setattr(benchmark_runner, "run_official_eval", fake_run_official_eval)

    exit_code = benchmark_runner.main(
        [
            "--framework",
            "solo_direct",
            "--out-dir",
            str(out_dir),
            "--max-queries",
            "2",
            "--seed",
            "42",
        ]
    )

    assert exit_code == 0

    failed_payload = json.loads((out_dir / "queries" / "query_000.json").read_text(encoding="utf-8"))
    success_payload = json.loads((out_dir / "queries" / "query_001.json").read_text(encoding="utf-8"))
    runs_payload = json.loads((out_dir / "runs.json").read_text(encoding="utf-8"))
    summary = json.loads((out_dir / "benchmark_summary.json").read_text(encoding="utf-8"))

    assert failed_payload["status"] == "failed"
    assert failed_payload["failure_reason"] == "exporter_crash"
    assert "not json at all" in failed_payload["stdout_tail"]
    assert success_payload["failure_reason"] == "ok"
    assert len(runs_payload["runs"]) == 2
    assert summary["queries_requested"] == 2
    assert summary["queries_succeeded"] == 1
    assert summary["failed_queries"] == 1
    assert summary["failure_reasons"] == {
        "exporter_crash": 1,
        "ok": 1,
    }


def test_build_query_indices_supports_inclusive_start_end_aliases() -> None:
    args = argparse.Namespace(
        start=0,
        end=2,
        start_index=0,
        end_index=None,
        max_queries=180,
    )

    assert build_query_indices(args) == [0, 1, 2]


def test_build_query_indices_keeps_existing_end_index_semantics() -> None:
    args = argparse.Namespace(
        start=None,
        end=None,
        start_index=3,
        end_index=5,
        max_queries=180,
    )

    assert build_query_indices(args) == [3, 4]
