from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from adapters.migrationbench.schemas import MigrationBenchInstance, TypedEdit, TypedEditSet
from adapters.migrationbench.workspace import MigrationBenchWorkspace


def _git_repo(tmp_path: Path) -> tuple[Path, str]:
    repo = tmp_path / "source"
    repo.mkdir()
    (repo / "pom.xml").write_text(
        "<project><properties>"
        "<maven.compiler.source>1.8</maven.compiler.source>"
        "<maven.compiler.target>1.8</maven.compiler.target>"
        "</properties></project>",
        encoding="utf-8",
    )
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    subprocess.run(["git", "add", "pom.xml"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
    return repo, commit


def _instance(repo: Path, commit: str) -> MigrationBenchInstance:
    return MigrationBenchInstance(
        instance_id="local_repo",
        repo_url=str(repo),
        base_commit=commit,
        target_java=17,
        migration_mode="minimal",
    )


def test_workspace_applies_typed_edits_and_verifies_patch(tmp_path: Path) -> None:
    repo, commit = _git_repo(tmp_path)
    workspace = MigrationBenchWorkspace(
        instance=_instance(repo, commit),
        root_dir=tmp_path / "workspace",
    )
    workspace.prepare(force=True)

    result = workspace.apply_typed_edits(
        TypedEditSet(
            edits=[
                TypedEdit(
                    type="replace_text",
                    path="pom.xml",
                    old="<maven.compiler.source>1.8</maven.compiler.source>",
                    new="<maven.compiler.source>17</maven.compiler.source>",
                )
            ]
        )
    )
    assert result.applied
    patch_path = tmp_path / "patch.diff"
    stats = workspace.export_patch(patch_path)

    assert stats.patch_delivered is True
    assert stats.files_modified_count == 1
    applies, reason = workspace.verify_patch_applies(
        patch_path=patch_path,
        verification_root=tmp_path / "verify",
    )
    assert applies is True
    assert reason == "ok"


def test_workspace_rejects_replacement_mismatch(tmp_path: Path) -> None:
    repo, commit = _git_repo(tmp_path)
    workspace = MigrationBenchWorkspace(
        instance=_instance(repo, commit),
        root_dir=tmp_path / "workspace",
    )
    workspace.prepare(force=True)

    result = workspace.apply_typed_edits(
        TypedEditSet(
            edits=[
                TypedEdit(
                    type="replace_text",
                    path="pom.xml",
                    old="<missing>1.8</missing>",
                    new="<missing>17</missing>",
                )
            ]
        )
    )
    assert result.applied is False
    assert result.failure_reason.startswith("replacement_count_mismatch")


def test_typed_edit_rejects_path_escape() -> None:
    with pytest.raises(ValueError):
        TypedEdit(
            type="write_file",
            path="../outside.txt",
            content="bad",
        )
