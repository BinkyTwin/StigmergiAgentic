"""End-to-end consistency invariants for the V10 MigrationBench harness.

These integration tests prove the *honesty contract* of the V10 telemetry
pipeline:

1. The summary written live by the harness is byte-for-byte equal to the
   summary reconstructed by ``replay_summary_from_dir`` from the same
   campaign tree (no metric is invented).
2. ``strict_success=True`` implies the full chain is True
   (``patch_delivered`` ∧ ``patch_applies`` ∧ ``compile_success`` ∧
   ``test_success`` ∧ ``class_version_ok`` ∧ ``official_success``).
3. The presence/absence of the official evaluator is what flips
   ``strict_success`` between True and False — there is no diagnostic
   shortcut.
4. ``adapters_v10/`` does not import any legacy ``core/`` or
   ``adapters/`` symbol — i.e. the ``_synthesize_best_partial_payload``
   shortcut from V7.2 has no equivalent.
"""

from __future__ import annotations

import ast
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
from scripts.bench.telemetry import SCORE_EVENT, replay_summary_from_dir


REPO_ROOT = Path(__file__).resolve().parents[3]


# ---------------------------------------------------------------------------
# Local upstream fixture (no network, no real Maven)
# ---------------------------------------------------------------------------


def _git(*args: str, cwd: Path) -> None:
    subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        env={
            "GIT_AUTHOR_NAME": "smoke",
            "GIT_AUTHOR_EMAIL": "smoke@test.local",
            "GIT_COMMITTER_NAME": "smoke",
            "GIT_COMMITTER_EMAIL": "smoke@test.local",
            "PATH": "/usr/bin:/bin:/usr/local/bin",
            "HOME": str(cwd),
        },
    )


@pytest.fixture()
def upstream_repo(tmp_path: Path) -> tuple[Path, str]:
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
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return repo, sha


def _write_subset(path: Path, repo: Path, sha: str, instance_id: str = "smoke__local") -> None:
    path.write_text(
        json.dumps(
            {
                "instance_id": instance_id,
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


class _FakeCmd:
    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = ""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.runtime_seconds = 0.01

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def _patch_maven_and_class_versions(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        verifier_mod, "run_maven", lambda *a, **kw: _FakeCmd(returncode=0)
    )
    monkeypatch.setattr(
        MigrationBenchVerifier,
        "_collect_class_versions",
        lambda self, repo_dir: {61},
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_smoke_live_summary_equals_replay_summary(
    upstream_repo: tuple[Path, str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, sha = upstream_repo
    subset = tmp_path / "subset.jsonl"
    _write_subset(subset, repo, sha)
    out_dir = tmp_path / "campaign"

    _patch_maven_and_class_versions(monkeypatch)

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
    base_factory = registry.adapter_factories["migrationbench"]

    def factory(extras: dict[str, Any]):
        adapter = base_factory({**extras, "official_eval": False})
        adapter.verifier.official_evaluator = _OkEvaluator()
        return adapter

    registry.adapter_factories["migrationbench"] = factory

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

    live = BenchHarness(options, registry).run()
    replay = replay_summary_from_dir(out_dir)

    # 1. Live and replay summaries must be identical.
    assert replay.to_dict() == live.to_dict()

    # 2. strict_success implies every other signal True.
    assert live.strict_success_count == 1
    instance = live.instances[0]
    assert instance.strict_success is True
    for key in (
        "patch_delivered",
        "patch_applies",
        "compile_success",
        "test_success",
        "class_version_ok",
        "official_success",
    ):
        assert instance.signals[key] is True, key


def test_smoke_without_official_evaluator_blocks_strict_success(
    upstream_repo: tuple[Path, str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, sha = upstream_repo
    subset = tmp_path / "subset.jsonl"
    _write_subset(subset, repo, sha)
    out_dir = tmp_path / "campaign"

    _patch_maven_and_class_versions(monkeypatch)

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
    instance = summary.instances[0]
    # The local chain succeeds, but the official evaluator is absent →
    # strict_success must remain False, with no diagnostic shortcut.
    assert instance.signals["compile_success"] is True
    assert instance.signals["test_success"] is True
    assert instance.signals["class_version_ok"] is True
    assert instance.signals["official_success"] is False
    assert instance.signals["strict_success"] is False
    assert summary.strict_success_count == 0


def test_score_event_payload_contains_canonical_eight_signals(
    upstream_repo: tuple[Path, str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The score.completed payload must carry every canonical signal key."""

    from adapters_v10.migrationbench import SIGNAL_KEYS

    repo, sha = upstream_repo
    subset = tmp_path / "subset.jsonl"
    _write_subset(subset, repo, sha)
    out_dir = tmp_path / "campaign"
    _patch_maven_and_class_versions(monkeypatch)

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
    BenchHarness(options, default_registry()).run()

    eventlog = (out_dir / "events" / "smoke__local" / "eventlog.jsonl").read_text(
        encoding="utf-8"
    )
    score_lines = [
        json.loads(line)
        for line in eventlog.splitlines()
        if line.strip() and json.loads(line)["type"] == SCORE_EVENT
    ]
    assert score_lines, "expected at least one score.completed event"
    payload = score_lines[-1]["payload"]
    metrics = payload["score"]["metrics"]
    for key in SIGNAL_KEYS:
        assert key in metrics, f"missing canonical signal: {key}"


def test_no_passive_partial_payload_fallback_anywhere_in_adapters_v10() -> None:
    """The legacy V7 ``_synthesize_best_partial_payload`` shortcut must not exist.

    Looks for an actual function/method definition (or callable assignment)
    bearing the forbidden name. Mentioning the name in docstrings or
    comments to document its intentional absence is allowed.
    """

    forbidden = "_synthesize_best_partial_payload"
    violations: list[str] = []
    for path in (REPO_ROOT / "adapters_v10").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == forbidden:
                violations.append(f"{path.name}: def {node.name}")
            elif isinstance(node, ast.AsyncFunctionDef) and node.name == forbidden:
                violations.append(f"{path.name}: async def {node.name}")
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == forbidden:
                        violations.append(f"{path.name}: assign {target.id}")
    assert violations == [], (
        f"V7 fallback symbol leaked into adapters_v10: {violations}"
    )


def test_adapters_v10_does_not_import_legacy_core_or_adapters() -> None:
    """Reaffirm the cloison étanche from a higher-level integration angle."""

    forbidden_top_modules = {"core", "adapters"}
    violations: list[str] = []
    for path in (REPO_ROOT / "adapters_v10").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    head = alias.name.split(".")[0]
                    if head in forbidden_top_modules:
                        violations.append(f"{path.name}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom) and node.module:
                head = node.module.split(".")[0]
                if head in forbidden_top_modules:
                    violations.append(f"{path.name}: from {node.module}")
    assert violations == []
