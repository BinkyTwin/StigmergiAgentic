"""V12.4 SD-Feedback primitives.

V12.4 makes SD-Feedback the verifier-gated loop of truth. Agents may use
read-only perception tools, then propose a patch through an explicit patch
channel. The harness guards, applies and verifies that proposal; the medium can
only enrich the next feedback block.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from core_v10.contracts import FeedbackDigest, ValidationResult, to_jsonable
from core_v10.operators import validate_edit_set_against_workspace
from core_v12.medium.local_view import AgentLocalView


JsonDict = dict[str, Any]


class PatchProposal(BaseModel):
    """One agent-authored patch proposal.

    This is not a deterministic operator result. It is the LLM's explicit
    proposed mutation, validated by the harness before verifier execution.
    """

    model_config = ConfigDict(extra="forbid")

    action: Literal["propose_patch"] = "propose_patch"
    rationale: str
    expected_effect: str = ""
    patch: str | None = None
    edit_set: JsonDict | None = None
    metadata: JsonDict = Field(default_factory=dict)

    @model_validator(mode="after")
    def _exactly_one_patch_shape(self) -> "PatchProposal":
        has_patch = bool((self.patch or "").strip())
        has_edit_set = self.edit_set is not None
        if has_patch == has_edit_set:
            raise ValueError("PatchProposal requires exactly one of patch or edit_set")
        return self


class PatchChannelResult(BaseModel):
    """Guard/apply result for the explicit V12.4 patch channel."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["accepted", "rejected", "failed"]
    summary: str
    errors: list[str] = Field(default_factory=list)
    workspace_mutated: bool = False
    metadata: JsonDict = Field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.status == "accepted"


@dataclass(frozen=True)
class FunnelPoint:
    """Comparable best-observed funnel point."""

    score: int
    stage: str


@dataclass(frozen=True)
class SDFeedbackDecision:
    """Accept/revert decision for one verified patch attempt."""

    action: Literal["accept", "accept_exploratory", "revert"]
    reason: str
    previous: FunnelPoint
    observed: FunnelPoint


@dataclass(frozen=True)
class SDFeedbackArm:
    """V12.4 arm definition."""

    arm_id: str
    description: str
    uses_readonly_tools: bool
    uses_medium: bool
    uses_patch_proposal_channel: bool = True


V12_4_EXPERIMENTAL_ARMS: tuple[SDFeedbackArm, ...] = (
    SDFeedbackArm(
        arm_id="S1_sd_feedback_exact",
        description="SD-Feedback loop: feedback plus explicit patch proposal; no interactive read-only tools and no medium.",
        uses_readonly_tools=False,
        uses_medium=False,
    ),
    SDFeedbackArm(
        arm_id="S2_sd_feedback_readonly_tools",
        description="Same SD-Feedback loop plus shared read-only perception tools; no stigmergic medium.",
        uses_readonly_tools=True,
        uses_medium=False,
    ),
    SDFeedbackArm(
        arm_id="V12_stigmergic_sd_feedback",
        description="Same tools, budget and patch channel as S2, plus compact stigmergic feedback augmentation.",
        uses_readonly_tools=True,
        uses_medium=True,
    ),
)


def guard_patch_proposal(
    proposal: PatchProposal,
    workspace: Any,
    *,
    apply: bool = False,
) -> PatchChannelResult:
    """Validate and optionally apply an agent-authored patch proposal.

    The medium is deliberately absent from this function. It cannot create or
    alter the proposal; it can only affect future prompt context through
    feedback annotations.
    """

    if proposal.edit_set is not None:
        return _guard_edit_set_proposal(proposal, workspace, apply=apply)
    return _guard_unified_diff_proposal(proposal, workspace, apply=apply)


def funnel_point_from_validation(validation: ValidationResult) -> FunnelPoint:
    """Map verifier signals to the V12.4 best-observed funnel score."""

    haystack = "\n".join([validation.summary or "", *map(str, validation.errors)])
    if "replacement_count_too_low" in haystack:
        return FunnelPoint(score=-20, stage="replacement_error")
    signals = dict(validation.signals or {})
    for stage, score in (
        ("strict_success", 100),
        ("official_success", 80),
        ("test_success", 60),
        ("class_version_ok", 50),
        ("compile_success", 40),
        ("patch_applies", 20),
        ("patch_delivered", 10),
        ("applied", 10),
    ):
        if bool(signals.get(stage)):
            return FunnelPoint(score=score, stage=stage)
    return FunnelPoint(score=0, stage="none")


def decide_sd_feedback_outcome(
    *,
    previous: FunnelPoint,
    observed: FunnelPoint,
    previous_failure_type: str | None = None,
    observed_failure_type: str | None = None,
    allow_exploratory_equal: bool = True,
) -> SDFeedbackDecision:
    """Return whether the harness should accept or revert the patch branch."""

    if observed.score > previous.score:
        return SDFeedbackDecision(
            action="accept",
            reason="funnel_score_improved",
            previous=previous,
            observed=observed,
        )
    if (
        allow_exploratory_equal
        and observed.score == previous.score
        and observed_failure_type
        and previous_failure_type
        and observed_failure_type != previous_failure_type
    ):
        return SDFeedbackDecision(
            action="accept_exploratory",
            reason="same_score_but_failure_family_changed",
            previous=previous,
            observed=observed,
        )
    return SDFeedbackDecision(
        action="revert",
        reason="no_funnel_progress",
        previous=previous,
        observed=observed,
    )


def stigmergic_feedback_block_from_view(
    view: AgentLocalView,
    *,
    max_supports: int = 5,
    max_inhibitions: int = 5,
    max_hot_files: int = 5,
    max_hypotheses: int = 3,
    max_attempts: int = 10,
) -> JsonDict:
    """Build the compact V12.4 feedback augmentation shown to the agent."""

    supports = _top_pheromone_targets(view, kind="support", limit=max_supports)
    inhibitions = _top_pheromone_targets(
        view, kind="inhibit", limit=max_inhibitions
    )
    active_hypotheses = _active_hypotheses(view, limit=max_hypotheses)
    attempts = _failed_attempts_summary(view, limit=max_attempts)
    return {
        "failed_attempts_summary": attempts,
        "inhibitions": inhibitions,
        "supports": supports,
        "hot_files": list(view.hot_files[:max_hot_files]),
        "active_hypotheses": active_hypotheses,
        "best_observed": view.current_best or {},
        "anti_actions": list(view.anti_actions[:max_inhibitions]),
        "candidate_history": [dict(item) for item in view.candidate_history[-5:]],
        "medium_created_patch_count": 0,
    }


def sd_feedback_prompt_contract(*, uses_medium: bool) -> str:
    """Return the concise prompt contract shared by V12.4 agents."""

    medium_line = (
        "Use stigmergic_context as compact guidance, not as an instruction to obey blindly."
        if uses_medium
        else "You receive raw verifier feedback only; no stigmergic context is available."
    )
    return "\n".join(
        [
            "You are in an SD-Feedback migration loop.",
            "You may inspect using read-only tools when available.",
            "When ready, output exactly one propose_patch object.",
            "The harness will guard the patch, apply it on an isolated branch, run the verifier, then accept or revert.",
            "Do not ask to run Maven or tests; verifier execution is automatic after a patch proposal.",
            "Do not delete or disable tests.",
            medium_line,
        ]
    )


def feedback_to_failure_type(feedback: FeedbackDigest | JsonDict | None) -> str | None:
    """Extract a comparable failure family from feedback-like data."""

    if feedback is None:
        return None
    payload = to_jsonable(feedback)
    if isinstance(payload, dict):
        return str(payload.get("failure_type") or "") or None
    return None


def _guard_edit_set_proposal(
    proposal: PatchProposal,
    workspace: Any,
    *,
    apply: bool,
) -> PatchChannelResult:
    edit_set = dict(proposal.edit_set or {})
    guard = validate_edit_set_against_workspace(edit_set, workspace)
    if not guard.ok:
        return PatchChannelResult(
            status="rejected",
            summary="edit_set rejected by workspace guard",
            metadata={"guard": guard.to_dict()},
        )
    if not apply:
        return PatchChannelResult(
            status="accepted",
            summary="edit_set passed workspace guard",
            metadata={"guard": guard.to_dict()},
        )
    if hasattr(workspace, "apply_typed_edits"):
        result = workspace.apply_typed_edits(edit_set)
        return PatchChannelResult(
            status="accepted" if result.applied else "failed",
            summary="edit_set applied" if result.applied else result.failure_reason,
            workspace_mutated=bool(result.applied),
            metadata={
                "guard": guard.to_dict(),
                "files_modified": list(result.files_modified),
                "replacements": dict(result.replacements),
            },
        )
    return PatchChannelResult(
        status="failed",
        summary="workspace cannot apply typed edits",
        metadata={"guard": guard.to_dict()},
    )


def _guard_unified_diff_proposal(
    proposal: PatchProposal,
    workspace: Any,
    *,
    apply: bool,
) -> PatchChannelResult:
    repo_dir = _repo_dir(workspace)
    if repo_dir is None:
        return PatchChannelResult(
            status="rejected",
            summary="repo directory unavailable for unified diff",
        )
    patch = str(proposal.patch or "")
    check = subprocess.run(
        ["git", "apply", "--check", "-"],
        cwd=repo_dir,
        input=patch,
        capture_output=True,
        text=True,
        check=False,
    )
    if check.returncode != 0:
        return PatchChannelResult(
            status="rejected",
            summary="git apply check failed",
            errors=[(check.stderr or check.stdout)[-2000:]],
        )
    if not apply:
        return PatchChannelResult(
            status="accepted",
            summary="unified diff passed git apply --check",
            metadata={"patch_chars": len(patch)},
        )
    applied = subprocess.run(
        ["git", "apply", "-"],
        cwd=repo_dir,
        input=patch,
        capture_output=True,
        text=True,
        check=False,
    )
    if applied.returncode != 0:
        return PatchChannelResult(
            status="failed",
            summary="git apply failed after successful check",
            errors=[(applied.stderr or applied.stdout)[-2000:]],
        )
    return PatchChannelResult(
        status="accepted",
        summary="unified diff applied",
        workspace_mutated=True,
        metadata={"patch_chars": len(patch)},
    )


def _repo_dir(workspace: Any) -> Path | None:
    metadata = getattr(workspace, "metadata", None)
    if isinstance(metadata, dict) and metadata.get("repo_dir"):
        return Path(str(metadata["repo_dir"]))
    root = getattr(workspace, "root", None)
    if root is not None:
        root_path = Path(root)
        return root_path / "repo" if (root_path / "repo").exists() else root_path
    repo = getattr(workspace, "repo_dir", None)
    return Path(repo) if repo is not None else None


def _top_pheromone_targets(
    view: AgentLocalView,
    *,
    kind: str,
    limit: int,
) -> list[JsonDict]:
    rows: list[JsonDict] = []
    for item in view.relevant_pheromones:
        if str(item.get("kind") or "") != kind:
            continue
        rows.append(
            {
                "target": item.get("target"),
                "strength": item.get("intensity"),
                "reason": item.get("reason"),
                "evidence": item.get("evidence") or [],
            }
        )
    rows.sort(key=lambda row: float(row.get("strength") or 0.0), reverse=True)
    return rows[:limit]


def _active_hypotheses(view: AgentLocalView, *, limit: int) -> list[JsonDict]:
    hypotheses: list[JsonDict] = []
    for failure in view.recent_failures[-limit:]:
        failure_type = str(failure.get("failure_type") or "")
        if not failure_type:
            continue
        hypotheses.append(
            {
                "name": failure_type,
                "confidence": 0.6,
                "evidence": failure.get("evidence") or [],
                "summary": failure.get("summary"),
            }
        )
    return hypotheses[-limit:]


def _failed_attempts_summary(view: AgentLocalView, *, limit: int) -> list[str]:
    rows: list[str] = []
    for failure in view.recent_failures[-limit:]:
        failure_type = str(failure.get("failure_type") or "unknown")
        summary = str(failure.get("summary") or failure_type)
        rows.append(f"{failure_type}: {summary[:240]}")
    return rows


__all__ = [
    "FunnelPoint",
    "PatchChannelResult",
    "PatchProposal",
    "SDFeedbackArm",
    "SDFeedbackDecision",
    "V12_4_EXPERIMENTAL_ARMS",
    "decide_sd_feedback_outcome",
    "feedback_to_failure_type",
    "funnel_point_from_validation",
    "guard_patch_proposal",
    "sd_feedback_prompt_contract",
    "stigmergic_feedback_block_from_view",
]
