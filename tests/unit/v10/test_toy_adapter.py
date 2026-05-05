from __future__ import annotations

from adapters_v10.toy import ToyTextAdapter
from core_v10.contracts import Candidate, CandidateKind, RunInstance
from core_v10.strategy_runner import StopReason, StrategyConfig, StrategyRunner


def test_toy_adapter_runs_agentless_end_to_end(tmp_path) -> None:
    adapter = ToyTextAdapter()
    runner = StrategyRunner(
        adapter=adapter,
        event_log_path=tmp_path / "events.jsonl",
    )
    instance = RunInstance(
        instance_id="toy-001",
        adapter_name=adapter.name,
        objective="write expected text",
        metadata={"workspace_root": tmp_path / "workspace", "expected": "done"},
    )

    result = runner.run_agentless(
        run_id="run-001",
        instance=instance,
        candidate_provider=lambda _observation, _instance: [
            Candidate(
                candidate_id="candidate-ok",
                kind=CandidateKind.TEXT,
                payload={"answer": "done"},
                origin="unit-test",
            )
        ],
    )

    assert result.strict_success is True
    assert result.finalization is not None
    artifact_path = result.finalization.artifact.artifacts["answer.txt"]
    assert artifact_path.read_text(encoding="utf-8") == "done"


def test_toy_adapter_branching_repair_end_to_end(tmp_path) -> None:
    adapter = ToyTextAdapter()
    runner = StrategyRunner(
        adapter=adapter,
        event_log_path=tmp_path / "events.jsonl",
    )
    instance = RunInstance(
        instance_id="toy-001",
        adapter_name=adapter.name,
        objective="write expected text",
        metadata={"workspace_root": tmp_path / "workspace", "expected": "done"},
    )

    result = runner.run_branching_repair(
        run_id="run-001",
        instance=instance,
        candidate_provider=lambda _observation, _instance: [
            Candidate(
                candidate_id="candidate-bad",
                kind=CandidateKind.TEXT,
                payload={"answer": "wrong"},
                origin="unit-test",
            )
        ],
        repair_provider=lambda feedback, candidate, observation, _instance: [
            Candidate(
                candidate_id=f"{candidate.candidate_id}-repair",
                kind=CandidateKind.TEXT,
                payload={"answer": observation.data["expected"]},
                origin=f"repair:{feedback.failure_type}",
            )
        ],
        config=StrategyConfig(
            name="branching_repair",
            max_candidates=1,
            max_repair_rounds=1,
        ),
    )

    assert result.stop_reason == StopReason.STRICT_SUCCESS
    assert result.selected_hypothesis_id == "candidate-bad-repair"
    assert result.blackboard is not None
    assert result.blackboard.metrics["lineage_depth"] == 1
    assert result.blackboard.failed_hypotheses == ("candidate-bad",)
