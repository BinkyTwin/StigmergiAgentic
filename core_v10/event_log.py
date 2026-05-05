"""Append-only V10 event log and minimal replay helpers."""

from __future__ import annotations

import hashlib
import json
import shutil
import fcntl
from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

from core_v10.contracts import JsonDict, to_jsonable


def utc_now_iso() -> str:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class EventRecord:
    """Single append-only runtime event."""

    event_id: str
    sequence: int
    run_id: str
    instance_id: str
    event_type: str
    actor: str
    timestamp: str
    payload: JsonDict = field(default_factory=dict)
    hypothesis_id: str | None = None
    cost: JsonDict = field(default_factory=dict)
    links: JsonDict = field(default_factory=dict)

    def to_dict(self) -> JsonDict:
        """Return the event using the public JSON field names."""

        return {
            "event_id": self.event_id,
            "sequence": self.sequence,
            "run_id": self.run_id,
            "instance_id": self.instance_id,
            "timestamp": self.timestamp,
            "type": self.event_type,
            "actor": self.actor,
            "hypothesis_id": self.hypothesis_id,
            "payload": to_jsonable(self.payload),
            "cost": to_jsonable(self.cost),
            "links": to_jsonable(self.links),
        }

    @classmethod
    def from_dict(cls, data: JsonDict) -> EventRecord:
        """Build an event from the public JSON representation."""

        return cls(
            event_id=str(data["event_id"]),
            sequence=int(data["sequence"]),
            run_id=str(data["run_id"]),
            instance_id=str(data["instance_id"]),
            timestamp=str(data["timestamp"]),
            event_type=str(data["type"]),
            actor=str(data["actor"]),
            hypothesis_id=data.get("hypothesis_id"),
            payload=dict(data.get("payload") or {}),
            cost=dict(data.get("cost") or {}),
            links=dict(data.get("links") or {}),
        )


@dataclass(frozen=True)
class ReplaySnapshot:
    """Compact reconstruction of an event stream."""

    run_id: str | None
    event_count: int
    counts_by_type: dict[str, int]
    latest_by_type: dict[str, JsonDict]
    latest_by_hypothesis: dict[str, JsonDict]


def make_event_id(
    *,
    sequence: int,
    run_id: str,
    instance_id: str,
    event_type: str,
    actor: str,
    hypothesis_id: str | None,
    payload: JsonDict,
) -> str:
    """Create a stable event id from sequence and event content."""

    canonical = json.dumps(
        {
            "sequence": sequence,
            "run_id": run_id,
            "instance_id": instance_id,
            "event_type": event_type,
            "actor": actor,
            "hypothesis_id": hypothesis_id,
            "payload": to_jsonable(payload),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha1(canonical.encode("utf-8")).hexdigest()[:10]
    return f"evt_{sequence:06d}_{digest}"


class JsonlEventLog:
    """Simple append-only JSONL event log.

    JSONL is enough for V10 bootstrap tests and replay bundles. A SQLite backend
    can later implement the same semantics without changing strategy code.
    """

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock_path = self.path.with_suffix(self.path.suffix + ".lock")

    def append(
        self,
        *,
        run_id: str,
        instance_id: str,
        event_type: str,
        actor: str,
        payload: JsonDict | None = None,
        hypothesis_id: str | None = None,
        cost: JsonDict | None = None,
        links: JsonDict | None = None,
        timestamp: str | None = None,
    ) -> EventRecord:
        """Append and return one event record."""

        with self._exclusive_lock():
            payload = payload or {}
            sequence = self.next_sequence()
            event = EventRecord(
                event_id=make_event_id(
                    sequence=sequence,
                    run_id=run_id,
                    instance_id=instance_id,
                    event_type=event_type,
                    actor=actor,
                    hypothesis_id=hypothesis_id,
                    payload=payload,
                ),
                sequence=sequence,
                run_id=run_id,
                instance_id=instance_id,
                event_type=event_type,
                actor=actor,
                timestamp=timestamp or utc_now_iso(),
                hypothesis_id=hypothesis_id,
                payload=payload,
                cost=cost or {},
                links=links or {},
            )
            with self.path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(event.to_dict(), sort_keys=True) + "\n")
            return event

    def next_sequence(self) -> int:
        """Return the next append sequence number."""

        return len(self.read_all()) + 1

    def read_all(self) -> list[EventRecord]:
        """Read all events from disk."""

        if not self.path.exists():
            return []
        events: list[EventRecord] = []
        with self.path.open("r", encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, start=1):
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    event_data = json.loads(stripped)
                    events.append(EventRecord.from_dict(event_data))
                except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
                    raise ValueError(
                        f"invalid JSONL event at {self.path}:{line_number}"
                    ) from exc
        return events

    @contextmanager
    def _exclusive_lock(self):
        self._lock_path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock_path.open("a", encoding="utf-8") as lock_stream:
            fcntl.flock(lock_stream.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock_stream.fileno(), fcntl.LOCK_UN)

    def for_run(self, run_id: str) -> list[EventRecord]:
        """Read all events for one run."""

        return [event for event in self.read_all() if event.run_id == run_id]

    def replay(self, run_id: str | None = None) -> ReplaySnapshot:
        """Reconstruct a compact snapshot from logged events."""

        events = self.read_all()
        if run_id is not None:
            events = [event for event in events if event.run_id == run_id]
        return replay_events(events)

    def export_bundle(self, destination: Path | str) -> Path:
        """Export the event log with a manifest and return the bundle path."""

        bundle_path = Path(destination)
        bundle_path.mkdir(parents=True, exist_ok=True)
        events_path = bundle_path / "events.jsonl"
        if self.path.exists():
            shutil.copyfile(self.path, events_path)
        else:
            events_path.write_text("", encoding="utf-8")

        manifest = {
            "format": "stigmergiagentic.v10.event_log_bundle",
            "event_count": len(self.read_all()),
            "source": str(self.path),
            "events": "events.jsonl",
        }
        (bundle_path / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return bundle_path


def replay_events(events: Iterable[EventRecord]) -> ReplaySnapshot:
    """Replay events into a compact, deterministic snapshot."""

    ordered = sorted(events, key=lambda event: event.sequence)
    counts = Counter(event.event_type for event in ordered)
    latest_by_type: dict[str, JsonDict] = {}
    latest_by_hypothesis: dict[str, JsonDict] = {}
    run_ids = {event.run_id for event in ordered}

    for event in ordered:
        public_event = event.to_dict()
        latest_by_type[event.event_type] = public_event
        if event.hypothesis_id:
            latest_by_hypothesis[event.hypothesis_id] = public_event

    run_id = next(iter(run_ids)) if len(run_ids) == 1 else None
    return ReplaySnapshot(
        run_id=run_id,
        event_count=len(ordered),
        counts_by_type=dict(counts),
        latest_by_type=latest_by_type,
        latest_by_hypothesis=latest_by_hypothesis,
    )
