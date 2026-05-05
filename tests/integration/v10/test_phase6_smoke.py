"""Phase 6 integration smoke — A3 vs A4 on the toy adapter.

These tests exercise the full bench harness on the in-tree toy adapter so we
can validate the live==replay parity of the new stigmergic counters and the
A4 ≡ A3 invariant when no signal-driven decision is taken.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.bench.compare_strategies import (
    DEFAULT_ARMS,
    AblationArm,
    run_comparison,
)
from scripts.bench.telemetry import (
    SIGNAL_APPLIED_EVENT,
    SIGNAL_EMITTED_EVENT,
    replay_summary_from_dir,
)


def _write_subset(path: Path, instances: list[dict]) -> None:
    path.write_text(
        "\n".join(json.dumps(inst) for inst in instances) + "\n",
        encoding="utf-8",
    )


def _read_eventlog(out_dir: Path, instance_id: str) -> list[dict]:
    path = out_dir / "events" / instance_id / "eventlog.jsonl"
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_phase6_a4_emits_signal_events_on_toy_subset(tmp_path: Path) -> None:
    subset = tmp_path / "subset.jsonl"
    _write_subset(
        subset,
        [
            {"instance_id": "i-1", "expected": "alpha"},
            {"instance_id": "i-2", "expected": "beta"},
        ],
    )
    out_dir = tmp_path / "compare"
    a4_only = (
        next(arm for arm in DEFAULT_ARMS if arm.arm_id == "A4_stigmergic_blackboard"),
    )
    run_comparison(
        adapter_name="toy",
        subset_path=subset,
        out_dir=out_dir,
        seed=42,
        extras={"out_dir": str(out_dir)},
        arms=a4_only,
    )
    arm_dir = out_dir / "A4_stigmergic_blackboard"
    summary_live = json.loads((arm_dir / "summary.json").read_text(encoding="utf-8"))
    summary_replay = replay_summary_from_dir(arm_dir).to_dict()
    assert summary_live == summary_replay, "live == replay parity must hold for A4"
    # The toy adapter validates every candidate ⇒ at least one SUPPORT
    # signal.emitted event per instance (origin reinforcement).
    for instance_id in ("i-1", "i-2"):
        events = _read_eventlog(arm_dir, instance_id)
        types = [e["type"] for e in events]
        assert SIGNAL_EMITTED_EVENT in types, f"missing signal.emitted for {instance_id}"


def test_phase6_a3_vs_a4_a4_does_not_break_strict_success(tmp_path: Path) -> None:
    subset = tmp_path / "subset.jsonl"
    _write_subset(
        subset,
        [
            {"instance_id": "i-1", "expected": "alpha"},
            {"instance_id": "i-2", "expected": "beta"},
            {"instance_id": "i-3", "expected": "gamma"},
        ],
    )
    out_dir = tmp_path / "compare"
    selected = tuple(
        arm
        for arm in DEFAULT_ARMS
        if arm.arm_id in {"A3_branching_repair", "A4_stigmergic_blackboard"}
    )
    comparison = run_comparison(
        adapter_name="toy",
        subset_path=subset,
        out_dir=out_dir,
        seed=42,
        extras={"out_dir": str(out_dir)},
        arms=selected,
    )
    by_arm = {arm["arm_id"]: arm for arm in comparison["arms"]}
    a3 = by_arm["A3_branching_repair"]
    a4 = by_arm["A4_stigmergic_blackboard"]
    # A4 must not regress vs A3 on a workload where every candidate validates.
    assert a4["strict_success_count"] >= a3["strict_success_count"]
    # A4 has signal counters > 0 (origin SUPPORT emitted on each pass).
    assert a4["signal_emitted_total"] > 0
    # A3 has no signal traffic.
    assert a3["signal_emitted_total"] == 0
    assert a3["signal_applied_total"] == 0


def test_phase6_a4_live_equals_replay_summary_on_three_instance_subset(
    tmp_path: Path,
) -> None:
    subset = tmp_path / "subset.jsonl"
    _write_subset(
        subset,
        [
            {"instance_id": f"i-{n}", "expected": f"x{n}"} for n in range(3)
        ],
    )
    out_dir = tmp_path / "compare"
    a4_only = (
        next(arm for arm in DEFAULT_ARMS if arm.arm_id == "A4_stigmergic_blackboard"),
    )
    run_comparison(
        adapter_name="toy",
        subset_path=subset,
        out_dir=out_dir,
        seed=42,
        extras={"out_dir": str(out_dir)},
        arms=a4_only,
    )
    arm_dir = out_dir / "A4_stigmergic_blackboard"
    live = json.loads((arm_dir / "summary.json").read_text(encoding="utf-8"))
    replay = replay_summary_from_dir(arm_dir).to_dict()
    assert live == replay
    # All five Phase 6 fields are reconstructible.
    for key in (
        "signal_emitted_total",
        "signal_applied_total",
        "pheromone_hit_rate",
        "feedback_reuse_rate",
        "repeated_failure_suppression_total",
    ):
        assert key in replay
