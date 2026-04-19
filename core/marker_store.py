"""SQLite-backed marker store for generic stigmergic coordination."""

from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping

from .audit import AuditEvent, AuditLog, utc_timestamp
from .decay import decay_inhibition, decay_intensity_by_type
from .guardrails import GuardrailEngine, ScopeLockError
from .marker import Marker
from .reinforcement import frequentation_boost


class MarkerStoreError(RuntimeError):
    """Raised when marker store operations fail."""


class MarkerStore:
    """Transactional marker store with WAL journaling and audit logging."""

    def __init__(
        self,
        db_path: str | Path,
        audit_path: str | Path | None = None,
        guardrails: GuardrailEngine | None = None,
        max_retry_count: int = 3,
        traceability: bool = True,
        session_id: str | None = None,
        session_isolation: bool = False,
    ) -> None:
        raw_db_path = Path(db_path)
        if session_isolation:
            if not session_id:
                raise MarkerStoreError(
                    "session_id is required when session isolation is enabled"
                )
            self.db_path = raw_db_path.parent / session_id / raw_db_path.name
        else:
            self.db_path = raw_db_path
        self.session_id = session_id
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        if audit_path is None:
            audit_path = self.db_path.parent / "audit_log.jsonl"

        self.audit_log = AuditLog(audit_path)
        self.guardrails = guardrails or GuardrailEngine()
        self.max_retry_count = int(max_retry_count)
        self.traceability = bool(traceability)
        self.last_decay_pruned_count = 0

        self._initialize_database()

    def upsert_marker(self, marker: Marker, agent_id: str) -> Marker:
        """Insert or update one marker in an atomic transaction."""
        timestamp = utc_timestamp()
        marker_to_save = self._copy_marker(marker)
        marker_to_save.updated_by = agent_id
        marker_to_save.updated_at = timestamp

        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            before = self._get_marker_in_tx(conn, marker_to_save.id)

            if before is not None:
                if before.lock_owner and before.lock_owner != agent_id:
                    raise ScopeLockError(
                        f"Marker {marker_to_save.id} is locked by {before.lock_owner}"
                    )
                marker_to_save.created_by = before.created_by
                marker_to_save.created_at = before.created_at
                if not marker_to_save.last_active_at:
                    marker_to_save.last_active_at = (
                        before.last_active_at or before.updated_at
                    )
            else:
                marker_to_save.created_by = marker_to_save.created_by or agent_id
                marker_to_save.created_at = marker_to_save.created_at or timestamp
                if not marker_to_save.last_active_at:
                    marker_to_save.last_active_at = (
                        marker_to_save.updated_at or marker_to_save.created_at or timestamp
                    )

            self.guardrails.validate_traceability(
                agent_id=agent_id,
                timestamp=marker_to_save.updated_at,
                enabled=self.traceability,
            )

            if self.guardrails.enforce_retry_limit(
                marker_to_save.retry_count,
                self.max_retry_count,
            ):
                marker_to_save.state = "skipped"

            self._upsert_in_tx(conn, marker_to_save)
            after = self._get_marker_in_tx(conn, marker_to_save.id)
            conn.execute("COMMIT")

        if after is None:
            raise MarkerStoreError("Marker upsert succeeded but row cannot be read")

        self._append_audit(
            agent_id=agent_id,
            action="upsert",
            marker_id=after.id,
            marker_type=after.marker_type,
            target=after.target,
            before=before,
            after=after,
            tick=None,
        )
        return after

    def get_marker(self, marker_id: str) -> Marker | None:
        """Fetch one marker by ID."""
        with self._connect() as conn:
            return self._get_marker_in_tx(conn, marker_id)

    def get_by_type_target(self, marker_type: str, target: str) -> Marker | None:
        """Fetch the most recently updated marker by type + target."""
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM markers
                WHERE marker_type = ? AND target = ?
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (marker_type, target),
            ).fetchone()
            if row is None:
                return None
            return self._row_to_marker(row)

    def query_markers(self, **filters: Any) -> list[Marker]:
        """Query markers with SQL-backed filtering operators.

        Supported operators: eq (implicit), gt, gte, lt, lte, in.
        """
        where_sql, params, residual = self._build_sql_filters(filters)
        query = "SELECT * FROM markers"
        if where_sql:
            query = f"{query} WHERE {where_sql}"
        query = f"{query} ORDER BY updated_at"

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()

        markers = [self._row_to_marker(row) for row in rows]
        if not residual:
            return markers
        return [marker for marker in markers if self._matches_filters(marker, residual)]

    def acquire_lock(self, marker_id: str, agent_id: str, tick: int) -> bool:
        """Acquire marker lock if unlocked or already owned by the caller."""
        timestamp = utc_timestamp()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            before = self._get_marker_in_tx(conn, marker_id)
            if before is None:
                conn.execute("COMMIT")
                return False

            if before.lock_owner not in {None, agent_id}:
                self._record_lock_event_in_tx(
                    conn=conn,
                    marker_id=marker_id,
                    agent_id=agent_id,
                    tick=tick,
                    acquired=False,
                )
                conn.execute("COMMIT")
                return False

            after = self._copy_marker(before)
            after.lock_owner = agent_id
            after.lock_tick = int(tick)
            after.updated_by = agent_id
            after.updated_at = timestamp

            self._upsert_in_tx(conn, after)
            self._record_lock_event_in_tx(
                conn=conn,
                marker_id=marker_id,
                agent_id=agent_id,
                tick=tick,
                acquired=True,
            )
            conn.execute("COMMIT")

        self._append_audit(
            agent_id=agent_id,
            action="acquire_lock",
            marker_id=after.id,
            marker_type=after.marker_type,
            target=after.target,
            before=before,
            after=after,
            tick=int(tick),
        )
        return True

    def release_lock(self, marker_id: str, agent_id: str) -> bool:
        """Release marker lock when owned by the caller."""
        timestamp = utc_timestamp()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            before = self._get_marker_in_tx(conn, marker_id)
            if before is None:
                conn.execute("COMMIT")
                return False

            if before.lock_owner != agent_id:
                conn.execute("COMMIT")
                return False

            after = self._copy_marker(before)
            after.lock_owner = None
            after.lock_tick = None
            after.updated_by = agent_id
            after.updated_at = timestamp

            self._upsert_in_tx(conn, after)
            conn.execute("COMMIT")

        self._append_audit(
            agent_id=agent_id,
            action="release_lock",
            marker_id=after.id,
            marker_type=after.marker_type,
            target=after.target,
            before=before,
            after=after,
            tick=None,
        )
        return True

    def apply_decay(self, current_tick: int, config: Mapping[str, Any]) -> int:
        """Apply configured decay to marker intensity and inhibition."""
        markers_cfg = dict(config.get("markers", {}))
        decay_type = str(markers_cfg.get("decay_type", "exponential"))
        decay_rate = float(markers_cfg.get("decay_rate", 0.05))
        default_decay_rate = float(markers_cfg.get("default_decay_rate", decay_rate))
        decay_rates_by_type = dict(markers_cfg.get("decay_rates_by_type", {}))
        inhibition_decay_rate = float(markers_cfg.get("inhibition_decay_rate", 0.08))
        prune_threshold_raw = markers_cfg.get("prune_threshold")
        prune_threshold = (
            None if prune_threshold_raw is None else float(prune_threshold_raw)
        )
        self.last_decay_pruned_count = 0

        clamp_raw = markers_cfg.get("intensity_clamp", [0.1, 1.0])
        clamp = (float(clamp_raw[0]), float(clamp_raw[1]))

        terminal_states = {"terminal", "skipped", "escalated"}

        changed = 0
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            rows = conn.execute("SELECT * FROM markers").fetchall()
            updates: list[tuple[Marker, Marker]] = []

            for row in rows:
                before = self._row_to_marker(row)
                if before.state in terminal_states:
                    continue

                after = self._copy_marker(before)
                after.intensity = decay_intensity_by_type(
                    value=before.intensity,
                    marker_type=before.marker_type,
                    decay_rates=decay_rates_by_type,
                    default_rate=default_decay_rate,
                    decay_type=decay_type,
                    clamp=clamp,
                )
                after.inhibition = decay_inhibition(
                    value=before.inhibition,
                    inhibition_decay_rate=inhibition_decay_rate,
                )

                if (
                    before.intensity == after.intensity
                    and before.inhibition == after.inhibition
                ):
                    continue

                after.updated_by = "system_decay"
                after.updated_at = utc_timestamp()
                self._upsert_in_tx(conn, after)
                updates.append((before, after))

            conn.execute("COMMIT")

        for before, after in updates:
            changed += 1
            self._append_audit(
                agent_id="system_decay",
                action="decay",
                marker_id=after.id,
                marker_type=after.marker_type,
                target=after.target,
                before=before,
                after=after,
                tick=int(current_tick),
            )

        pruned = 0
        if prune_threshold is not None:
            pruned = self.prune_markers(prune_threshold)
        self.last_decay_pruned_count = int(pruned)

        return changed

    def apply_frequentation(self, current_tick: int, config: Mapping[str, Any]) -> int:
        """Apply read-traffic reinforcement boosts for one tick."""
        reinforcement_cfg = dict(config.get("reinforcement", {}))
        frequentation_cfg = dict(reinforcement_cfg.get("frequentation", {}))
        if not bool(frequentation_cfg.get("enabled", False)):
            return 0

        read_boost = float(frequentation_cfg.get("read_boost", 0.01))
        completion_boost = float(frequentation_cfg.get("completion_boost", 0.05))
        max_boost_per_tick = float(frequentation_cfg.get("max_boost_per_tick", 0.1))
        diminishing_factor = float(frequentation_cfg.get("diminishing_factor", 0.5))

        changed = 0
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            read_rows = conn.execute(
                """
                SELECT marker_id, COUNT(*) AS read_count
                FROM marker_reads
                WHERE tick = ?
                GROUP BY marker_id
                """,
                (int(current_tick),),
            ).fetchall()

            updates: list[tuple[Marker, Marker]] = []
            for row in read_rows:
                marker_id = str(row["marker_id"])
                read_count = int(row["read_count"])
                before = self._get_marker_in_tx(conn, marker_id)
                if before is None:
                    continue

                boost = frequentation_boost(
                    read_count=read_count,
                    base_boost=read_boost,
                    max_boost=max_boost_per_tick,
                    diminishing_factor=diminishing_factor,
                )
                if before.state in {"completed", "verified", "terminal"}:
                    boost = min(max_boost_per_tick, boost + max(0.0, completion_boost))
                if boost <= 0.0:
                    continue

                after = self._copy_marker(before)
                after.intensity = min(1.0, max(0.0, float(before.intensity) + float(boost)))
                timestamp = utc_timestamp()
                after.updated_by = "system_frequentation"
                after.updated_at = timestamp
                after.last_active_at = timestamp

                self._upsert_in_tx(conn, after)
                updates.append((before, after))

            conn.execute("COMMIT")

        for before, after in updates:
            changed += 1
            self._append_audit(
                agent_id="system_frequentation",
                action="frequentation",
                marker_id=after.id,
                marker_type=after.marker_type,
                target=after.target,
                before=before,
                after=after,
                tick=int(current_tick),
            )
        return changed

    def maintain_locks(self, current_tick: int, ttl: int) -> list[str]:
        """Release expired locks and requeue active items."""
        released_marker_ids: list[str] = []

        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            rows = conn.execute(
                "SELECT * FROM markers WHERE lock_owner IS NOT NULL AND lock_tick IS NOT NULL"
            ).fetchall()

            updates: list[tuple[Marker, Marker]] = []
            for row in rows:
                before = self._row_to_marker(row)
                if before.lock_tick is None:
                    continue
                if not self.guardrails.enforce_lock_ttl(
                    lock_tick=before.lock_tick,
                    current_tick=current_tick,
                    ttl=ttl,
                ):
                    continue

                after = self._copy_marker(before)
                after.lock_owner = None
                after.lock_tick = None
                if after.state == "active":
                    after.state = "pending"
                    after.retry_count = int(after.retry_count) + 1
                    if self.guardrails.enforce_retry_limit(
                        after.retry_count,
                        self.max_retry_count,
                    ):
                        after.state = "skipped"
                after.updated_by = "system_ttl"
                after.updated_at = utc_timestamp()

                self._upsert_in_tx(conn, after)
                updates.append((before, after))
                released_marker_ids.append(after.id)

            conn.execute("COMMIT")

        for before, after in updates:
            self._append_audit(
                agent_id="system_ttl",
                action="ttl_release",
                marker_id=after.id,
                marker_type=after.marker_type,
                target=after.target,
                before=before,
                after=after,
                tick=int(current_tick),
            )

        return released_marker_ids

    def snapshot(self) -> dict[str, list[Marker]]:
        """Return an immutable-like grouped snapshot by marker type."""
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM markers ORDER BY marker_type, updated_at").fetchall()

        grouped: dict[str, list[Marker]] = defaultdict(list)
        for row in rows:
            marker = self._row_to_marker(row)
            grouped[marker.marker_type].append(marker)
        return dict(grouped)

    def record_read(self, marker_id: str, agent_id: str, tick: int) -> None:
        """Persist one agent read event for a marker on one tick."""
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO marker_reads (
                    marker_id, agent_id, tick, read_at
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    str(marker_id),
                    str(agent_id),
                    int(tick),
                    utc_timestamp(),
                ),
            )

    def record_lock_attempt(
        self,
        *,
        marker_id: str,
        agent_id: str,
        tick: int,
        acquired: bool,
    ) -> None:
        """Persist one explicit lock-attempt outcome for a marker."""
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            self._record_lock_event_in_tx(
                conn=conn,
                marker_id=marker_id,
                agent_id=agent_id,
                tick=tick,
                acquired=acquired,
            )
            conn.execute("COMMIT")

    def read_count(self, marker_id: str, since_tick: int = 0) -> int:
        """Return the number of recorded reads for one marker."""
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) AS total
                FROM marker_reads
                WHERE marker_id = ? AND tick >= ?
                """,
                (str(marker_id), int(since_tick)),
            ).fetchone()
        if row is None:
            return 0
        return int(row["total"])

    def lock_stats_snapshot(self, since_tick: int = 0) -> dict[str, dict[str, Any]]:
        """Return aggregated lock-attempt telemetry per marker."""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    marker_id,
                    COUNT(*) AS attempts,
                    SUM(CASE WHEN acquired = 0 THEN 1 ELSE 0 END) AS conflicts,
                    MAX(CASE WHEN acquired = 0 THEN tick END) AS last_conflict_tick,
                    MAX(CASE WHEN acquired = 1 THEN tick END) AS last_success_tick
                FROM marker_lock_events
                WHERE tick >= ?
                GROUP BY marker_id
                """,
                (int(since_tick),),
            ).fetchall()

        stats: dict[str, dict[str, Any]] = {}
        for row in rows:
            attempts = int(row["attempts"] or 0)
            conflicts = int(row["conflicts"] or 0)
            conflict_rate = (
                float(conflicts) / float(attempts)
                if attempts > 0
                else 0.0
            )
            stats[str(row["marker_id"])] = {
                "attempts": attempts,
                "conflicts": conflicts,
                "conflict_rate": conflict_rate,
                "last_conflict_tick": (
                    None
                    if row["last_conflict_tick"] is None
                    else int(row["last_conflict_tick"])
                ),
                "last_success_tick": (
                    None
                    if row["last_success_tick"] is None
                    else int(row["last_success_tick"])
                ),
            }
        return stats

    def lock_stats(self, marker_id: str, since_tick: int = 0) -> dict[str, Any]:
        """Return aggregated lock-attempt telemetry for one marker."""
        return dict(
            self.lock_stats_snapshot(since_tick=since_tick).get(
                str(marker_id),
                {
                    "attempts": 0,
                    "conflicts": 0,
                    "conflict_rate": 0.0,
                    "last_conflict_tick": None,
                    "last_success_tick": None,
                },
            )
        )

    def prune_markers(self, threshold: float) -> int:
        """Delete markers whose intensity is strictly below threshold."""
        cutoff = float(threshold)
        if cutoff <= 0.0:
            return 0
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            cursor = conn.execute(
                "DELETE FROM markers WHERE intensity < ?",
                (cutoff,),
            )
            deleted = int(cursor.rowcount or 0)
            conn.execute("COMMIT")
        return deleted

    def _initialize_database(self) -> None:
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute("PRAGMA foreign_keys=ON;")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS markers (
                    id TEXT PRIMARY KEY,
                    marker_type TEXT NOT NULL,
                    target TEXT NOT NULL,
                    intensity REAL NOT NULL,
                    state TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_by TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_active_at TEXT NOT NULL DEFAULT '',
                    lock_owner TEXT,
                    lock_tick INTEGER,
                    inhibition REAL NOT NULL,
                    retry_count INTEGER NOT NULL,
                    history_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_markers_type_state ON markers(marker_type, state)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_markers_target ON markers(target)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_markers_lock_owner ON markers(lock_owner)"
            )
            self._ensure_column(
                conn=conn,
                table_name="markers",
                column_name="last_active_at",
                definition="TEXT NOT NULL DEFAULT ''",
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS marker_reads (
                    marker_id TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    tick INTEGER NOT NULL,
                    read_at TEXT NOT NULL,
                    PRIMARY KEY (marker_id, agent_id, tick)
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_marker_reads_tick ON marker_reads(tick)"
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS marker_lock_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    marker_id TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    tick INTEGER NOT NULL,
                    acquired INTEGER NOT NULL,
                    recorded_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_marker_lock_events_tick ON marker_lock_events(tick)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_marker_lock_events_marker ON marker_lock_events(marker_id)"
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _upsert_in_tx(self, conn: sqlite3.Connection, marker: Marker) -> None:
        conn.execute(
            """
            INSERT INTO markers (
                id, marker_type, target, intensity, state, payload_json,
                created_by, created_at, updated_by, updated_at, last_active_at,
                lock_owner, lock_tick, inhibition, retry_count, history_json
            ) VALUES (
                :id, :marker_type, :target, :intensity, :state, :payload_json,
                :created_by, :created_at, :updated_by, :updated_at, :last_active_at,
                :lock_owner, :lock_tick, :inhibition, :retry_count, :history_json
            )
            ON CONFLICT(id) DO UPDATE SET
                marker_type = excluded.marker_type,
                target = excluded.target,
                intensity = excluded.intensity,
                state = excluded.state,
                payload_json = excluded.payload_json,
                updated_by = excluded.updated_by,
                updated_at = excluded.updated_at,
                last_active_at = excluded.last_active_at,
                lock_owner = excluded.lock_owner,
                lock_tick = excluded.lock_tick,
                inhibition = excluded.inhibition,
                retry_count = excluded.retry_count,
                history_json = excluded.history_json
            """,
            {
                "id": marker.id,
                "marker_type": marker.marker_type,
                "target": marker.target,
                "intensity": marker.intensity,
                "state": marker.state,
                "payload_json": json.dumps(marker.payload, sort_keys=True),
                "created_by": marker.created_by,
                "created_at": marker.created_at,
                "updated_by": marker.updated_by,
                "updated_at": marker.updated_at,
                "last_active_at": marker.last_active_at,
                "lock_owner": marker.lock_owner,
                "lock_tick": marker.lock_tick,
                "inhibition": marker.inhibition,
                "retry_count": marker.retry_count,
                "history_json": json.dumps(marker.history),
            },
        )

    def _get_marker_in_tx(self, conn: sqlite3.Connection, marker_id: str) -> Marker | None:
        row = conn.execute("SELECT * FROM markers WHERE id = ?", (marker_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_marker(row)

    def _row_to_marker(self, row: sqlite3.Row) -> Marker:
        return Marker(
            id=str(row["id"]),
            marker_type=str(row["marker_type"]),
            target=str(row["target"]),
            intensity=float(row["intensity"]),
            state=str(row["state"]),
            payload=json.loads(str(row["payload_json"])),
            created_by=str(row["created_by"]),
            created_at=str(row["created_at"]),
            updated_by=str(row["updated_by"]),
            updated_at=str(row["updated_at"]),
            last_active_at=str(row["last_active_at"] or ""),
            lock_owner=(None if row["lock_owner"] is None else str(row["lock_owner"])),
            lock_tick=(None if row["lock_tick"] is None else int(row["lock_tick"])),
            inhibition=float(row["inhibition"]),
            retry_count=int(row["retry_count"]),
            history=[str(item) for item in json.loads(str(row["history_json"]))],
        )

    def _append_audit(
        self,
        agent_id: str,
        action: str,
        marker_id: str,
        marker_type: str,
        target: str,
        before: Marker | None,
        after: Marker,
        tick: int | None,
    ) -> None:
        event = AuditEvent(
            timestamp=utc_timestamp(),
            agent_id=agent_id,
            action=action,
            marker_id=marker_id,
            marker_type=marker_type,
            target=target,
            before={} if before is None else before.to_dict(),
            after=after.to_dict(),
            tick=tick,
        )
        self.audit_log.append(event)

    def _copy_marker(self, marker: Marker) -> Marker:
        return Marker.from_dict(marker.to_dict())

    def _build_sql_filters(
        self,
        filters: Mapping[str, Any],
    ) -> tuple[str, list[Any], dict[str, Any]]:
        supported_columns = {
            "id",
            "marker_type",
            "target",
            "intensity",
            "state",
            "created_by",
            "created_at",
            "updated_by",
            "updated_at",
            "last_active_at",
            "lock_owner",
            "lock_tick",
            "inhibition",
            "retry_count",
        }
        where_clauses: list[str] = []
        params: list[Any] = []
        residual: dict[str, Any] = {}

        for filter_key, expected in filters.items():
            field_name, operator = self._parse_filter(filter_key)
            if field_name not in supported_columns:
                residual[filter_key] = expected
                continue

            column = field_name
            if operator == "eq":
                if expected is None:
                    where_clauses.append(f"{column} IS NULL")
                else:
                    where_clauses.append(f"{column} = ?")
                    params.append(expected)
            elif operator == "gt":
                where_clauses.append(f"{column} > ?")
                params.append(expected)
            elif operator == "gte":
                where_clauses.append(f"{column} >= ?")
                params.append(expected)
            elif operator == "lt":
                where_clauses.append(f"{column} < ?")
                params.append(expected)
            elif operator == "lte":
                where_clauses.append(f"{column} <= ?")
                params.append(expected)
            elif operator == "in":
                if not isinstance(expected, (list, tuple, set)):
                    raise MarkerStoreError("Operator 'in' expects a list/tuple/set")
                values = list(expected)
                if not values:
                    return "1 = 0", [], {}
                placeholders = ",".join("?" for _ in values)
                where_clauses.append(f"{column} IN ({placeholders})")
                params.extend(values)
            else:
                residual[filter_key] = expected

        return " AND ".join(where_clauses), params, residual

    def _matches_filters(self, marker: Marker, filters: Mapping[str, Any]) -> bool:
        marker_data = marker.to_dict()
        for filter_key, expected in filters.items():
            field_name, operator = self._parse_filter(filter_key)
            value = marker_data.get(field_name)

            if operator == "eq" and value != expected:
                return False
            if operator == "gt" and not self._compare_numeric(value, expected, "gt"):
                return False
            if operator == "gte" and not self._compare_numeric(value, expected, "gte"):
                return False
            if operator == "lt" and not self._compare_numeric(value, expected, "lt"):
                return False
            if operator == "lte" and not self._compare_numeric(value, expected, "lte"):
                return False
            if operator == "in":
                if not isinstance(expected, (list, tuple, set)):
                    raise MarkerStoreError("Operator 'in' expects a list/tuple/set")
                if value not in expected:
                    return False
                continue
            if operator not in {"eq", "gt", "gte", "lt", "lte", "in"}:
                raise MarkerStoreError(f"Unsupported filter operator: {operator}")

        return True

    def _parse_filter(self, filter_name: str) -> tuple[str, str]:
        if "__" not in filter_name:
            return filter_name, "eq"
        field, operator = filter_name.rsplit("__", 1)
        return field, operator

    def _compare_numeric(self, value: Any, expected: Any, op: str) -> bool:
        if not isinstance(value, (int, float)):
            return False

        left = float(value)
        right = float(expected)

        if op == "gt":
            return left > right
        if op == "gte":
            return left >= right
        if op == "lt":
            return left < right
        if op == "lte":
            return left <= right

        raise MarkerStoreError(f"Unsupported numeric operator: {op}")

    def _ensure_column(
        self,
        *,
        conn: sqlite3.Connection,
        table_name: str,
        column_name: str,
        definition: str,
    ) -> None:
        columns = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        existing = {str(row["name"]) for row in columns}
        if column_name in existing:
            return
        conn.execute(
            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}"
        )

    def _record_lock_event_in_tx(
        self,
        *,
        conn: sqlite3.Connection,
        marker_id: str,
        agent_id: str,
        tick: int,
        acquired: bool,
    ) -> None:
        conn.execute(
            """
            INSERT INTO marker_lock_events (
                marker_id, agent_id, tick, acquired, recorded_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                str(marker_id),
                str(agent_id),
                int(tick),
                1 if acquired else 0,
                utc_timestamp(),
            ),
        )
