from __future__ import annotations

import pytest
from pydantic import ValidationError

from adapters_v10.migrationbench.schemas import (
    JAVA_MAJOR_VERSION,
    MigrationBenchInstance,
    PatchStats,
    TypedEdit,
    TypedEditSet,
    stable_instance_id,
)


def test_stable_instance_id_strips_github_prefix_and_dotgit() -> None:
    assert stable_instance_id("https://github.com/owner/repo.git") == "owner__repo"
    assert stable_instance_id("Owner/Repo") == "owner__repo"


def test_instance_auto_id_is_derived_from_repo_url() -> None:
    instance = MigrationBenchInstance(
        instance_id="auto",
        repo_url="https://github.com/foo/bar",
        base_commit="deadbeef",
    )
    assert instance.instance_id == "foo__bar"


def test_instance_target_java_must_be_supported() -> None:
    with pytest.raises(ValidationError):
        MigrationBenchInstance(
            instance_id="foo__bar",
            repo_url="https://github.com/foo/bar",
            base_commit="deadbeef",
            target_java=14,
        )


def test_instance_class_version_mapping_matches_table() -> None:
    instance = MigrationBenchInstance(
        instance_id="foo__bar",
        repo_url="https://github.com/foo/bar",
        base_commit="deadbeef",
        target_java=17,
    )
    assert instance.require_compiled_java_major_version == JAVA_MAJOR_VERSION[17]
    assert instance.require_compiled_java_major_version == 61


def test_typed_edit_replace_text_requires_old_and_new() -> None:
    with pytest.raises(ValidationError):
        TypedEdit(type="replace_text", path="pom.xml", old="", new="x")
    with pytest.raises(ValidationError):
        TypedEdit(type="replace_text", path="pom.xml", old="x", new=None)


def test_typed_edit_path_must_be_repo_relative() -> None:
    with pytest.raises(ValidationError):
        TypedEdit(type="write_file", path="/etc/passwd", content="x")
    with pytest.raises(ValidationError):
        TypedEdit(type="write_file", path="../escape", content="x")


def test_typed_edit_set_rejects_empty_edits() -> None:
    with pytest.raises(ValidationError):
        TypedEditSet(edits=[])


def test_typed_edit_set_accepts_minimal_edit() -> None:
    edits = TypedEditSet(
        edits=[TypedEdit(type="write_file", path="A.java", content="class A{}")]
    )
    assert edits.expected_build_command == "mvn clean verify"
    assert len(edits.edits) == 1


def test_patch_stats_defaults_to_undelivered() -> None:
    stats = PatchStats()
    assert stats.patch_delivered is False
    assert stats.patch_lines_added == 0
    assert stats.files_modified_count == 0
