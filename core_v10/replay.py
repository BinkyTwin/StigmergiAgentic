"""Replay utilities for V10 runtime artifacts."""

from __future__ import annotations

from pathlib import Path

from core_v10.event_log import EventRecord, JsonlEventLog, ReplaySnapshot, replay_events


def replay_jsonl(path: Path | str, run_id: str | None = None) -> ReplaySnapshot:
    """Replay a JSONL event log into a compact snapshot."""

    return JsonlEventLog(path).replay(run_id=run_id)


__all__ = [
    "EventRecord",
    "JsonlEventLog",
    "ReplaySnapshot",
    "replay_events",
    "replay_jsonl",
]
