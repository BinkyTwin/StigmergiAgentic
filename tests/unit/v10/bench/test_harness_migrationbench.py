from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from adapters_v10.migrationbench import verifier as verifier_mod
from adapters_v10.migrationbench.verifier import (
    MigrationBenchVerifier,
    OfficialVerificationResult,
)
from scripts.bench.harness import BenchHarness, HarnessOptions, default_registry
from scripts.bench.telemetry import replay_summary_from_dir


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


class _FakeCmd:
    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = ""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.runtime_seconds = 0.01

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def test_default_registry_includes_migrationbench() -> None:
    registry = default_registry()
    assert "migrationbench" in registry.adapter_factories
    assert "migrationbench" in registry.candidate_provider_factories
    assert "migrationbench" in registry.repair_provider_factories
    assert "migrationbench" in registry.run_instance_factories


def test_smoke_local_pipeline_reaches_strict_success_with_mocked_maven(
    upstream: tuple[Path, str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End-to-end harness run on one local instance, no LLM, no real Maven."""

    repo, sha = upstream
    subset = tmp_path / "smoke.jsonl"
    subset.write_text(
        json.dumps(
            {
                "instance_id": "t__local",
                "repo_url": str(repo),
                "base_commit": sha,
                "target_java": 17,
                "migration_mode": "minimal",
                "stats": {"num_test_cases": 0},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    out_dir = tmp_path / "out"

    monkeypatch.setattr(
        verifier_mod, "run_maven", lambda *a, **kw: _FakeCmd(returncode=0)
    )
    monkeypatch.setattr(
        MigrationBenchVerifier,
        "_collect_class_versions",
        lambda self, repo_dir: {61},
    )

    class _OkEvaluator:
        @property
        def available(self) -> bool:
            return True

        def evaluate(self, **kwargs: Any) -> OfficialVerificationResult:
            return OfficialVerificationResult(
                official_success=True,
                ran=True,
                returncode=0,
                failure_reason="ok",
                command=["fake"],
                stdout_tail="Success = True",
                stderr_tail="",
                log_path="",
                runtime_seconds=0.0,
            )

    registry = default_registry()
    original_factory = registry.adapter_factories["migrationbench"]

    def patched_factory(extras: dict[str, Any]):
        adapter = original_factory({**extras, "official_eval": False})
        adapter.verifier.official_evaluator = _OkEvaluator()
        return adapter

    registry.adapter_factories["migrationbench"] = patched_factory

    options = HarnessOptions(
        adapter_name="migrationbench",
        strategy_name="branching_repair",
        subset_path=subset,
        out_dir=out_dir,
        max_candidates=1,
        max_repair_rounds=0,
        extras={
            "out_dir": str(out_dir),
            "workspace_root_root": str(tmp_path / "ws"),
            "artifacts_root": str(out_dir / "artifacts"),
            "official_eval": False,
            "prepare": True,
        },
    )

    summary = BenchHarness(options, registry).run()
    assert summary.instance_count == 1
    assert summary.strict_success_count == 1
    assert summary.by_signal["patch_delivered"] == 1
    assert summary.by_signal["compile_success"] == 1
    assert summary.by_signal["test_success"] == 1
    assert summary.by_signal["official_success"] == 1
    assert summary.by_signal["strict_success"] == 1

    assert (out_dir / "manifest.json").exists()
    assert (out_dir / "runs.jsonl").exists()
    assert (out_dir / "summary.json").exists()
    assert (out_dir / "events" / "t__local" / "eventlog.jsonl").exists()
    assert (out_dir / "hypotheses" / "t__local" / "graph.json").exists()

    replay = replay_summary_from_dir(out_dir)
    assert replay.to_dict() == summary.to_dict()


def test_smoke_local_pipeline_records_infra_failed_when_evaluator_missing(
    upstream: tuple[Path, str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without official evaluator the chain must surface strict_success=False."""

    repo, sha = upstream
    subset = tmp_path / "smoke.jsonl"
    subset.write_text(
        json.dumps(
            {
                "instance_id": "t__local",
                "repo_url": str(repo),
                "base_commit": sha,
                "target_java": 17,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    out_dir = tmp_path / "out"

    monkeypatch.setattr(
        verifier_mod, "run_maven", lambda *a, **kw: _FakeCmd(returncode=0)
    )
    monkeypatch.setattr(
        MigrationBenchVerifier,
        "_collect_class_versions",
        lambda self, repo_dir: {61},
    )

    options = HarnessOptions(
        adapter_name="migrationbench",
        strategy_name="branching_repair",
        subset_path=subset,
        out_dir=out_dir,
        extras={
            "out_dir": str(out_dir),
            "workspace_root_root": str(tmp_path / "ws"),
            "artifacts_root": str(out_dir / "artifacts"),
            "official_eval": False,
            "prepare": True,
        },
    )
    summary = BenchHarness(options, default_registry()).run()
    assert summary.strict_success_count == 0
    instance = summary.instances[0]
    assert instance.signals["compile_success"] is True
    assert instance.signals["official_success"] is False
    assert instance.signals["strict_success"] is False
