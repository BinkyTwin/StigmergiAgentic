"""Phase 5 — A1/A2/A3 ablation harness tests on the toy adapter."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.bench.compare_strategies import (
    DEFAULT_ARMS,
    AblationArm,
    run_comparison,
)
from scripts.bench.telemetry import replay_summary_from_dir


def _write_subset(path: Path, instances: list[dict]) -> None:
    path.write_text(
        "\n".join(json.dumps(inst) for inst in instances) + "\n",
        encoding="utf-8",
    )


def test_compare_strategies_runs_three_arms_and_writes_comparison_json(tmp_path: Path) -> None:
    subset = tmp_path / "subset.jsonl"
    _write_subset(
        subset,
        [
            {"instance_id": "a", "expected": "alpha"},
            {"instance_id": "b", "expected": "beta"},
        ],
    )
    out_dir = tmp_path / "compare"

    comparison = run_comparison(
        adapter_name="toy",
        subset_path=subset,
        out_dir=out_dir,
        seed=11,
        extras={"out_dir": str(out_dir)},
    )

    assert (out_dir / "comparison.json").exists()
    arm_ids = [arm["arm_id"] for arm in comparison["arms"]]
    assert arm_ids == [arm.arm_id for arm in DEFAULT_ARMS]
    for arm_payload in comparison["arms"]:
        arm_dir = out_dir / arm_payload["arm_id"]
        assert (arm_dir / "manifest.json").exists()
        assert (arm_dir / "summary.json").exists()
        assert (arm_dir / "runs.jsonl").exists()
        assert arm_payload["instance_count"] == 2
        # Toy adapter trivially solves every instance: every arm should hit
        # strict_success on both records.
        assert arm_payload["strict_success_count"] == 2


def test_compare_strategies_each_arm_has_live_replay_parity(tmp_path: Path) -> None:
    subset = tmp_path / "subset.jsonl"
    _write_subset(subset, [{"instance_id": "x", "expected": "y"}])
    out_dir = tmp_path / "compare"

    run_comparison(
        adapter_name="toy",
        subset_path=subset,
        out_dir=out_dir,
        extras={"out_dir": str(out_dir)},
    )

    for arm in DEFAULT_ARMS:
        live = json.loads((out_dir / arm.arm_id / "summary.json").read_text())
        replay = replay_summary_from_dir(out_dir / arm.arm_id).to_dict()
        assert live == replay, f"live!=replay for arm {arm.arm_id}"


def test_compare_strategies_a3_payload_exposes_dedup_and_rationale(tmp_path: Path) -> None:
    subset = tmp_path / "subset.jsonl"
    _write_subset(subset, [{"instance_id": "only", "expected": "z"}])
    out_dir = tmp_path / "compare"

    comparison = run_comparison(
        adapter_name="toy",
        subset_path=subset,
        out_dir=out_dir,
        extras={"out_dir": str(out_dir)},
    )

    a3 = next(arm for arm in comparison["arms"] if arm["arm_id"].startswith("A3"))
    assert "dedup_skipped_total" in a3
    assert "repeat_failure_suppressed_total" in a3
    only = a3["instances"][0]
    assert "selection_rationale" in only
    assert only["selection_rationale"] is not None
    assert only["selection_rationale"]["selected_hypothesis_id"] is not None


def test_compare_strategies_accepts_custom_arm_list(tmp_path: Path) -> None:
    subset = tmp_path / "subset.jsonl"
    _write_subset(subset, [{"instance_id": "only", "expected": "z"}])
    out_dir = tmp_path / "compare"

    custom = (
        AblationArm(
            arm_id="solo_a1",
            strategy_name="agentless_basic",
            max_candidates=1,
            max_repair_rounds=0,
            max_repairs_per_candidate=1,
        ),
    )

    comparison = run_comparison(
        adapter_name="toy",
        subset_path=subset,
        out_dir=out_dir,
        extras={"out_dir": str(out_dir)},
        arms=custom,
    )

    arm_ids = [arm["arm_id"] for arm in comparison["arms"]]
    assert arm_ids == ["solo_a1"]
