"""Export helpers for Sprint 3 run artifacts."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Mapping, Sequence


TICK_FIELDNAMES = [
    "tick",
    "any_agent_acted",
    "acted_scout",
    "acted_transformer",
    "acted_tester",
    "acted_validator",
    "files_total",
    "files_migrated",
    "files_validated",
    "files_failed",
    "files_needs_review",
    "total_tokens",
    "total_cost_usd",
    "total_ticks",
    "tokens_per_file",
    "cost_per_file_usd",
    "success_rate",
    "rollback_rate",
    "human_escalation_rate",
    "retry_resolution_rate",
    "starvation_count",
    "audit_completeness",
]


def ensure_output_dir(output_dir: Path) -> Path:
    """Create the output directory if missing."""
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def write_ticks_csv(path: Path, tick_rows: Sequence[Mapping[str, Any]]) -> None:
    """Write tick-level metrics as CSV."""
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=TICK_FIELDNAMES)
        writer.writeheader()
        for row in tick_rows:
            payload = {field: row.get(field) for field in TICK_FIELDNAMES}
            writer.writerow(payload)


def write_summary_json(path: Path, summary: Mapping[str, Any]) -> None:
    """Write run summary as JSON."""
    with path.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2, sort_keys=True)
        handle.write("\n")


def write_manifest_json(path: Path, manifest: Mapping[str, Any]) -> None:
    """Write run manifest as JSON."""
    with path.open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)
        handle.write("\n")
