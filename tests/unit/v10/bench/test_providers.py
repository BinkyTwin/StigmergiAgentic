from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from adapters_v10.migrationbench.adapter import MigrationBenchAdapterV10
from core_v10.contracts import CandidateKind, Observation, RunInstance
from scripts.bench.providers import (
    JAVA17_POM_REPLACEMENTS,
    deterministic_pom17_edits,
    make_migrationbench_deterministic_provider,
    make_migrationbench_noop_repair_provider,
)


def test_deterministic_pom17_edits_picks_up_java8_declarations() -> None:
    pom = (
        "<project>\n"
        "  <maven.compiler.source>1.8</maven.compiler.source>\n"
        "  <maven.compiler.target>1.8</maven.compiler.target>\n"
        "  <java.version>1.8</java.version>\n"
        "</project>\n"
    )
    edits = deterministic_pom17_edits(["pom.xml"], {"pom.xml": pom})
    olds = {edit["old"] for edit in edits}
    expected_olds = {
        "<maven.compiler.source>1.8</maven.compiler.source>",
        "<maven.compiler.target>1.8</maven.compiler.target>",
        "<java.version>1.8</java.version>",
    }
    assert expected_olds.issubset(olds)
    for edit in edits:
        assert edit["type"] == "replace_text"
        assert edit["path"] == "pom.xml"
        assert edit["expected_replacements"] == 1


def test_deterministic_pom17_edits_skips_unrelated_pom() -> None:
    pom = "<project><groupId>g</groupId></project>"
    edits = deterministic_pom17_edits(["pom.xml"], {"pom.xml": pom})
    assert edits == []


def test_deterministic_replacement_table_is_complete() -> None:
    olds = {old for old, _ in JAVA17_POM_REPLACEMENTS}
    assert "<source>1.8</source>" in olds
    assert "<release>8</release>" in olds


def test_make_repair_provider_returns_empty() -> None:
    provider = make_migrationbench_noop_repair_provider(None, {})
    assert list(provider(None, None, None, None)) == []


def test_make_deterministic_provider_rejects_wrong_adapter() -> None:
    with pytest.raises(TypeError):
        make_migrationbench_deterministic_provider(object(), {})


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
def upstream(tmp_path: Path) -> tuple[Path, str]:
    if shutil.which("git") is None:
        pytest.skip("git not available")
    repo = tmp_path / "upstream"
    repo.mkdir()
    _git("init", "--initial-branch=main", "-q", cwd=repo)
    (repo / "pom.xml").write_text(
        "<project>\n"
        "  <maven.compiler.source>1.8</maven.compiler.source>\n"
        "  <maven.compiler.target>1.8</maven.compiler.target>\n"
        "</project>\n",
        encoding="utf-8",
    )
    _git("add", "-A", cwd=repo)
    _git("commit", "-m", "init", "-q", cwd=repo)
    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo, check=True, capture_output=True, text=True,
    ).stdout.strip()
    return repo, sha


def test_provider_emits_pom17_candidate_against_real_workspace(
    upstream: tuple[Path, str], tmp_path: Path
) -> None:
    repo, sha = upstream
    adapter = MigrationBenchAdapterV10()
    instance = RunInstance(
        instance_id="t__local",
        adapter_name="migrationbench_v10",
        objective="migrate to java 17",
        metadata={
            "workspace_root": str(tmp_path / "ws"),
            "instance": {
                "instance_id": "t__local",
                "repo_url": str(repo),
                "base_commit": sha,
                "target_java": 17,
            },
        },
    )
    handle = adapter.setup(instance)
    obs = adapter.observe(handle)
    provider = make_migrationbench_deterministic_provider(adapter, {})
    candidates = list(provider(obs, instance))
    assert len(candidates) == 1
    cand = candidates[0]
    assert cand.kind == CandidateKind.PATCH
    assert cand.payload["branch_id"] == "pom17"
    edit_set = cand.payload["edit_set"]
    assert any(
        e["old"] == "<maven.compiler.source>1.8</maven.compiler.source>"
        for e in edit_set["edits"]
    )
