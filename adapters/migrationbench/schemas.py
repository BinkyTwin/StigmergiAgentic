"""Typed contracts for MigrationBench instances, edits, and run outputs."""

from __future__ import annotations

import re
from pathlib import PurePosixPath
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


def stable_instance_id(repo: str) -> str:
    """Return a deterministic filesystem-safe id for an owner/repo string."""
    cleaned = re.sub(r"^https?://github\.com/", "", str(repo).strip())
    cleaned = cleaned[:-4] if cleaned.endswith(".git") else cleaned
    return re.sub(r"[^A-Za-z0-9]+", "__", cleaned).strip("_").lower()


class MigrationBenchInstance(BaseModel):
    """One MigrationBench repository-level migration task."""

    instance_id: str
    repo_url: str
    base_commit: str
    target_java: int = 17
    migration_mode: Literal["minimal", "maximal"] = "minimal"
    source: str = "migrationbench_selected"
    stratum: dict[str, Any] = Field(default_factory=dict)
    stats: dict[str, Any] = Field(default_factory=dict)

    @field_validator("instance_id")
    @classmethod
    def _instance_id_non_empty(cls, value: str) -> str:
        value = str(value).strip()
        if not value:
            raise ValueError("instance_id cannot be empty")
        return value

    @field_validator("repo_url")
    @classmethod
    def _repo_url_non_empty(cls, value: str) -> str:
        value = str(value).strip()
        if not value:
            raise ValueError("repo_url cannot be empty")
        return value

    @field_validator("base_commit")
    @classmethod
    def _base_commit_non_empty(cls, value: str) -> str:
        value = str(value).strip()
        if not value:
            raise ValueError("base_commit cannot be empty")
        return value

    @model_validator(mode="after")
    def _normalize_instance_id(self) -> "MigrationBenchInstance":
        if self.instance_id == "auto":
            self.instance_id = stable_instance_id(self.repo_url)
        return self

    @property
    def require_compiled_java_major_version(self) -> int:
        """Return official JVM class major version for the target Java version."""
        return {8: 52, 11: 55, 17: 61, 21: 65}.get(int(self.target_java), 61)

    @property
    def is_maximal_migration(self) -> bool:
        return self.migration_mode == "maximal"


class TypedEdit(BaseModel):
    """One repository-relative edit primitive shared by all arms."""

    type: Literal["replace_text", "write_file"]
    path: str
    old: str | None = None
    new: str | None = None
    content: str | None = None
    expected_replacements: int = 1
    allow_multiple: bool = False

    @field_validator("path")
    @classmethod
    def _path_is_repo_relative(cls, value: str) -> str:
        value = str(value).strip().replace("\\", "/")
        if not value:
            raise ValueError("edit path cannot be empty")
        posix = PurePosixPath(value)
        if posix.is_absolute() or ".." in posix.parts:
            raise ValueError("edit path must stay inside the repository")
        return value

    @model_validator(mode="after")
    def _validate_payload(self) -> "TypedEdit":
        if self.type == "replace_text":
            if not self.old:
                raise ValueError("replace_text.old must be non-empty")
            if self.new is None:
                raise ValueError("replace_text.new is required")
            if int(self.expected_replacements) < 1:
                raise ValueError("expected_replacements must be >= 1")
        if self.type == "write_file" and self.content is None:
            raise ValueError("write_file.content is required")
        return self


class TypedEditSet(BaseModel):
    """Structured LLM output for patch-producing arms."""

    edits: list[TypedEdit] = Field(default_factory=list)
    rationale: str = ""
    expected_build_command: str = "mvn clean verify"


class EditApplicationResult(BaseModel):
    """Result of applying typed edits to a workspace."""

    applied: bool
    failure_reason: str = "ok"
    files_modified: list[str] = Field(default_factory=list)
    replacements: dict[str, int] = Field(default_factory=dict)


class PatchStats(BaseModel):
    """Simple git diff stats for a produced patch artifact."""

    patch_delivered: bool = False
    patch_lines_added: int = 0
    patch_lines_deleted: int = 0
    files_modified_count: int = 0


class PatchHypothesis(BaseModel):
    """Traceable V7 patch branch state stored in marker payloads."""

    branch_id: str
    parent_branch_id: str | None = None
    attempt: int = 0
    typed_edits: dict[str, Any] = Field(default_factory=dict)
    failure_taxonomy: str = ""
    build_feedback_digest: str = ""
    patch_applies: bool = False
    build_success: bool = False
    official_success: bool = False
    quality_score: float = 0.0


def empty_output_contract(
    *,
    instance: MigrationBenchInstance,
    framework: str,
    provider: str = "",
    model: str = "",
    seed: int = 42,
    failure_reason: str,
) -> dict[str, Any]:
    """Return the common failure contract used by exporters and runners."""
    return {
        "instance_id": instance.instance_id,
        "framework": framework,
        "provider": provider,
        "model": model,
        "seed": int(seed),
        "artifact_delivered": False,
        "patch_delivered": False,
        "patch_applies": False,
        "official_success": False,
        "strict_success": False,
        "failure_reason": failure_reason,
        "migration_mode": instance.migration_mode,
        "target_java": int(instance.target_java),
        "build_success": False,
        "test_success": False,
        "compiled_major_version_ok": None,
        "test_count_non_decreasing": None,
        "dependency_policy_ok": None,
        "tokens_total": 0,
        "cost_total_usd": 0.0,
        "runtime_seconds": 0.0,
        "repair_cycles": 0,
        "llm_calls": 0,
        "branch_count": 0,
        "best_branch_id": "",
        "failure_taxonomy": "",
        "dynamic_agents_min": None,
        "dynamic_agents_max": None,
        "dynamic_agents_avg": None,
        "caps_hit": {},
        "last_progress_at": None,
        "manual_abort": False,
        "abort_reason": "",
        "files_modified_count": 0,
        "patch_lines_added": 0,
        "patch_lines_deleted": 0,
        "markers_created": 0,
        "coordination_overhead": 0,
    }
