"""Phase 6 — A4 arm is wired into the ablation harness."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.bench.compare_strategies import DEFAULT_ARMS, run_comparison


def _write_subset(path: Path, instances: list[dict]) -> None:
    path.write_text(
        "\n".join(json.dumps(inst) for inst in instances) + "\n",
        encoding="utf-8",
    )


def test_default_arms_contain_a4_with_a3_budgets() -> None:
    by_id = {arm.arm_id: arm for arm in DEFAULT_ARMS}
    assert "A4_stigmergic_blackboard" in by_id
    a3 = by_id["A3_branching_repair"]
    a4 = by_id["A4_stigmergic_blackboard"]
    assert a4.strategy_name == "stigmergic_blackboard"
    # Same budget envelope as A3 to keep the ablation valid.
    assert a4.max_candidates == a3.max_candidates
    assert a4.max_repair_rounds == a3.max_repair_rounds
    assert a4.max_repairs_per_candidate == a3.max_repairs_per_candidate


def test_compare_strategies_runs_four_arms_on_toy(tmp_path: Path) -> None:
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
        seed=42,
        extras={"out_dir": str(out_dir)},
    )

    arm_ids = [arm["arm_id"] for arm in comparison["arms"]]
    assert "A4_stigmergic_blackboard" in arm_ids
    a4_payload = next(
        arm for arm in comparison["arms"] if arm["arm_id"] == "A4_stigmergic_blackboard"
    )
    # New Phase 6 fields are present in the comparison.
    for key in (
        "signal_emitted_total",
        "signal_applied_total",
        "pheromone_hit_rate",
        "feedback_reuse_rate",
        "repeated_failure_suppression_total",
    ):
        assert key in a4_payload
    # Toy adapter validates every candidate ⇒ A4 must finish ≥1 strict success.
    assert a4_payload["strict_success_count"] >= 1
    # Each instance entry now carries the per-instance signal counters.
    sample = a4_payload["instances"][0]
    for key in (
        "signal_emitted_count",
        "signal_applied_count",
        "pheromone_hit_rate",
        "feedback_reuse_rate",
        "repeated_failure_suppression",
    ):
        assert key in sample
