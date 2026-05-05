from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.bench.artifacts import (
    Manifest,
    RunRow,
    load_subset,
    read_runs_jsonl,
    write_manifest,
    write_runs_jsonl,
)


def test_load_subset_skips_blank_and_comment_lines(tmp_path: Path) -> None:
    subset = tmp_path / "s.jsonl"
    subset.write_text(
        '\n# comment\n{"instance_id":"a"}\n  \n{"instance_id":"b"}\n',
        encoding="utf-8",
    )
    rows = load_subset(subset)
    assert [r["instance_id"] for r in rows] == ["a", "b"]


def test_load_subset_missing_path_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_subset(tmp_path / "missing.jsonl")


def test_write_manifest_serializes_payload(tmp_path: Path) -> None:
    manifest = Manifest(
        campaign_id="c1",
        adapter_name="toy",
        strategy_name="agentless_basic",
        subset_path="s.jsonl",
        instance_ids=["a", "b"],
        out_dir=str(tmp_path),
    )
    target = write_manifest(tmp_path, manifest)
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["campaign_id"] == "c1"
    assert payload["instance_ids"] == ["a", "b"]
    assert payload["adapter_name"] == "toy"


def test_runs_jsonl_round_trip(tmp_path: Path) -> None:
    rows = [
        RunRow(
            instance_id="a",
            strategy_name="agentless_basic",
            stop_reason="strict_success",
            strict_success=True,
            selected_hypothesis_id="h1",
            candidate_count=1,
            signals={"strict_success": True},
            artifact_paths={"answer.txt": "/tmp/answer.txt"},
        ),
        RunRow(
            instance_id="b",
            strategy_name="agentless_basic",
            stop_reason="all_candidates_invalid",
            strict_success=False,
            selected_hypothesis_id=None,
            candidate_count=1,
            signals={},
            artifact_paths={},
        ),
    ]
    write_runs_jsonl(tmp_path, rows)
    read_back = read_runs_jsonl(tmp_path)
    assert read_back == rows
