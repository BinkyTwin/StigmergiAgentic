"""V10 unified bench harness.

The harness drives a ``DomainAdapterV10`` through a ``StrategyRunner`` and
materialises a campaign tree on disk: ``manifest.json``, per-instance
``events/<id>/eventlog.jsonl`` and ``hypotheses/<id>/graph.json`` files,
``artifacts/<id>/<candidate>/{patch.diff, signals.json}``, ``runs.jsonl``,
and ``summary.json``.

The summary is *always* derived from the EventLog by
``scripts.bench.telemetry.build_summary`` so that ``summary.json`` is
structurally equal to a replay reconstruction (proven by L7 integration
tests).
"""

from __future__ import annotations

from scripts.bench.artifacts import (
    Manifest,
    RunRow,
    load_subset,
    write_manifest,
    write_runs_jsonl,
)
from scripts.bench.telemetry import (
    InstanceSummary,
    Summary,
    build_summary,
    replay_summary_from_dir,
)

__all__ = [
    "InstanceSummary",
    "Manifest",
    "RunRow",
    "Summary",
    "build_summary",
    "load_subset",
    "replay_summary_from_dir",
    "write_manifest",
    "write_runs_jsonl",
]
