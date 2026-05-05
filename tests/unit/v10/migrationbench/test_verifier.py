from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from adapters_v10.migrationbench import schemas as schemas_mod
from adapters_v10.migrationbench import verifier as verifier_mod
from adapters_v10.migrationbench import maven as maven_mod
from adapters_v10.migrationbench.schemas import (
    MigrationBenchInstance,
    PatchStats,
)
from adapters_v10.migrationbench.verifier import (
    LocalVerificationResult,
    MigrationBenchVerifier,
    OfficialEvaluator,
    OfficialVerificationResult,
    PatchApplyResult,
    SIGNAL_KEYS,
)
from adapters_v10.migrationbench.workspace import MigrationBenchWorkspaceV10
from core_v10.contracts import ValidationStatus


@dataclass
class _FakeCmdResult:
    returncode: int
    stdout: str = ""
    stderr: str = ""
    runtime_seconds: float = 0.01

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def _instance(target_java: int = 17, maximal: bool = False) -> MigrationBenchInstance:
    return MigrationBenchInstance(
        instance_id="t__local",
        repo_url="https://github.com/t/local",
        base_commit="deadbeef",
        target_java=target_java,
        migration_mode="maximal" if maximal else "minimal",
        stats={"num_test_cases": 2},
    )


def _make_branch(tmp_path: Path, instance: MigrationBenchInstance) -> MigrationBenchWorkspaceV10:
    branch = MigrationBenchWorkspaceV10(instance=instance, root_dir=tmp_path / "br")
    branch.repo_dir.mkdir(parents=True)
    return branch


def test_signal_keys_are_canonical_eight() -> None:
    assert SIGNAL_KEYS == (
        "patch_delivered",
        "patch_applies",
        "compile_success",
        "test_success",
        "class_version_ok",
        "dependency_policy_ok",
        "official_success",
        "strict_success",
    )


def test_strict_success_requires_full_chain() -> None:
    patch_stats = PatchStats(patch_delivered=True, files_modified_count=1)
    apply = PatchApplyResult(applies=True, reason="ok")
    local = LocalVerificationResult(
        compile_success=True,
        test_success=True,
        class_version_ok=True,
        dependency_policy_ok=None,
        class_versions=[61],
    )
    official = OfficialVerificationResult(
        official_success=True,
        ran=True,
        returncode=0,
        failure_reason="ok",
        command=[],
        stdout_tail="",
        stderr_tail="",
        log_path="",
        runtime_seconds=0.0,
    )
    signals = MigrationBenchVerifier.build_signals(
        patch_stats=patch_stats,
        patch_apply=apply,
        local=local,
        official=official,
        is_maximal=False,
    )
    assert signals["strict_success"] is True
    assert all(signals[k] is True for k in (
        "patch_delivered", "patch_applies", "compile_success",
        "test_success", "class_version_ok", "official_success",
    ))


def test_strict_success_blocked_by_missing_official() -> None:
    patch_stats = PatchStats(patch_delivered=True)
    apply = PatchApplyResult(applies=True, reason="ok")
    local = LocalVerificationResult(
        compile_success=True,
        test_success=True,
        class_version_ok=True,
    )
    signals = MigrationBenchVerifier.build_signals(
        patch_stats=patch_stats,
        patch_apply=apply,
        local=local,
        official=None,
        is_maximal=False,
    )
    assert signals["official_success"] is False
    assert signals["strict_success"] is False


def test_strict_success_blocked_by_failed_apply_even_if_official_ok() -> None:
    patch_stats = PatchStats(patch_delivered=True)
    apply = PatchApplyResult(applies=False, reason="git_apply_check_failed")
    local = LocalVerificationResult(
        compile_success=True, test_success=True, class_version_ok=True
    )
    official = OfficialVerificationResult(
        official_success=True, ran=True, returncode=0, failure_reason="ok",
        command=[], stdout_tail="", stderr_tail="", log_path="", runtime_seconds=0.0,
    )
    signals = MigrationBenchVerifier.build_signals(
        patch_stats=patch_stats,
        patch_apply=apply,
        local=local,
        official=official,
        is_maximal=False,
    )
    assert signals["patch_applies"] is False
    assert signals["strict_success"] is False


def test_strict_success_blocked_by_class_version_mismatch() -> None:
    patch_stats = PatchStats(patch_delivered=True)
    apply = PatchApplyResult(applies=True, reason="ok")
    local = LocalVerificationResult(
        compile_success=True, test_success=True, class_version_ok=False,
        class_versions=[52, 61],
    )
    official = OfficialVerificationResult(
        official_success=True, ran=True, returncode=0, failure_reason="ok",
        command=[], stdout_tail="", stderr_tail="", log_path="", runtime_seconds=0.0,
    )
    signals = MigrationBenchVerifier.build_signals(
        patch_stats=patch_stats, patch_apply=apply, local=local,
        official=official, is_maximal=False,
    )
    assert signals["class_version_ok"] is False
    assert signals["strict_success"] is False


def test_strict_success_requires_dependency_policy_when_maximal() -> None:
    patch_stats = PatchStats(patch_delivered=True)
    apply = PatchApplyResult(applies=True, reason="ok")
    local = LocalVerificationResult(
        compile_success=True, test_success=True, class_version_ok=True,
        dependency_policy_ok=False,
    )
    official = OfficialVerificationResult(
        official_success=True, ran=True, returncode=0, failure_reason="ok",
        command=[], stdout_tail="", stderr_tail="", log_path="", runtime_seconds=0.0,
    )
    signals = MigrationBenchVerifier.build_signals(
        patch_stats=patch_stats, patch_apply=apply, local=local,
        official=official, is_maximal=True,
    )
    assert signals["dependency_policy_ok"] is False
    assert signals["strict_success"] is False


def test_to_validation_result_status_mapping() -> None:
    local = LocalVerificationResult(compile_success=True, test_success=True)
    pass_signals = {k: True for k in SIGNAL_KEYS}
    pass_signals["dependency_policy_ok"] = None
    res = MigrationBenchVerifier.to_validation_result(
        candidate_id="c1", signals=pass_signals, local=local
    )
    assert res.status == ValidationStatus.PASSED

    official_fail_signals = dict(pass_signals)
    official_fail_signals.update(
        {"official_success": False, "strict_success": False}
    )
    res_official = MigrationBenchVerifier.to_validation_result(
        candidate_id="c1",
        signals=official_fail_signals,
        local=local,
        require_official_success=True,
    )
    assert res_official.status == ValidationStatus.PARTIAL

    partial_signals = dict(pass_signals)
    partial_signals.update({"strict_success": False, "test_success": False})
    res2 = MigrationBenchVerifier.to_validation_result(
        candidate_id="c1", signals=partial_signals, local=local
    )
    assert res2.status == ValidationStatus.PARTIAL

    fail_local = LocalVerificationResult(compile_success=False, test_success=False)
    fail_signals = {k: False for k in SIGNAL_KEYS}
    res3 = MigrationBenchVerifier.to_validation_result(
        candidate_id="c1", signals=fail_signals, local=fail_local
    )
    assert res3.status == ValidationStatus.FAILED
    assert res3.errors  # non-empty


def test_verify_local_compile_failure_short_circuits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    instance = _instance()
    branch = _make_branch(tmp_path, instance)
    calls: list[str] = []

    def fake_run_maven(repo_dir: Path, cmd: str, *, timeout_seconds: float) -> Any:
        calls.append(cmd)
        if "dependency:resolve" in cmd:
            return _FakeCmdResult(returncode=0)
        if "compile" in cmd:
            return _FakeCmdResult(
                returncode=1, stdout="[ERROR] cannot find symbol\n[ERROR] compilation failure"
            )
        return _FakeCmdResult(returncode=0)

    monkeypatch.setattr(verifier_mod, "run_maven", fake_run_maven)

    verifier = MigrationBenchVerifier()
    local = verifier.verify_local(branch)
    assert local.compile_success is False
    assert local.test_success is False
    assert local.class_version_ok is False
    assert local.failure_taxonomy == "compile_error"
    assert any("dependency:resolve" in c for c in calls)
    assert any("compile" in c for c in calls)
    assert not any(" test" in c for c in calls)


def test_verify_local_dependency_failure_taxonomy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    instance = _instance()
    branch = _make_branch(tmp_path, instance)

    def fake_run_maven(repo_dir: Path, cmd: str, *, timeout_seconds: float) -> Any:
        return _FakeCmdResult(returncode=1, stdout="Could not resolve dependencies")

    monkeypatch.setattr(verifier_mod, "run_maven", fake_run_maven)
    verifier = MigrationBenchVerifier()
    local = verifier.verify_local(branch)
    assert local.failure_taxonomy == "dependency_resolution_error"
    assert local.compile_success is False


def test_official_evaluator_missing_returns_explicit_failure(tmp_path: Path) -> None:
    instance = _instance()
    evaluator = OfficialEvaluator(migrationbench_root=tmp_path / "missing")
    assert evaluator.available is False
    res = evaluator.evaluate(
        instance=instance,
        patch_path=tmp_path / "p.diff",
        output_dir=tmp_path / "out",
    )
    assert res.ran is False
    assert res.official_success is False
    assert res.failure_reason == "official_evaluator_missing"


def test_official_evaluator_parses_success_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "MigrationBench"
    (root / "src" / "migration_bench").mkdir(parents=True)
    (root / "src" / "migration_bench" / "run_eval.py").write_text("pass\n")

    captured: dict[str, Any] = {}

    def fake_run_command(command, *, cwd=None, env=None, timeout_seconds=None):
        captured["command"] = command
        return _FakeCmdResult(returncode=0, stdout="...\nSuccess = True\n")

    monkeypatch.setattr(verifier_mod, "run_command", fake_run_command)

    patch = tmp_path / "p.diff"
    patch.write_text("diff --git a/x b/x\n+a\n", encoding="utf-8")
    evaluator = OfficialEvaluator(migrationbench_root=root)
    res = evaluator.evaluate(
        instance=_instance(),
        patch_path=patch,
        output_dir=tmp_path / "out",
    )
    assert res.ran is True
    assert res.official_success is True
    assert res.failure_reason == "ok"
    assert "--require_compiled_java_major_version" in captured["command"]
    assert "61" in captured["command"]


def test_official_evaluator_handles_failure_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "MigrationBench"
    (root / "src" / "migration_bench").mkdir(parents=True)
    (root / "src" / "migration_bench" / "run_eval.py").write_text("pass\n")

    monkeypatch.setattr(
        verifier_mod, "run_command",
        lambda *a, **kw: _FakeCmdResult(returncode=0, stdout="Success = False\n"),
    )

    patch = tmp_path / "p.diff"
    patch.write_text("diff\n+x", encoding="utf-8")
    evaluator = OfficialEvaluator(migrationbench_root=root)
    res = evaluator.evaluate(
        instance=_instance(), patch_path=patch, output_dir=tmp_path / "out"
    )
    assert res.official_success is False
    assert res.failure_reason == "official_eval_failed"
