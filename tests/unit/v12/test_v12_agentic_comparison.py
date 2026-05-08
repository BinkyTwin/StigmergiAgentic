"""V12.3 agentic comparison runner and audit tests."""

from __future__ import annotations

import json
from pathlib import Path

from core_v10.event_log import JsonlEventLog
from core_v12.agent_loop import AgentLoop
from core_v12.tools.registry import ToolExecutionContext
from core_v12.tools.schema import ToolCall
from scripts.bench.artifacts import Manifest, write_manifest
from scripts.v12.audit_v12_campaign import audit_v12_campaign


class StubWorkspace:
    def __init__(self, files: dict[str, str], *, label: str = "base") -> None:
        self.files = dict(files)
        self.label = label

    def read_file(self, rel: str, *, max_bytes: int = 0) -> str:
        return self.files[rel]

    def write_file(self, rel: str, content: str) -> None:
        self.files[rel] = content


def test_agent_loop_context_preparer_is_used_for_mutating_tool() -> None:
    base = StubWorkspace({"pom.xml": "<java.version>1.8</java.version>"}, label="base")
    branch = StubWorkspace(dict(base.files), label="branch")

    def prepare(call, context, step_index):  # noqa: ANN001
        assert call.tool_name == "edit_file_guarded"
        assert step_index == 0
        return ToolExecutionContext(
            workspace=branch,
            migration_context=context.migration_context,
            objective=context.objective,
            metadata={"branch_id": "branch-step-0", "candidate_id": "cand-step-0"},
        )

    loop = AgentLoop(
        context_preparer=prepare,
        tool_chooser=lambda view, tools, history: ToolCall(
            tool_name="edit_file_guarded",
            arguments={
                "edits": [
                    {
                        "type": "replace_text",
                        "path": "pom.xml",
                        "old": "<java.version>1.8</java.version>",
                        "new": "<java.version>17</java.version>",
                    }
                ]
            },
        ),
    )

    step = loop.step(
        context=ToolExecutionContext(workspace=base),
        objective="migrate",
        migration_context={"target_java": 17},
    )

    assert step.result.status == "success"
    assert base.files["pom.xml"] == "<java.version>1.8</java.version>"
    assert branch.files["pom.xml"] == "<java.version>17</java.version>"
    assert step.result.metadata["execution_context"]["branch_id"] == "branch-step-0"


def test_v12_audit_writes_readiness_and_pairwise_csv(tmp_path: Path) -> None:
    root = tmp_path / "campaign"
    tools = ["read_file", "edit_file_guarded", "inspect_pom"]
    for arm in (
        "S1_sd_feedback_like",
        "S2_tool_feedback_agent",
        "V12_stigmergic_tool_agent",
    ):
        arm_dir = root / arm
        write_manifest(
            arm_dir,
            Manifest(
                campaign_id=f"camp-{arm}",
                adapter_name="migrationbench",
                strategy_name="v12_agentic_tool_loop",
                subset_path="subset.jsonl",
                instance_ids=["inst1"],
                out_dir=str(arm_dir),
                extras={"v12_tool_registry": tools} if arm != "S1_sd_feedback_like" else {},
            ),
        )
        log = JsonlEventLog(arm_dir / "events" / "inst1" / "eventlog.jsonl")
        log.append(
            run_id="r1",
            instance_id="inst1",
            event_type="validation.completed",
            actor="verifier",
            hypothesis_id=f"{arm}-h1",
            payload={
                "validation": {
                    "candidate_id": f"{arm}-c1",
                    "status": "failed",
                    "summary": "partial",
                    "signals": {
                        "patch_delivered": True,
                        "patch_applies": arm != "S1_sd_feedback_like",
                        "compile_success": arm == "V12_stigmergic_tool_agent",
                    },
                }
            },
        )
        if arm != "S1_sd_feedback_like":
            log.append(
                run_id="r1",
                instance_id="inst1",
                event_type="agent.tool_call.requested",
                actor=arm,
                payload={
                    "tool_call": {"tool_name": "read_file", "rationale": "inspect"},
                    "tool_recommendation_context": {
                        "strongly_supported_tools": ["read_file"],
                        "selected_recommendation": "strong_support",
                        "selected_is_inhibited": False,
                        "selected_is_forbidden": False,
                        "ignored_strongly_supported_tools": [],
                    },
                },
            )
            log.append(
                run_id="r1",
                instance_id="inst1",
                event_type="tool.executed",
                actor=arm,
                payload={
                    "tool_call": {"tool_name": "read_file", "rationale": "inspect"},
                    "result": {
                        "tool_name": "read_file",
                        "status": "success",
                        "summary": "read pom.xml",
                        "workspace_mutated": False,
                        "candidate_created": False,
                    },
                },
            )
        if arm == "V12_stigmergic_tool_agent":
            log.append(
                run_id="r1",
                instance_id="inst1",
                event_type="pheromone.read",
                actor=arm,
                payload={"pheromone_ids": ["p1"]},
            )
        log.append(
            run_id="r1",
            instance_id="inst1",
            event_type="run.completed",
            actor="v12_runner",
            payload={
                "medium_created_patch_count": 0,
                "suggest_tool_applied_patch_count": 0,
            },
        )

    report = audit_v12_campaign(root)

    assert report["gates"]["s2_v12_same_tool_registry"] is True
    assert report["gates"]["medium_created_patch_count_zero"] is True
    assert report["gates"]["suggest_tool_applied_patch_count_zero"] is True
    assert (root / "audits" / "pairwise_best_observed.csv").exists()
    assert (root / "audits" / "medium_effect_attribution.csv").exists()
    pairwise = (root / "audits" / "pairwise_best_observed.csv").read_text()
    assert "V12_stigmergic_tool_agent" in pairwise
    assert json.loads((root / "v12_readiness_report.json").read_text()) == report
