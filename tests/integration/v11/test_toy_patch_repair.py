"""V11 toy patch repair integration smoke."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.bench.compare_strategies import V11_ARMS, run_comparison
from scripts.bench.telemetry import (
    DECISION_INFLUENCED_EVENT,
    OPERATOR_APPLIED_EVENT,
    OPERATOR_INVOKED_EVENT,
    SIGNAL_READ_EVENT,
    TRAJECTORY_DIVERGED_EVENT,
    WORKER_ACTIVATED_EVENT,
    replay_summary_from_dir,
)
from scripts.v11.run_v11_smoke import run_toy_smoke


def _write_subset(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                json.dumps({"instance_id": "toy-v11-a", "expected": "alpha"}),
                json.dumps({"instance_id": "toy-v11-b", "expected": "beta"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _read_event_types(arm_dir: Path, instance_id: str) -> list[str]:
    path = arm_dir / "events" / instance_id / "eventlog.jsonl"
    return [
        json.loads(line)["type"]
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _read_events(arm_dir: Path, instance_id: str) -> list[dict]:
    path = arm_dir / "events" / instance_id / "eventlog.jsonl"
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_v11_operator_search_produces_causal_chain_and_replay_parity(
    tmp_path: Path,
) -> None:
    subset = tmp_path / "subset.jsonl"
    _write_subset(subset)
    out_dir = tmp_path / "compare"
    arms = tuple(arm for arm in V11_ARMS if arm.arm_id in {"B2_branching_repair", "B6_operator_search"})

    comparison = run_comparison(
        adapter_name="toy",
        subset_path=subset,
        out_dir=out_dir,
        seed=42,
        extras={"out_dir": str(out_dir), "toy_initial_wrong": True},
        arms=arms,
    )
    by_arm = {arm["arm_id"]: arm for arm in comparison["arms"]}

    b2 = by_arm["B2_branching_repair"]
    b6 = by_arm["B6_operator_search"]
    assert b2["decision_influenced_total"] == 0
    assert b6["signal_read_total"] > 0
    assert b6["decision_influenced_total"] > 0
    assert b6["trajectory_divergence_total"] > 0
    assert b6["operator_invoked_total"] > 0
    assert b6["operator_applied_total"] > 0
    assert b6["stigmergic_causality_rate"] > 0
    assert b6["strict_success_count"] == 2

    arm_dir = out_dir / "B6_operator_search"
    live = json.loads((arm_dir / "summary.json").read_text(encoding="utf-8"))
    replay = replay_summary_from_dir(arm_dir).to_dict()
    assert live == replay

    events = _read_events(arm_dir, "toy-v11-a")
    event_types = [event["type"] for event in events]
    for event_type in (
        "signal.emitted",
        SIGNAL_READ_EVENT,
        WORKER_ACTIVATED_EVENT,
        DECISION_INFLUENCED_EVENT,
        TRAJECTORY_DIVERGED_EVENT,
        OPERATOR_INVOKED_EVENT,
        OPERATOR_APPLIED_EVENT,
        "validation.completed",
    ):
        assert event_type in event_types

    emitted = next(event for event in events if event["type"] == "signal.emitted")
    created_from = emitted["payload"]["created_from"]
    assert created_from["hypothesis_id"] == "toy-v11-a-c0"
    assert created_from["verifier_status"] == "failed"
    assert created_from["failure_type"] == "answer_mismatch"


def test_v11_toy_smoke_is_idempotent_for_reused_output_dir(tmp_path: Path) -> None:
    out_dir = tmp_path / "v11_smoke"

    first = run_toy_smoke(out_dir)
    second = run_toy_smoke(out_dir)

    assert first["arms"][0]["instance_count"] == second["arms"][0]["instance_count"]
    for arm in second["arms"]:
        arm_dir = out_dir / "toy" / arm["arm_id"]
        live = json.loads((arm_dir / "summary.json").read_text(encoding="utf-8"))
        assert live == replay_summary_from_dir(arm_dir).to_dict()
