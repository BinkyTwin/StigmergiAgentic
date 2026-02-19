"""JSON-backed pheromone store with locking, decay, and audit trail."""

from __future__ import annotations

import copy
import fcntl
import json
from pathlib import Path
from typing import Any, Callable, Mapping

import yaml  # type: ignore[import-untyped]

from .decay import decay_inhibition, decay_intensity
from .guardrails import Guardrails, utc_timestamp

PHEROMONE_FILE_MAP = {
    "tasks": "tasks.json",
    "status": "status.json",
    "quality": "quality.json",
}


class PheromoneStoreError(RuntimeError):
    """Raised when pheromone persistence fails."""


class PheromoneStore:
    """CRUD interface for task, status, and quality pheromones."""

    def __init__(
        self,
        config: Mapping[str, Any] | str | Path,
        base_path: str | Path | None = None,
    ) -> None:
        self.config = self._load_config(config)
        self.base_path = Path(base_path) if base_path else Path.cwd()

        self.pheromone_dir = self.base_path / "pheromones"
        self.file_paths = {
            pheromone_type: self.pheromone_dir / filename
            for pheromone_type, filename in PHEROMONE_FILE_MAP.items()
        }
        self.audit_log_path = self.pheromone_dir / "audit_log.jsonl"

        self.guardrails = Guardrails(self.config)

        pheromone_config = self.config.get("pheromones", {})
        self.decay_type = str(pheromone_config.get("decay_type", "exponential"))
        self.decay_rate = float(pheromone_config.get("decay_rate", 0.05))
        self.inhibition_decay_rate = float(
            pheromone_config.get("inhibition_decay_rate", 0.08)
        )

        self._ensure_store_files()

    def read_all(self, pheromone_type: str) -> dict[str, dict[str, Any]]:
        """Read all entries for one pheromone type."""
        self._validate_pheromone_type(pheromone_type)
        return self._read_json_file(self.file_paths[pheromone_type])

    def read_one(self, pheromone_type: str, file_key: str) -> dict[str, Any] | None:
        """Read one entry by file key."""
        return self.read_all(pheromone_type).get(file_key)

    def query(self, pheromone_type: str, **filters: Any) -> dict[str, dict[str, Any]]:
        """Filter entries by field operators (eq, gt, gte, lt, lte, in)."""
        entries = self.read_all(pheromone_type)
        return {
            file_key: entry
            for file_key, entry in entries.items()
            if self._matches_filters(file_key, entry, filters)
        }

    def write(
        self,
        pheromone_type: str,
        file_key: str,
        data: dict[str, Any],
        agent_id: str,
    ) -> None:
        """Write/overwrite one pheromone entry."""
        self._validate_pheromone_type(pheromone_type)
        if not isinstance(data, dict):
            raise PheromoneStoreError("write expects a dictionary payload")

        self._enforce_scope_lock(pheromone_type, file_key, agent_id)

        def transform(previous_entry: dict[str, Any]) -> dict[str, Any]:
            candidate = copy.deepcopy(data)
            candidate = self._finalize_status_entry(
                pheromone_type=pheromone_type,
                previous_entry=previous_entry,
                candidate_entry=candidate,
                agent_id=agent_id,
            )
            return self.guardrails.stamp_trace(candidate, agent_id, action="write")

        previous_values, updated_entry = self._upsert_entry(
            pheromone_type=pheromone_type,
            file_key=file_key,
            transform=transform,
        )

        self._append_audit_event(
            agent_id=agent_id,
            pheromone_type=pheromone_type,
            file_key=file_key,
            action="write",
            previous_values=previous_values,
            updated_values=updated_entry,
        )

    def update(
        self,
        pheromone_type: str,
        file_key: str,
        agent_id: str,
        **fields: Any,
    ) -> None:
        """Update selected fields on one pheromone entry."""
        self._validate_pheromone_type(pheromone_type)
        self._enforce_scope_lock(pheromone_type, file_key, agent_id)

        def transform(previous_entry: dict[str, Any]) -> dict[str, Any]:
            candidate = copy.deepcopy(previous_entry)
            candidate.update(fields)
            candidate = self._finalize_status_entry(
                pheromone_type=pheromone_type,
                previous_entry=previous_entry,
                candidate_entry=candidate,
                agent_id=agent_id,
            )
            return self.guardrails.stamp_trace(candidate, agent_id, action="update")

        previous_values, updated_entry = self._upsert_entry(
            pheromone_type=pheromone_type,
            file_key=file_key,
            transform=transform,
        )

        self._append_audit_event(
            agent_id=agent_id,
            pheromone_type=pheromone_type,
            file_key=file_key,
            action="update",
            previous_values=previous_values,
            updated_values=updated_entry,
        )

    def apply_decay(self, pheromone_type: str) -> None:
        """Apply configured decay to task intensity pheromones."""
        self._validate_pheromone_type(pheromone_type)
        if pheromone_type != "tasks":
            return

        status_data = self.read_all("status")
        path = self.file_paths["tasks"]
        audit_events: list[dict[str, Any]] = []

        with path.open("r+", encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                payload = self._load_json_from_handle(handle)

                for file_key, entry in payload.items():
                    status_value = status_data.get(file_key, {}).get(
                        "status", "pending"
                    )
                    if status_value not in {"pending", "retry"}:
                        continue

                    intensity = entry.get("intensity")
                    if not isinstance(intensity, (int, float)):
                        continue

                    updated_intensity = decay_intensity(
                        value=float(intensity),
                        decay_type=self.decay_type,
                        decay_rate=self.decay_rate,
                    )
                    if updated_intensity == float(intensity):
                        continue

                    entry["intensity"] = updated_intensity
                    entry["timestamp"] = utc_timestamp()
                    entry["updated_by"] = "system_decay"

                    audit_events.append(
                        {
                            "timestamp": utc_timestamp(),
                            "agent": "system_decay",
                            "pheromone_type": "tasks",
                            "file_key": file_key,
                            "action": "update",
                            "fields_changed": {"intensity": updated_intensity},
                            "previous_values": {"intensity": float(intensity)},
                        }
                    )

                self._dump_json_to_handle(handle, payload)
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

        self._append_audit_events(audit_events)

    def apply_decay_inhibition(self) -> None:
        """Apply inhibition decay gamma^(t+1)=gamma^t*exp(-k_gamma)."""
        path = self.file_paths["status"]
        audit_events: list[dict[str, Any]] = []

        with path.open("r+", encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                payload = self._load_json_from_handle(handle)

                for file_key, entry in payload.items():
                    inhibition = entry.get("inhibition")
                    if not isinstance(inhibition, (int, float)):
                        continue
                    if inhibition <= 0:
                        continue

                    updated_inhibition = decay_inhibition(
                        value=float(inhibition),
                        inhibition_decay_rate=self.inhibition_decay_rate,
                    )
                    if updated_inhibition == float(inhibition):
                        continue

                    entry["inhibition"] = updated_inhibition
                    entry["timestamp"] = utc_timestamp()
                    entry["updated_by"] = "system_decay"

                    audit_events.append(
                        {
                            "timestamp": utc_timestamp(),
                            "agent": "system_decay",
                            "pheromone_type": "status",
                            "file_key": file_key,
                            "action": "update",
                            "fields_changed": {"inhibition": updated_inhibition},
                            "previous_values": {"inhibition": float(inhibition)},
                        }
                    )

                self._dump_json_to_handle(handle, payload)
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

        self._append_audit_events(audit_events)

    def maintain_status(self, current_tick: int) -> dict[str, list[str]]:
        """Apply status maintenance transitions atomically.

        This method handles:
        - zombie lock release using scope lock TTL
        - retry queue release (`retry` -> `pending`) at tick start
        """
        path = self.file_paths["status"]
        audit_events: list[dict[str, Any]] = []
        ttl_released: list[str] = []
        retry_requeued: list[str] = []

        with path.open("r+", encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                payload = self._load_json_from_handle(handle)
                previous_payload = copy.deepcopy(payload)

                ttl_released = self.guardrails.enforce_scope_lock_ttl(
                    payload, current_tick=current_tick
                )
                for file_key in ttl_released:
                    previous_entry = previous_payload.get(file_key, {})
                    updated_entry = payload.get(file_key, {})
                    audit_events.append(
                        {
                            "timestamp": utc_timestamp(),
                            "agent": "system_ttl",
                            "pheromone_type": "status",
                            "file_key": file_key,
                            "action": "update",
                            "fields_changed": {
                                "status": updated_entry.get("status"),
                                "retry_count": updated_entry.get("retry_count"),
                            },
                            "previous_values": {
                                "status": previous_entry.get("status"),
                                "retry_count": previous_entry.get("retry_count"),
                            },
                        }
                    )

                for file_key, entry in payload.items():
                    if entry.get("status") != "retry":
                        continue

                    previous_status = entry.get("status")
                    entry["previous_status"] = previous_status
                    entry["status"] = "pending"
                    entry["timestamp"] = utc_timestamp()
                    entry["updated_by"] = "system_retry"
                    retry_requeued.append(file_key)

                    audit_events.append(
                        {
                            "timestamp": utc_timestamp(),
                            "agent": "system_retry",
                            "pheromone_type": "status",
                            "file_key": file_key,
                            "action": "update",
                            "fields_changed": {
                                "status": "pending",
                            },
                            "previous_values": {
                                "status": previous_status,
                            },
                        }
                    )

                self._dump_json_to_handle(handle, payload)
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

        self._append_audit_events(audit_events)
        return {
            "ttl_released": sorted(ttl_released),
            "retry_requeued": sorted(retry_requeued),
        }

    def _validate_pheromone_type(self, pheromone_type: str) -> None:
        if pheromone_type not in self.file_paths:
            raise PheromoneStoreError(
                f"Invalid pheromone_type '{pheromone_type}'. "
                f"Expected one of: {', '.join(self.file_paths.keys())}"
            )

    def _enforce_scope_lock(
        self, pheromone_type: str, file_key: str, agent_id: str
    ) -> None:
        if pheromone_type == "status":
            status_entry = self.read_one("status", file_key)
        else:
            status_entry = self.read_one("status", file_key)
        self.guardrails.enforce_scope_lock(file_key, agent_id, status_entry)

    def _finalize_status_entry(
        self,
        pheromone_type: str,
        previous_entry: dict[str, Any],
        candidate_entry: dict[str, Any],
        agent_id: str,
    ) -> dict[str, Any]:
        if pheromone_type != "status":
            return candidate_entry

        current_tick = int(candidate_entry.pop("current_tick", 0))
        status_value = candidate_entry.get("status")

        previous_retry = int(previous_entry.get("retry_count", 0))
        candidate_retry = int(candidate_entry.get("retry_count", previous_retry))
        candidate_entry["retry_count"] = max(previous_retry, candidate_retry)

        if status_value == "in_progress":
            candidate_entry = self.guardrails.acquire_scope_lock(
                candidate_entry,
                agent_id=agent_id,
                current_tick=current_tick,
            )
        else:
            candidate_entry = self.guardrails.release_scope_lock(
                candidate_entry,
                agent_id=agent_id,
            )

        if self.guardrails.enforce_retry_limit(candidate_entry["retry_count"]):
            candidate_entry["status"] = "skipped"

        return candidate_entry

    def _upsert_entry(
        self,
        pheromone_type: str,
        file_key: str,
        transform: Callable[[dict[str, Any]], dict[str, Any]],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        path = self.file_paths[pheromone_type]

        with path.open("r+", encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                payload = self._load_json_from_handle(handle)
                previous_entry = copy.deepcopy(payload.get(file_key, {}))
                updated_entry = transform(previous_entry)
                payload[file_key] = updated_entry
                self._dump_json_to_handle(handle, payload)
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

        return previous_entry, updated_entry

    def _read_json_file(self, path: Path) -> dict[str, dict[str, Any]]:
        with path.open("r", encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_SH)
            try:
                payload = self._load_json_from_handle(handle)
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        return payload

    def _load_json_from_handle(self, handle: Any) -> dict[str, dict[str, Any]]:
        handle.seek(0)
        raw_content = handle.read().strip()
        if not raw_content:
            return {}

        try:
            payload = json.loads(raw_content)
        except json.JSONDecodeError as exc:
            raise PheromoneStoreError(f"Invalid JSON in {handle.name}") from exc

        if not isinstance(payload, dict):
            raise PheromoneStoreError(f"Expected object payload in {handle.name}")

        return payload

    def _dump_json_to_handle(self, handle: Any, payload: dict[str, Any]) -> None:
        handle.seek(0)
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.truncate()
        handle.flush()

    def _matches_filters(
        self,
        file_key: str,
        entry: Mapping[str, Any],
        filters: Mapping[str, Any],
    ) -> bool:
        for filter_name, expected_value in filters.items():
            field_name, operator = self._parse_filter(filter_name)
            current_value = (
                file_key if field_name == "file_key" else entry.get(field_name)
            )

            if operator == "eq" and current_value != expected_value:
                return False
            if operator == "gt" and not self._compare_numeric(
                current_value, expected_value, op="gt"
            ):
                return False
            if operator == "gte" and not self._compare_numeric(
                current_value, expected_value, op="gte"
            ):
                return False
            if operator == "lt" and not self._compare_numeric(
                current_value, expected_value, op="lt"
            ):
                return False
            if operator == "lte" and not self._compare_numeric(
                current_value, expected_value, op="lte"
            ):
                return False
            if operator == "in" and current_value not in expected_value:
                return False

        return True

    def _parse_filter(self, filter_name: str) -> tuple[str, str]:
        if "__" not in filter_name:
            return filter_name, "eq"
        field_name, operator = filter_name.rsplit("__", 1)
        return field_name, operator

    def _compare_numeric(
        self, current_value: Any, expected_value: Any, op: str
    ) -> bool:
        if not isinstance(current_value, (int, float)):
            return False

        if op == "gt":
            return float(current_value) > float(expected_value)
        if op == "gte":
            return float(current_value) >= float(expected_value)
        if op == "lt":
            return float(current_value) < float(expected_value)
        if op == "lte":
            return float(current_value) <= float(expected_value)

        raise PheromoneStoreError(f"Unsupported numeric operator: {op}")

    def _append_audit_event(
        self,
        agent_id: str,
        pheromone_type: str,
        file_key: str,
        action: str,
        previous_values: Mapping[str, Any],
        updated_values: Mapping[str, Any],
    ) -> None:
        changed_fields: dict[str, Any] = {}
        previous_changed_values: dict[str, Any] = {}

        for key, updated_value in updated_values.items():
            previous_value = previous_values.get(key)
            if previous_value != updated_value:
                changed_fields[key] = updated_value
                if key in previous_values:
                    previous_changed_values[key] = previous_value

        event = {
            "timestamp": utc_timestamp(),
            "agent": agent_id,
            "pheromone_type": pheromone_type,
            "file_key": file_key,
            "action": action,
            "fields_changed": changed_fields,
            "previous_values": previous_changed_values,
        }
        self._append_audit_events([event])

    def _append_audit_events(self, events: list[dict[str, Any]]) -> None:
        if not events:
            return

        with self.audit_log_path.open("a+", encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                for event in events:
                    handle.write(json.dumps(event, sort_keys=True) + "\n")
                handle.flush()
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def _ensure_store_files(self) -> None:
        self.pheromone_dir.mkdir(parents=True, exist_ok=True)

        for path in self.file_paths.values():
            if not path.exists() or path.stat().st_size == 0:
                path.write_text("{}\n", encoding="utf-8")

        if not self.audit_log_path.exists():
            self.audit_log_path.touch()

    def _load_config(self, config: Mapping[str, Any] | str | Path) -> dict[str, Any]:
        if isinstance(config, Mapping):
            return dict(config)

        config_path = Path(config)
        with config_path.open("r", encoding="utf-8") as handle:
            loaded = yaml.safe_load(handle) or {}

        if not isinstance(loaded, dict):
            raise PheromoneStoreError("Config file must resolve to a mapping")

        return loaded
