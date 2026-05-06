from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from adapters_v10.migrationbench.adapter import MigrationBenchAdapterV10
from adapters_v10.migrationbench.context import MigrationContext
from core_v10.contracts import CandidateKind, RunInstance
from scripts.bench.providers import (
    deterministic_maven_target_java_edits,
    make_migrationbench_deterministic_provider,
    make_migrationbench_noop_repair_provider,
)


def _context(target_java: int = 17) -> MigrationContext:
    return MigrationContext(
        source_language="java",
        source_version=8,
        target_language="java",
        target_version=target_java,
        target_class_major={11: 55, 17: 61, 21: 65}[target_java],
        build_system="maven",
        migration_mode="minimal",
        dependency_policy="minimal",
    )


def test_deterministic_target_java_edits_picks_up_source_declarations() -> None:
    pom = (
        "<project>\n"
        "  <maven.compiler.source>1.8</maven.compiler.source>\n"
        "  <maven.compiler.target>1.8</maven.compiler.target>\n"
        "  <java.version>1.8</java.version>\n"
        "</project>\n"
    )
    edits = deterministic_maven_target_java_edits(
        ["pom.xml"],
        {"pom.xml": pom},
        _context(17),
    )
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


def test_deterministic_target_java_edits_skips_unrelated_pom() -> None:
    pom = "<project><groupId>g</groupId></project>"
    edits = deterministic_maven_target_java_edits(
        ["pom.xml"],
        {"pom.xml": pom},
        _context(17),
    )
    assert edits == []


def test_deterministic_replacement_table_is_complete() -> None:
    from adapters_v10.migrationbench.operators import target_java_replacements

    olds = {old for old, _ in target_java_replacements(_context(17))}
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


def test_provider_emits_target_java_candidate_against_real_workspace(
    upstream: tuple[Path, str], tmp_path: Path
) -> None:
    repo, sha = upstream
    adapter = MigrationBenchAdapterV10()
    instance = RunInstance(
        instance_id="t__local",
        adapter_name="migrationbench_v10",
        objective="migrate to target java",
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
    assert cand.payload["branch_id"] == "target_java_17"
    assert cand.origin == "builtin_deterministic_maven_target_java"
    edit_set = cand.payload["edit_set"]
    assert any(
        e["old"] == "<maven.compiler.source>1.8</maven.compiler.source>"
        for e in edit_set["edits"]
    )
