"""Unit tests for audit log."""

from __future__ import annotations

from pathlib import Path

from core.audit import AuditEvent, AuditLog, utc_timestamp


def test_audit_append_and_read(tmp_path: Path) -> None:
    path = tmp_path / "pheromones" / "audit_log.jsonl"
    log = AuditLog(path)

    event = AuditEvent(
        timestamp=utc_timestamp(),
        agent_id="agent-1",
        action="upsert",
        marker_id="m-1",
        marker_type="task",
        target="file.py",
        before={},
        after={"state": "pending"},
    )
    log.append(event)

    events = log.read_all()
    assert len(events) == 1
    assert events[0].marker_id == "m-1"


def test_audit_log_is_append_only(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    log = AuditLog(path)

    for marker_id in ("m-1", "m-2"):
        log.append(
            AuditEvent(
                timestamp=utc_timestamp(),
                agent_id="agent-1",
                action="upsert",
                marker_id=marker_id,
                marker_type="task",
                target="file.py",
                before={},
                after={"state": "pending"},
            )
        )

    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line]
    assert len(lines) == 2


def test_audit_event_keeps_before_after_payloads(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    log = AuditLog(path)

    event = AuditEvent(
        timestamp=utc_timestamp(),
        agent_id="agent-2",
        action="update",
        marker_id="m-3",
        marker_type="quality",
        target="run-1",
        before={"state": "active", "confidence": 0.4},
        after={"state": "completed", "confidence": 0.8},
    )
    log.append(event)
    loaded = log.read_all()[0]

    assert loaded.before["state"] == "active"
    assert loaded.after["state"] == "completed"


def test_audit_event_tick_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    log = AuditLog(path)

    event = AuditEvent(
        timestamp=utc_timestamp(),
        agent_id="system",
        action="decay",
        marker_id="m-4",
        marker_type="task",
        target="x",
        before={"intensity": 1.0},
        after={"intensity": 0.95},
        tick=9,
    )
    log.append(event)

    loaded = log.read_all()[0]
    assert loaded.tick == 9
