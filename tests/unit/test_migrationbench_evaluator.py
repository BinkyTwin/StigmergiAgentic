from __future__ import annotations

from pathlib import Path

from adapters.migrationbench.evaluator import MigrationBenchEvaluator, build_strict_contract
from adapters.migrationbench.schemas import MigrationBenchInstance, PatchStats


def _instance() -> MigrationBenchInstance:
    return MigrationBenchInstance(
        instance_id="x",
        repo_url="https://github.com/example/repo",
        base_commit="abc",
    )


def test_empty_patch_never_strict_success(tmp_path: Path) -> None:
    patch = tmp_path / "patch.diff"
    patch.write_text("", encoding="utf-8")
    evaluator = MigrationBenchEvaluator(run_official=False)
    official = evaluator.evaluate_patch(
        instance=_instance(),
        patch_path=patch,
        output_dir=tmp_path / "official",
        patch_stats=PatchStats(patch_delivered=False),
        patch_applies=False,
        patch_apply_reason="empty_patch",
    )
    contract = build_strict_contract(
        instance=_instance(),
        framework="test",
        provider="deepseek",
        model="deepseek-v4-flash",
        seed=42,
        patch_path=patch,
        patch_stats=PatchStats(patch_delivered=False),
        patch_applies=False,
        patch_apply_reason="empty_patch",
        official=official,
    )
    assert contract["strict_success"] is False
    assert contract["failure_reason"] == "empty_patch"


def test_official_success_requires_patch_applies(tmp_path: Path) -> None:
    patch = tmp_path / "patch.diff"
    patch.write_text("diff --git a/a b/a\n", encoding="utf-8")
    official = {"official_success": True, "failure_reason": "ok"}
    contract = build_strict_contract(
        instance=_instance(),
        framework="test",
        provider="deepseek",
        model="deepseek-v4-flash",
        seed=42,
        patch_path=patch,
        patch_stats=PatchStats(patch_delivered=True),
        patch_applies=False,
        patch_apply_reason="patch_does_not_apply",
        official=official,
    )
    assert contract["strict_success"] is False
    assert contract["failure_reason"] == "patch_does_not_apply"
