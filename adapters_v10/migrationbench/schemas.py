"""Typed contracts for V10 MigrationBench instances and edits.

This module is intentionally a clean re-implementation of the legacy
``adapters/migrationbench/schemas.py`` surface, dropping V7 colony-only
artefacts (``EditApplicationResult``, ``PatchHypothesis``,
``empty_output_contract``) that carried orchestration concepts now owned by
``core_v10``.
"""

from __future__ import annotations

import re
from pathlib import PurePosixPath
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


JAVA_MAJOR_VERSION: dict[int, int] = {8: 52, 11: 55, 17: 61, 21: 65}
"""Mapping from Java SE version to JVM class file ``major_version`` byte."""


def stable_instance_id(repo: str) -> str:
    """Return a deterministic filesystem-safe id for an ``owner/repo`` string."""

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

    @field_validator("target_java")
    @classmethod
    def _target_java_supported(cls, value: int) -> int:
        if int(value) not in JAVA_MAJOR_VERSION:
            raise ValueError(
                f"target_java {value} is not in supported set "
                f"{sorted(JAVA_MAJOR_VERSION)}"
            )
        return int(value)

    @model_validator(mode="after")
    def _normalize_instance_id(self) -> "MigrationBenchInstance":
        if self.instance_id == "auto":
            self.instance_id = stable_instance_id(self.repo_url)
        return self

    @property
    def require_compiled_java_major_version(self) -> int:
        """Return official JVM class major version for the target Java version."""

        return JAVA_MAJOR_VERSION[int(self.target_java)]

    @property
    def is_maximal_migration(self) -> bool:
        return self.migration_mode == "maximal"


class TypedEdit(BaseModel):
    """One repository-relative edit primitive shared by all V10 patch arms."""

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
    """Structured LLM output for V10 patch-producing strategies."""

    edits: list[TypedEdit] = Field(default_factory=list)
    rationale: str = ""
    expected_build_command: str = "mvn clean verify"

    @model_validator(mode="after")
    def _reject_empty(self) -> "TypedEditSet":
        if not self.edits:
            raise ValueError("TypedEditSet.edits cannot be empty")
        return self


class PatchStats(BaseModel):
    """Simple git-diff stats for an exported V10 patch artifact."""

    patch_delivered: bool = False
    patch_lines_added: int = 0
    patch_lines_deleted: int = 0
    files_modified_count: int = 0
