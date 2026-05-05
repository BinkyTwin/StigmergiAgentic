from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.bench.artifacts import read_runs_jsonl
from scripts.bench.harness import (
    BenchHarness,
    HarnessOptions,
    default_registry,
    main,
)
from scripts.bench.telemetry import replay_summary_from_dir


def _write_subset(path: Path, instances: list[dict[str, str]]) -> None:
    path.write_text(
        "\n".join(json.dumps(inst) for inst in instances) + "\n",
        encoding="utf-8",
    )


def test_harness_runs_toy_adapter_end_to_end_strict_success(tmp_path: Path) -> None:
    subset = tmp_path / "subset.jsonl"
    _write_subset(
        subset,
        [
            {"instance_id": "a", "expected": "hello"},
            {"instance_id": "b", "expected": "world"},
        ],
    )
    out_dir = tmp_path / "out"
    options = HarnessOptions(
        adapter_name="toy",
        strategy_name="agentless_basic",
        subset_path=subset,
        out_dir=out_dir,
        extras={"out_dir": str(out_dir)},
    )
    summary = BenchHarness(options, default_registry()).run()

    assert summary.instance_count == 2
    assert summary.strict_success_count == 2
    assert (out_dir / "manifest.json").exists()
    assert (out_dir / "runs.jsonl").exists()
    assert (out_dir / "summary.json").exists()
    assert (out_dir / "events" / "a" / "eventlog.jsonl").exists()
    assert (out_dir / "hypotheses" / "a" / "graph.json").exists()

    rows = read_runs_jsonl(out_dir)
    assert {row.instance_id for row in rows} == {"a", "b"}
    assert all(row.strict_success for row in rows)


def test_harness_summary_round_trips_through_replay(tmp_path: Path) -> None:
    subset = tmp_path / "subset.jsonl"
    _write_subset(subset, [{"instance_id": "a", "expected": "x"}])
    out_dir = tmp_path / "out"
    options = HarnessOptions(
        adapter_name="toy",
        strategy_name="agentless_basic",
        subset_path=subset,
        out_dir=out_dir,
        extras={"out_dir": str(out_dir)},
    )
    live = BenchHarness(options, default_registry()).run()
    replay = replay_summary_from_dir(out_dir)
    assert replay.to_dict() == live.to_dict()


def test_harness_unknown_adapter_raises(tmp_path: Path) -> None:
    subset = tmp_path / "subset.jsonl"
    _write_subset(subset, [{"instance_id": "a", "expected": "x"}])
    options = HarnessOptions(
        adapter_name="missing",
        strategy_name="agentless_basic",
        subset_path=subset,
        out_dir=tmp_path / "out",
        extras={},
    )
    with pytest.raises(KeyError):
        BenchHarness(options, default_registry()).run()


def test_harness_branching_repair_falls_through_when_first_candidate_passes(
    tmp_path: Path,
) -> None:
    subset = tmp_path / "subset.jsonl"
    _write_subset(subset, [{"instance_id": "a", "expected": "x"}])
    out_dir = tmp_path / "out"
    options = HarnessOptions(
        adapter_name="toy",
        strategy_name="branching_repair",
        subset_path=subset,
        out_dir=out_dir,
        max_repair_rounds=1,
        extras={"out_dir": str(out_dir)},
    )
    summary = BenchHarness(options, default_registry()).run()
    assert summary.strict_success_count == 1


def test_harness_cli_main_writes_outputs(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    subset = tmp_path / "subset.jsonl"
    _write_subset(subset, [{"instance_id": "z", "expected": "abc"}])
    out_dir = tmp_path / "out"
    rc = main(
        [
            "--adapter",
            "toy",
            "--strategy",
            "agentless_basic",
            "--subset",
            str(subset),
            "--out-dir",
            str(out_dir),
            "--extras",
            json.dumps({"out_dir": str(out_dir)}),
        ]
    )
    assert rc == 0
    captured = capsys.readouterr().out
    payload = json.loads(captured)
    assert payload["instance_count"] == 1
    assert payload["strict_success_count"] == 1
