"""Lightweight cleanup helpers for MigrationBench runners."""

from __future__ import annotations

import shutil
from pathlib import Path


def clean_stigmergic_artifacts(out_dir: Path) -> None:
    """Remove per-instance marker/audit/output state before a forced rerun."""
    out_dir.mkdir(parents=True, exist_ok=True)
    artifacts_dir = out_dir / "artifacts"
    if artifacts_dir.exists():
        shutil.rmtree(artifacts_dir)
    for name in [
        "markers.db",
        "markers.db-wal",
        "markers.db-shm",
        "audit_log.jsonl",
    ]:
        path = out_dir / name
        if path.exists():
            path.unlink()
