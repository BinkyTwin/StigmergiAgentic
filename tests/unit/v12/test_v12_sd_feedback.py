"""V12.4 SD-Feedback loop primitives."""

from __future__ import annotations

import subprocess
from types import SimpleNamespace

from core_v10.contracts import FeedbackDigest, ValidationResult, ValidationStatus
from core_v12.medium.local_view import V12StigmergicMedium
from core_v12.sd_feedback import (
    FunnelPoint,
    PatchProposal,
    V12_4_EXPERIMENTAL_ARMS,
    decide_sd_feedback_outcome,
    funnel_point_from_validation,
    guard_patch_proposal,
    sd_feedback_prompt_contract,
    stigmergic_feedback_block_from_view,
)
from core_v12.tools.executor import build_sd_feedback_readonly_tool_registry


class StubWorkspace:
    def __init__(self, files: dict[str, str]) -> None:
        self.files = dict(files)

    def read_file(self, rel: str, *, max_bytes: int = 0) -> str:
        return self.files[rel]


def test_sd_feedback_patch_channel_guards_unified_diff(tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pom.xml").write_text("<project>old</project>\n", encoding="utf-8")
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    workspace = SimpleNamespace(metadata={"repo_dir": str(repo)})
    proposal = PatchProposal(
        rationale="Change the agent-authored patch only through the patch channel.",
        expected_effect="pom marker changes",
        patch=(
            "diff --git a/pom.xml b/pom.xml\n"
            "--- a/pom.xml\n"
            "+++ b/pom.xml\n"
            "@@ -1 +1 @@\n"
            "-<project>old</project>\n"
            "+<project>new</project>\n"
        ),
    )

    checked = guard_patch_proposal(proposal, workspace, apply=False)
    applied = guard_patch_proposal(proposal, workspace, apply=True)

    assert checked.status == "accepted"
    assert checked.workspace_mutated is False
    assert applied.status == "accepted"
    assert applied.workspace_mutated is True
    assert (repo / "pom.xml").read_text(encoding="utf-8") == (
        "<project>new</project>\n"
    )


def test_sd_feedback_patch_channel_rejects_invalid_edit_set() -> None:
    workspace = StubWorkspace({"pom.xml": "<java.version>1.8</java.version>"})
    proposal = PatchProposal(
        rationale="The LLM proposed an absent old span.",
        expected_effect="set target Java",
        edit_set={
            "edits": [
                {
                    "type": "replace_text",
                    "path": "pom.xml",
                    "old": "<missing>1.8</missing>",
                    "new": "<java.version>17</java.version>",
                    "expected_replacements": 1,
                }
            ]
        },
    )

    result = guard_patch_proposal(proposal, workspace)

    assert result.status == "rejected"
    assert result.metadata["guard"]["issues"][0]["reason"] == "old_span_absent"
    assert workspace.files["pom.xml"] == "<java.version>1.8</java.version>"


def test_accept_revert_policy_uses_best_observed_funnel() -> None:
    previous = FunnelPoint(score=20, stage="patch_applies")
    improved = FunnelPoint(score=40, stage="compile_success")
    same = FunnelPoint(score=20, stage="patch_applies")

    assert (
        decide_sd_feedback_outcome(previous=previous, observed=improved).action
        == "accept"
    )
    assert (
        decide_sd_feedback_outcome(
            previous=previous,
            observed=same,
            previous_failure_type="compile_error",
            observed_failure_type="test_failure",
        ).action
        == "accept_exploratory"
    )
    assert (
        decide_sd_feedback_outcome(
            previous=previous,
            observed=same,
            previous_failure_type="compile_error",
            observed_failure_type="compile_error",
        ).action
        == "revert"
    )


def test_funnel_point_from_validation_matches_v12_4_scores() -> None:
    validation = ValidationResult(
        candidate_id="c1",
        status=ValidationStatus.FAILED,
        validator_name="migrationbench",
        signals={"patch_applies": True, "compile_success": True},
        summary="compile passed",
    )
    replacement_error = ValidationResult(
        candidate_id="c2",
        status=ValidationStatus.ERROR,
        validator_name="migrationbench",
        signals={"patch_applies": True},
        summary="replacement_count_too_low",
    )

    assert funnel_point_from_validation(validation) == FunnelPoint(
        score=40, stage="compile_success"
    )
    assert funnel_point_from_validation(replacement_error) == FunnelPoint(
        score=-20, stage="replacement_error"
    )


def test_sd_feedback_readonly_tool_registry_has_no_mutators() -> None:
    registry = build_sd_feedback_readonly_tool_registry()

    assert "read_build_log" in registry.names()
    assert "edit_file_guarded" not in registry.names()
    assert "apply_patch" not in registry.names()
    assert "run_maven" not in registry.names()
    assert all(not spec.mutates_workspace for spec in registry.specs())
    assert all(not spec.creates_candidate for spec in registry.specs())


def test_v12_4_arm_definitions_keep_s2_v12_tool_attribution_clean() -> None:
    arms = {arm.arm_id: arm for arm in V12_4_EXPERIMENTAL_ARMS}

    assert set(arms) == {
        "S1_sd_feedback_exact",
        "S2_sd_feedback_readonly_tools",
        "V12_stigmergic_sd_feedback",
    }
    assert arms["S2_sd_feedback_readonly_tools"].uses_readonly_tools is True
    assert arms["V12_stigmergic_sd_feedback"].uses_readonly_tools is True
    assert arms["S2_sd_feedback_readonly_tools"].uses_medium is False
    assert arms["V12_stigmergic_sd_feedback"].uses_medium is True


def test_stigmergic_feedback_block_is_compact_and_patch_free() -> None:
    medium = V12StigmergicMedium()
    medium.update_from_feedback(
        FeedbackDigest(
            candidate_id="c1",
            failure_type="compile_error",
            severity="blocking",
            summary="src/main/java/App.java cannot find symbol",
            locations=[{"path": "src/main/java/App.java", "line": 3}],
            anti_actions=["repeat_same_pom_release_edit"],
        )
    )
    view = medium.local_view(
        objective="migrate",
        migration_context={"target_java": 17},
        current_best={"best_stage": "patch_applies"},
        tool_registry=build_sd_feedback_readonly_tool_registry().names(),
    )

    block = stigmergic_feedback_block_from_view(view)

    assert block["medium_created_patch_count"] == 0
    assert block["failed_attempts_summary"]
    assert block["supports"]
    assert "src/main/java/App.java" in block["hot_files"]
    assert "patch" not in block


def test_sd_feedback_prompt_contract_keeps_verifier_automatic() -> None:
    prompt = sd_feedback_prompt_contract(uses_medium=True)

    assert "propose_patch" in prompt
    assert "verifier execution is automatic" in prompt
    assert "Do not ask to run Maven or tests" in prompt
