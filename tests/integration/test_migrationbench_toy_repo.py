from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _toy_repo(tmp_path: Path) -> tuple[Path, str]:
    repo = tmp_path / "toy-java8"
    repo.mkdir()
    (repo / "pom.xml").write_text(
        "<project><modelVersion>4.0.0</modelVersion>"
        "<groupId>x</groupId><artifactId>x</artifactId><version>1</version>"
        "<properties><maven.compiler.source>1.8</maven.compiler.source>"
        "<maven.compiler.target>1.8</maven.compiler.target></properties></project>",
        encoding="utf-8",
    )
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    subprocess.run(["git", "add", "pom.xml"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
    return repo, commit


def test_query_export_dependency_baseline_on_toy_repo(tmp_path: Path) -> None:
    repo, commit = _toy_repo(tmp_path)
    instance = {
        "instance_id": "toy_java8",
        "repo_url": str(repo),
        "base_commit": commit,
        "target_java": 17,
        "migration_mode": "minimal",
        "source": "synthetic_unit_integration_only",
        "stratum": {"repo_size": "small", "build_complexity": "single-module"},
    }
    instance_json = tmp_path / "instance.json"
    instance_json.write_text(json.dumps(instance), encoding="utf-8")
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_migrationbench_query_export.py",
            "--framework",
            "dependency_only_script",
            "--instance-json",
            str(instance_json),
            "--out-dir",
            str(tmp_path / "out"),
            "--workspace-root",
            str(tmp_path / "workspaces"),
            "--skip-official-eval",
            "--force",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["patch_delivered"] is True
    assert payload["patch_applies"] is True
    assert payload["strict_success"] is False
    assert payload["failure_reason"] == "official_eval_not_run"
