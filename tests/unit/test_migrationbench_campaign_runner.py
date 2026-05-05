from __future__ import annotations

import json
from pathlib import Path

from scripts.aggregate_migrationbench_comparison import mcnemar_exact_p
from scripts.run_migrationbench_framework_benchmark import (
    _run_exporter_command,
    build_manifest,
    summarize,
)


def test_summary_uses_manifest_denominator_for_missing_outputs(tmp_path: Path) -> None:
    manifest = {
        "framework": "x",
        "provider": "deepseek",
        "model": "deepseek-v4-flash",
        "seed": 42,
        "requested_instances": 2,
        "instances": [
            {"instance_id": "a", "target_java": 17, "migration_mode": "minimal"},
            {"instance_id": "b", "target_java": 17, "migration_mode": "minimal"},
        ],
    }
    rows = [
        {
            "instance_id": "a",
            "strict_success": True,
            "artifact_delivered": True,
            "patch_applies": True,
            "official_success": True,
            "failure_reason": "ok",
        }
    ]
    summary = summarize(manifest, rows, tmp_path)
    assert summary["requested_instances"] == 2
    assert summary["strict_success_rate"] == 0.5
    assert summary["failure_reasons"]["missing_output"] == 1


def test_mcnemar_exact_p_handles_no_discordance() -> None:
    assert mcnemar_exact_p(0, 0) == 1.0
    assert 0.0 <= mcnemar_exact_p(3, 0) <= 1.0


def test_exporter_command_timeout_kills_process_group() -> None:
    returncode, stdout, stderr, timed_out = _run_exporter_command(
        ["python", "-c", "import time; print('start', flush=True); time.sleep(30)"],
        timeout_seconds=0.2,
    )
    assert timed_out is True
    assert returncode == 124
    assert "start" in stdout
    assert "timed out" in stderr


def test_manifest_records_query_timeout() -> None:
    class Args:
        framework = "solo_direct"
        subset = Path("subset.jsonl")
        seed = 42
        config = Path("config.yaml")
        migrationbench_root = Path("external/MigrationBench")
        workspace_root = Path("workspaces/migrationbench")
        skip_official_eval = False
        query_timeout_seconds = 1800.0

    manifest = build_manifest(
        Args(),
        [{"instance_id": "a", "target_java": 17, "migration_mode": "minimal"}],
        {"llm": {"provider": "deepseek", "model": "deepseek-v4-flash"}},
    )
    assert manifest["query_timeout_seconds"] == 1800.0
