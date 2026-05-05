from __future__ import annotations

import subprocess
from pathlib import Path

from adapters.migrationbench.evaluator import MigrationBenchEvaluator
from adapters.migrationbench.schemas import MigrationBenchInstance
from adapters.migrationbench.scientific_baselines import (
    run_dependency_only_script,
    run_no_change,
)


def _repo(tmp_path: Path) -> tuple[Path, str]:
    repo = tmp_path / "source"
    repo.mkdir()
    (repo / "pom.xml").write_text(
        "<project><properties><java.version>1.8</java.version></properties></project>",
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
    )


def test_no_change_emits_empty_patch_failure(tmp_path: Path) -> None:
    repo, commit = _repo(tmp_path)
    result = run_no_change(
        instance=_instance(repo, commit),
        workspace_root=tmp_path / "workspace",
        output_dir=tmp_path / "out",
        evaluator=MigrationBenchEvaluator(run_official=False),
        force=True,
    )
    assert result["patch_delivered"] is False
    assert result["strict_success"] is False
    assert result["failure_reason"] == "empty_patch"
    assert (tmp_path / "out" / "patch.diff").read_text(encoding="utf-8") == ""


def test_dependency_only_script_emits_applicable_patch(tmp_path: Path) -> None:
    repo, commit = _repo(tmp_path)
    result = run_dependency_only_script(
        instance=_instance(repo, commit),
        workspace_root=tmp_path / "workspace",
        output_dir=tmp_path / "out",
        evaluator=MigrationBenchEvaluator(run_official=False),
        force=True,
    )
    assert result["patch_delivered"] is True
    assert result["patch_applies"] is True
    assert result["strict_success"] is False
    assert result["failure_reason"] == "official_eval_not_run"
