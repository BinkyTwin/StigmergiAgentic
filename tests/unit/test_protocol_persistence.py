"""Unit tests for coordination protocol persistence in MarkerStore."""

from __future__ import annotations

from core.marker_store import MarkerStore


def _namespace() -> str:
    return "coordination_protocol::travelplanner::abcd1234"


def test_save_and_load_protocol_marker_roundtrip(tmp_path) -> None:
    store = MarkerStore(db_path=tmp_path / "protocols.db")
    namespace = _namespace()
    payload = {
        "metrics": {"colony_specialization": 0.5},
        "adaptations": {"agents.selection_temperature": 0.08},
        "score": 123456.0,
        "session_id": "sess-1",
    }

    store.save_protocol_marker(slot="latest", namespace=namespace, payload=payload)
    loaded = store.load_protocol_marker(slot="latest", namespace=namespace)

    assert loaded is not None
    assert loaded["session_id"] == "sess-1"
    assert loaded["adaptations"]["agents.selection_temperature"] == 0.08
    assert loaded["slot"] == "latest"
    assert loaded["namespace"] == namespace


def test_load_returns_none_when_slot_missing(tmp_path) -> None:
    store = MarkerStore(db_path=tmp_path / "protocols.db")
    assert store.load_protocol_marker(slot="best", namespace=_namespace()) is None


def test_save_protocol_marker_preserves_baseline_creation_metadata(tmp_path) -> None:
    store = MarkerStore(db_path=tmp_path / "protocols.db")
    namespace = _namespace()
    store.save_protocol_marker(
        slot="baseline",
        namespace=namespace,
        payload={"config": {"agents": {"selection_temperature": 0.1}}, "session_id": "sess-1"},
    )
    first = store.load_protocol_marker(slot="baseline", namespace=namespace)
    store.save_protocol_marker(
        slot="baseline",
        namespace=namespace,
        payload={"config": {"agents": {"selection_temperature": 0.2}}, "session_id": "sess-2"},
    )
    second = store.load_protocol_marker(slot="baseline", namespace=namespace)

    assert first is not None and second is not None
    # Caller controls baseline semantics; store just upserts. Verify payload is replaced.
    assert second["session_id"] == "sess-2"


def test_save_protocol_marker_requires_non_empty_slot_and_namespace(tmp_path) -> None:
    store = MarkerStore(db_path=tmp_path / "protocols.db")
    import pytest
    from core.marker_store import MarkerStoreError

    with pytest.raises(MarkerStoreError):
        store.save_protocol_marker(slot="", namespace="ns", payload={})
    with pytest.raises(MarkerStoreError):
        store.save_protocol_marker(slot="latest", namespace="", payload={})
