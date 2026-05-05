from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from adapters_v10.migrationbench import verifier as verifier_mod
from adapters_v10.migrationbench.adapter import MigrationBenchAdapterV10
from adapters_v10.migrationbench.schemas import (
    MigrationBenchInstance,
    TypedEdit,
    TypedEditSet,
)
from adapters_v10.migrationbench.verifier import (
    MigrationBenchVerifier,
    OfficialVerificationResult,
)
from core_v10.contracts import (
    ArtifactStatus,
    Candidate,
    CandidateKind,
    RunInstance,
    ValidationStatus,
)


@dataclass
class _Cmd:
    returncode: int
    stdout: str = ""
    stderr: str = ""
    runtime_seconds: float = 0.01

    @property
    def ok(self) -> bool:
        return self.returncode == 0


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
        "<project>\n  <maven.compiler.source>1.8</maven.compiler.source>\n"
        "  <maven.compiler.target>1.8</maven.compiler.target>\n</project>\n",
        encoding="utf-8",
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


def _make_run_instance(repo: Path, sha: str, tmp_path: Path) -> RunInstance:
    return RunInstance(
        instance_id="t__local",
        adapter_name="migrationbench_v10",
        objective="migrate to java 17",
        metadata={
            "workspace_root": str(tmp_path / "ws"),
            "artifacts_dir": str(tmp_path / "artifacts"),
            "instance": MigrationBenchInstance(
                instance_id="t__local",
                repo_url=str(repo),
                base_commit=sha,
                target_java=17,
                stats={"num_test_cases": 0},
            ).model_dump(),
        },
    )


def _patch_candidate() -> Candidate:
    edits = TypedEditSet(
        edits=[
            TypedEdit(
                type="replace_text",
                path="pom.xml",
                old="<maven.compiler.source>1.8</maven.compiler.source>",
                new="<maven.compiler.source>17</maven.compiler.source>",
            ),
            TypedEdit(
                type="replace_text",
                path="pom.xml",
                old="<maven.compiler.target>1.8</maven.compiler.target>",
                new="<maven.compiler.target>17</maven.compiler.target>",
            ),
        ]
    )
    return Candidate(
        candidate_id="c1",
        kind=CandidateKind.PATCH,
        payload={"branch_id": "b1", "edits": edits.model_dump()},
        origin="test",
    )


def test_adapter_setup_observe_capabilities(
    upstream: tuple[Path, str], tmp_path: Path
) -> None:
    repo, sha = upstream
    adapter = MigrationBenchAdapterV10()
    handle = adapter.setup(_make_run_instance(repo, sha, tmp_path))
    assert handle.instance_id == "t__local"
    assert handle.metadata["target_class_major"] == 61
    obs = adapter.observe(handle)
    assert "pom.xml" in obs.data["pom_files"]
    caps = adapter.capabilities()
    kinds = {c.kind for c in caps}
    assert {"proposer", "applier", "validator", "finalizer"}.issubset(kinds)


def test_adapter_apply_unsupported_kind(
    upstream: tuple[Path, str], tmp_path: Path
) -> None:
    repo, sha = upstream
    adapter = MigrationBenchAdapterV10()
    handle = adapter.setup(_make_run_instance(repo, sha, tmp_path))
    cand = Candidate(
        candidate_id="c0",
        kind=CandidateKind.TEXT,
        payload={},
        origin="test",
    )
    res = adapter.apply(cand, handle)
    assert res.applied is False
    assert "unsupported candidate kind" in res.summary


def test_adapter_apply_writes_branch_workspace(
    upstream: tuple[Path, str], tmp_path: Path
) -> None:
    repo, sha = upstream
    adapter = MigrationBenchAdapterV10()
    handle = adapter.setup(_make_run_instance(repo, sha, tmp_path))
    res = adapter.apply(_patch_candidate(), handle)
    assert res.applied is True
    branch_root = res.workspace.root
    assert (branch_root / "repo" / "pom.xml").exists()
    assert (
        "<maven.compiler.source>17</maven.compiler.source>"
        in (branch_root / "repo" / "pom.xml").read_text(encoding="utf-8")
    )


def test_adapter_validate_returns_partial_when_compile_ok_but_official_absent(
    upstream: tuple[Path, str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, sha = upstream
    adapter = MigrationBenchAdapterV10()
    handle = adapter.setup(_make_run_instance(repo, sha, tmp_path))

    def fake_run_maven(repo_dir: Path, cmd: str, *, timeout_seconds: float) -> Any:
        return _Cmd(returncode=0)

    monkeypatch.setattr(verifier_mod, "run_maven", fake_run_maven)
    monkeypatch.setattr(
        MigrationBenchVerifier,
        "_collect_class_versions",
        lambda self, repo_dir: {61},
    )

    cand = _patch_candidate()
    apply_result = adapter.apply(cand, handle)
    assert apply_result.applied is True
    val = adapter.validate(cand, apply_result.workspace)
    assert val.signals["compile_success"] is True
    assert val.signals["test_success"] is True
    assert val.signals["class_version_ok"] is True
    assert val.signals["official_success"] is False
    assert val.signals["strict_success"] is False
    # patch_applies might be True (we exported a real diff)
    assert val.metadata["patch_path"].endswith("patch.diff")
    assert val.metadata["verification_cleaned"] is True
    assert not Path(val.metadata["verification_root"]).exists()


def test_adapter_diagnose_emits_recommendations_for_compile_error(
    upstream: tuple[Path, str], tmp_path: Path
) -> None:
    adapter = MigrationBenchAdapterV10()
    repo, sha = upstream
    handle = adapter.setup(_make_run_instance(repo, sha, tmp_path))
    from core_v10.contracts import ValidationResult

    val = ValidationResult(
        candidate_id="c1",
        status=ValidationStatus.FAILED,
        validator_name="migrationbench_v10",
        signals={
            "patch_delivered": True,
            "patch_applies": True,
            "compile_success": False,
            "test_success": False,
            "class_version_ok": False,
            "dependency_policy_ok": None,
            "official_success": False,
            "strict_success": False,
        },
        summary="compile_error",
        raw_output="[ERROR] cannot find symbol",
    )
    feedback = adapter.diagnose(val, handle)
    assert feedback.failure_type == "compile_error"
    assert any(
        a.get("action") == "fix_compile_error" for a in feedback.recommended_next_actions
    )
    assert "do not repeat" in feedback.anti_actions[0]
    # ADR 2026-05-04 (piste 4): preserve_existing_tests is appended to every
    # non-success diagnose so the rule is traceable in feedback.created.
    assert "preserve_existing_tests" in feedback.anti_actions


def test_adapter_finalize_strict_success_full_chain(
    upstream: tuple[Path, str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, sha = upstream
    adapter = MigrationBenchAdapterV10()
    handle = adapter.setup(_make_run_instance(repo, sha, tmp_path))

    monkeypatch.setattr(
        verifier_mod, "run_maven", lambda *a, **kw: _Cmd(returncode=0)
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

        def evaluate(self, **kwargs):
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

    adapter.verifier.official_evaluator = _OkEvaluator()
    cand = _patch_candidate()
    apply_result = adapter.apply(cand, handle)
    artifact = adapter.finalize(cand, apply_result.workspace)
    assert artifact.status == ArtifactStatus.DELIVERED
    assert artifact.metadata["signals"]["strict_success"] is True
    assert artifact.metadata["verification_cleaned"] is True
    score = adapter.score(artifact)
    assert score.strict_success is True
    assert score.metrics["official_success"] is True
    assert score.metrics["artifact_delivered"] is True


def test_adapter_finalize_blocks_strict_success_when_official_missing(
    upstream: tuple[Path, str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, sha = upstream
    adapter = MigrationBenchAdapterV10()  # no official evaluator
    handle = adapter.setup(_make_run_instance(repo, sha, tmp_path))

    monkeypatch.setattr(verifier_mod, "run_maven", lambda *a, **kw: _Cmd(returncode=0))
    monkeypatch.setattr(
        MigrationBenchVerifier,
        "_collect_class_versions",
        lambda self, repo_dir: {61},
    )

    cand = _patch_candidate()
    apply_result = adapter.apply(cand, handle)
    artifact = adapter.finalize(cand, apply_result.workspace)
    assert artifact.metadata["signals"]["compile_success"] is True
    assert artifact.metadata["signals"]["official_success"] is False
    assert artifact.metadata["signals"]["strict_success"] is False
    score = adapter.score(artifact)
    assert score.strict_success is False


def test_adapter_score_handles_missing_signals_metadata() -> None:
    from core_v10.contracts import ArtifactResult

    adapter = MigrationBenchAdapterV10()
    artifact = ArtifactResult(
        candidate_id="c1",
        status=ArtifactStatus.MISSING,
        artifacts={},
        metadata={},
    )
    score = adapter.score(artifact)
    assert score.strict_success is False
    assert score.metrics["reason"] == "signals_missing"
