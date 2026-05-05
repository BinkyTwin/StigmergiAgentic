from __future__ import annotations

import subprocess
from pathlib import Path

from core.marker import Marker
from adapters.migrationbench.adapter import MigrationBenchAdapter
from adapters.migrationbench.evaluator import MigrationBenchEvaluator
from adapters.migrationbench.schemas import MigrationBenchInstance, TypedEdit, TypedEditSet


def _marker(marker_id: str, marker_type: str, payload: dict) -> Marker:
    return Marker(
        id=marker_id,
        marker_type=marker_type,
        target=marker_id,
        intensity=1.0,
        state="terminal",
        payload=payload,
        created_by="test",
        created_at="2026-01-01T00:00:00+00:00",
        updated_by="test",
        updated_at="2026-01-01T00:00:00+00:00",
    )


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


def test_evaluate_run_ignores_lesson_marker_for_final_contract() -> None:
    adapter = MigrationBenchAdapter()
    lesson = _marker(
        "lesson::migrationbench::x::finalize_patch",
        "lesson",
        {"lesson": "not the benchmark contract", "quality_score": 1.0},
    )
    final = _marker(
        "migrationbench::x::finalize_patch",
        "task",
        {
            "artifact_delivered": True,
            "patch_applies": True,
            "official_success": True,
            "strict_success": True,
            "failure_reason": "ok",
        },
    )

    result = adapter.evaluate_run({"markers": [lesson, final]})

    assert result["strict_success_rate"] == 1.0
    assert result["failure_reason"] == "ok"
    assert result["final_contract"]["strict_success"] is True


def test_v7_best_partial_exports_patch_and_runs_strict_contract(tmp_path: Path, monkeypatch) -> None:
    repo, commit = _git_repo(tmp_path)
    instance = _instance(repo, commit)
    artifact_dir = tmp_path / "artifacts"
    config = {
        "llm": {"provider": "deepseek", "model": "deepseek-v4-flash"},
        "migrationbench": {
            "framework": "stigmergic_v7_repair_colony",
            "workflow": "v7_repair_colony",
            "instance": instance.model_dump(),
            "workspace_dir": str(tmp_path / "workspace"),
            "artifact_dir": str(artifact_dir),
            "run_official_eval": True,
            "official_root": str(tmp_path / "official_root"),
        },
    }
    adapter = MigrationBenchAdapter(config=config)
    workspace = adapter.create_workspace(config)
    edits = TypedEditSet(
        edits=[
            TypedEdit(
                type="replace_text",
                path="pom.xml",
                old="<maven.compiler.source>1.8</maven.compiler.source>",
                new="<maven.compiler.source>17</maven.compiler.source>",
            )
        ]
    )
    branch = workspace.branch_workspace("b1", force=True)
    assert branch.apply_typed_edits(edits).applied is True

    def fake_evaluate_patch(self, **kwargs):
        patch_path = Path(kwargs["patch_path"])
        assert patch_path.exists()
        assert kwargs["patch_stats"].patch_delivered is True
        assert kwargs["patch_applies"] is True
        return {
            "official_success": True,
            "official_eval_ran": True,
            "failure_reason": "ok",
            "build_success": True,
            "test_success": True,
            "compiled_major_version_ok": True,
            "test_count_non_decreasing": True,
            "dependency_policy_ok": None,
        }

    monkeypatch.setattr(MigrationBenchEvaluator, "evaluate_patch", fake_evaluate_patch)
    partial = _marker(
        "migrationbench::local::patch::b1",
        "patch_hypothesis",
        {
            "objective_id": "migrationbench::local",
            "branch_id": "b1",
            "attempt": 0,
            "typed_edits": edits.model_dump(),
            "patch_applies": True,
            "quality_score": 0.4,
            "failure_taxonomy": "build_failure",
        },
    )

    result = adapter.evaluate_run({"markers": [partial]})

    contract = result["final_contract"]
    assert contract["best_partial_finalization"] is True
    assert contract["artifact_delivered"] is True
    assert contract["patch_delivered"] is True
    assert contract["patch_applies"] is True
    assert contract["strict_success"] is True
    assert contract["failure_reason"] == "ok"
    assert Path(contract["patch_path"]) == artifact_dir / "patch.diff"
    assert (artifact_dir / "patch.diff").read_text(encoding="utf-8").strip()
