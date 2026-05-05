"""Manifest, subset loader, and per-run row helpers for the V10 bench harness."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class Manifest:
    """Frozen description of one campaign launch."""

    campaign_id: str
    adapter_name: str
    strategy_name: str
    subset_path: str
    instance_ids: list[str]
    out_dir: str
    started_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    seed: int = 42
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RunRow:
    """One row in ``runs.jsonl`` — minimal view of a single instance run."""

    instance_id: str
    strategy_name: str
    stop_reason: str
    strict_success: bool
    selected_hypothesis_id: str | None
    candidate_count: int
    signals: dict[str, Any]
    artifact_paths: dict[str, str]


def load_subset(path: Path | str) -> list[dict[str, Any]]:
    """Load a JSONL benchmark subset into a list of records."""

    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"subset file not found: {path}")
    records: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        records.append(json.loads(line))
    return records


def write_manifest(out_dir: Path | str, manifest: Manifest) -> Path:
    """Serialize a :class:`Manifest` next to the campaign outputs."""

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = asdict(manifest)
    target = out_dir / "manifest.json"
    target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


def write_runs_jsonl(out_dir: Path | str, rows: Iterable[RunRow]) -> Path:
    """Serialize ``runs.jsonl`` (one JSON line per instance run)."""

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / "runs.jsonl"
    with target.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(asdict(row), sort_keys=True) + "\n")
    return target


def read_runs_jsonl(out_dir: Path | str) -> list[RunRow]:
    """Read a previously written ``runs.jsonl`` back into :class:`RunRow` items."""

    target = Path(out_dir) / "runs.jsonl"
    rows: list[RunRow] = []
    if not target.exists():
        return rows
    for line in target.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        data = json.loads(line)
        rows.append(
            RunRow(
                instance_id=str(data["instance_id"]),
                strategy_name=str(data["strategy_name"]),
                stop_reason=str(data["stop_reason"]),
                strict_success=bool(data["strict_success"]),
                selected_hypothesis_id=data.get("selected_hypothesis_id"),
                candidate_count=int(data["candidate_count"]),
                signals=dict(data.get("signals") or {}),
                artifact_paths=dict(data.get("artifact_paths") or {}),
            )
        )
    return rows


__all__ = [
    "Manifest",
    "RunRow",
    "load_subset",
    "read_runs_jsonl",
    "write_manifest",
    "write_runs_jsonl",
]
