from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from adapters_v10.migrationbench import (
    MigrationBenchInstance,
    MigrationBenchWorkspaceV10,
    TypedEdit,
    TypedEditSet,
    WorkspaceError,
)


def _git(*args: str, cwd: Path) -> None:
    subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        env={
            "GIT_AUTHOR_NAME": "test",
            "GIT_AUTHOR_EMAIL": "test@test.local",
            "GIT_COMMITTER_NAME": "test",
            "GIT_COMMITTER_EMAIL": "test@test.local",
            "PATH": "/usr/bin:/bin:/usr/local/bin",
            "HOME": str(cwd),
        },
    )


@pytest.fixture()
def upstream_repo(tmp_path: Path) -> tuple[Path, str]:
    """Create a tiny local git repo to act as the cloneable source."""

    if shutil.which("git") is None:
        pytest.skip("git not available")
    repo = tmp_path / "upstream"
    repo.mkdir()
    _git("init", "--initial-branch=main", "-q", cwd=repo)
    (repo / "pom.xml").write_text(
        "<project><groupId>g</groupId><artifactId>a</artifactId>"
        "<version>1</version></project>\n",
        encoding="utf-8",
    )
    (repo / "src" / "main" / "java").mkdir(parents=True)
    (repo / "src" / "main" / "java" / "A.java").write_text(
        "class A { static final String K = \"old\"; }\n", encoding="utf-8"
    )
    _git("add", "-A", cwd=repo)
    _git("commit", "-m", "init", "-q", cwd=repo)
    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return repo, sha


def _instance(repo: Path, sha: str) -> MigrationBenchInstance:
    return MigrationBenchInstance(
        instance_id="t__local",
        repo_url=str(repo),
        base_commit=sha,
        target_java=17,
    )


def test_prepare_clones_and_checkouts_base(
    upstream_repo: tuple[Path, str], tmp_path: Path
) -> None:
    repo, sha = upstream_repo
    ws = MigrationBenchWorkspaceV10(
        instance=_instance(repo, sha), root_dir=tmp_path / "ws"
    )
    ws.prepare()
    assert (ws.repo_dir / "pom.xml").exists()
    assert (ws.repo_dir / "src/main/java/A.java").exists()


def test_prepare_resets_existing_checkout_before_reuse(
    upstream_repo: tuple[Path, str], tmp_path: Path
) -> None:
    repo, sha = upstream_repo
    ws = MigrationBenchWorkspaceV10(
        instance=_instance(repo, sha), root_dir=tmp_path / "ws"
    )
    ws.prepare()
    ws.write_file("pom.xml", "STALE TARGET JAVA PATCH")
    ws.write_file("untracked.txt", "stale")

    ws.prepare()

    assert "STALE TARGET JAVA PATCH" not in ws.read_file("pom.xml")
    assert not (ws.repo_dir / "untracked.txt").exists()
    assert (ws.repo_dir / "pom.xml").read_text(encoding="utf-8").startswith("<project>")


def test_prepare_can_remove_stale_candidate_branches(
    upstream_repo: tuple[Path, str], tmp_path: Path
) -> None:
    repo, sha = upstream_repo
    ws = MigrationBenchWorkspaceV10(
        instance=_instance(repo, sha), root_dir=tmp_path / "ws"
    )
    stale = ws.branch_workspace("c1_llm")
    stale.write_file("pom.xml", "STALE BRANCH PATCH")

    ws.prepare(reset_branches=True)
    fresh = ws.branch_workspace("c1_llm")

    assert "STALE BRANCH PATCH" not in fresh.read_file("pom.xml")
    assert fresh.read_file("pom.xml").startswith("<project>")


def test_branch_workspace_is_isolated_copy(
    upstream_repo: tuple[Path, str], tmp_path: Path
) -> None:
    repo, sha = upstream_repo
    ws = MigrationBenchWorkspaceV10(
        instance=_instance(repo, sha), root_dir=tmp_path / "ws"
    )
    branch = ws.branch_workspace("b1")
    assert branch.repo_dir != ws.repo_dir
    assert (branch.repo_dir / "pom.xml").exists()
    branch.write_file("pom.xml", "MUTATED")
    assert (ws.repo_dir / "pom.xml").read_text(encoding="utf-8").startswith("<project>")
    assert branch.read_file("pom.xml") == "MUTATED"


def test_fork_branch_workspace_copies_from_source_branch(
    upstream_repo: tuple[Path, str], tmp_path: Path
) -> None:
    repo, sha = upstream_repo
    ws = MigrationBenchWorkspaceV10(
        instance=_instance(repo, sha), root_dir=tmp_path / "ws"
    )
    b1 = ws.branch_workspace("b1")
    b1.write_file("MARKER.txt", "b1-was-here")
    b2 = ws.fork_branch_workspace(source_branch_id="b1", branch_id="b2")
    assert b2.read_file("MARKER.txt") == "b1-was-here"
    b2.write_file("MARKER.txt", "b2-overwrote")
    assert b1.read_file("MARKER.txt") == "b1-was-here"


def test_fork_branch_workspace_skips_generated_build_outputs(
    upstream_repo: tuple[Path, str], tmp_path: Path
) -> None:
    repo, sha = upstream_repo
    ws = MigrationBenchWorkspaceV10(
        instance=_instance(repo, sha), root_dir=tmp_path / "ws"
    )
    b1 = ws.branch_workspace("b1")
    (b1.repo_dir / "target" / "classes").mkdir(parents=True)
    (b1.repo_dir / "target" / "classes" / "A.class").write_bytes(b"\xca\xfe")

    b2 = ws.fork_branch_workspace(source_branch_id="b1", branch_id="b2")

    assert not (b2.repo_dir / "target").exists()
    assert (b2.repo_dir / ".git").exists()


def test_cleanup_build_outputs_removes_targets_without_touching_git(
    upstream_repo: tuple[Path, str], tmp_path: Path
) -> None:
    repo, sha = upstream_repo
    ws = MigrationBenchWorkspaceV10(
        instance=_instance(repo, sha), root_dir=tmp_path / "ws"
    )
    branch = ws.branch_workspace("b1")
    (branch.repo_dir / "target").mkdir()
    (branch.repo_dir / "target" / "generated.txt").write_text("x", encoding="utf-8")
    (branch.repo_dir / "module" / "build").mkdir(parents=True)

    removed = branch.cleanup_build_outputs()

    assert "target" in removed
    assert "module/build" in removed
    assert not (branch.repo_dir / "target").exists()
    assert (branch.repo_dir / ".git").exists()


def test_apply_typed_edits_replace_text_count_must_match(
    upstream_repo: tuple[Path, str], tmp_path: Path
) -> None:
    repo, sha = upstream_repo
    ws = MigrationBenchWorkspaceV10(
        instance=_instance(repo, sha), root_dir=tmp_path / "ws"
    )
    branch = ws.branch_workspace("b1")
    edits = TypedEditSet(
        edits=[
            TypedEdit(
                type="replace_text",
                path="src/main/java/A.java",
                old="\"old\"",
                new="\"new\"",
                expected_replacements=1,
            )
        ]
    )
    result = branch.apply_typed_edits(edits)
    assert result.applied is True
    assert "src/main/java/A.java" in result.files_modified
    assert "\"new\"" in branch.read_file("src/main/java/A.java")


def test_apply_typed_edits_count_mismatch_blocks_apply(
    upstream_repo: tuple[Path, str], tmp_path: Path
) -> None:
    repo, sha = upstream_repo
    ws = MigrationBenchWorkspaceV10(
        instance=_instance(repo, sha), root_dir=tmp_path / "ws"
    )
    branch = ws.branch_workspace("b1")
    edits = TypedEditSet(
        edits=[
            TypedEdit(
                type="replace_text",
                path="src/main/java/A.java",
                old="DOES_NOT_EXIST",
                new="x",
                expected_replacements=1,
            )
        ]
    )
    result = branch.apply_typed_edits(edits)
    assert result.applied is False
    assert "replacement_count_mismatch" in result.failure_reason


def test_apply_typed_edits_write_file_creates_new_path(
    upstream_repo: tuple[Path, str], tmp_path: Path
) -> None:
    repo, sha = upstream_repo
    ws = MigrationBenchWorkspaceV10(
        instance=_instance(repo, sha), root_dir=tmp_path / "ws"
    )
    branch = ws.branch_workspace("b1")
    edits = TypedEditSet(
        edits=[
            TypedEdit(
                type="write_file",
                path="src/main/java/B.java",
                content="class B {}\n",
            )
        ]
    )
    result = branch.apply_typed_edits(edits)
    assert result.applied is True
    assert (branch.repo_dir / "src/main/java/B.java").exists()


def test_export_patch_records_diff_against_base(
    upstream_repo: tuple[Path, str], tmp_path: Path
) -> None:
    repo, sha = upstream_repo
    ws = MigrationBenchWorkspaceV10(
        instance=_instance(repo, sha), root_dir=tmp_path / "ws"
    )
    branch = ws.branch_workspace("b1")
    branch.apply_typed_edits(
        TypedEditSet(
            edits=[
                TypedEdit(
                    type="replace_text",
                    path="src/main/java/A.java",
                    old="\"old\"",
                    new="\"new\"",
                )
            ]
        )
    )
    patch_path = tmp_path / "out.diff"
    stats = branch.export_patch(patch_path)
    assert patch_path.exists()
    assert stats.patch_delivered is True
    assert stats.files_modified_count == 1
    assert stats.patch_lines_added >= 1


def test_safe_path_blocks_traversal(
    upstream_repo: tuple[Path, str], tmp_path: Path
) -> None:
    repo, sha = upstream_repo
    ws = MigrationBenchWorkspaceV10(
        instance=_instance(repo, sha), root_dir=tmp_path / "ws"
    )
    branch = ws.branch_workspace("b1")
    with pytest.raises(WorkspaceError):
        branch.read_file("../../etc/passwd")


def test_as_handle_exposes_workspace_metadata(
    upstream_repo: tuple[Path, str], tmp_path: Path
) -> None:
    repo, sha = upstream_repo
    ws = MigrationBenchWorkspaceV10(
        instance=_instance(repo, sha), root_dir=tmp_path / "ws"
    )
    branch = ws.branch_workspace("b1")
    handle = branch.as_handle(branch_id="b1")
    assert handle.instance_id == "t__local"
    assert handle.metadata["repo_url"] == str(repo)
    assert handle.metadata["base_commit"] == sha
    assert handle.metadata["branch_id"] == "b1"
    assert handle.metadata["target_java"] == 17
