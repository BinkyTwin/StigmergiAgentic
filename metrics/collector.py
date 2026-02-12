"""Tick-level metrics collector for stigmergic loop runs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


TERMINAL_STATUSES = {"validated", "skipped", "needs_review"}
MIGRATED_STATUSES = {
    "in_progress",
    "transformed",
    "tested",
    "validated",
    "failed",
    "needs_review",
    "retry",
    "skipped",
}


class MetricsCollector:
    """Collect and aggregate per-tick metrics for one run."""

    def __init__(self, audit_log_path: Path, starvation_threshold: int = 12) -> None:
        self.audit_log_path = audit_log_path
        self.starvation_threshold = starvation_threshold
        self.tick_rows: list[dict[str, Any]] = []

        self._previous_statuses: dict[str, str] = {}
        self._idle_ticks_by_file: dict[str, int] = {}
        self._files_with_retry: set[str] = set()
        self._resolved_retry_files: set[str] = set()

    def record_tick(
        self,
        tick: int,
        agents_acted: Mapping[str, bool],
        status_entries: Mapping[str, Mapping[str, Any]],
        total_tokens: int,
    ) -> None:
        """Record one loop tick worth of metrics."""
        normalized_statuses: dict[str, str] = {
            file_key: str(entry.get("status", "pending"))
            for file_key, entry in status_entries.items()
        }
        self._update_status_tracking(normalized_statuses)

        statuses = list(normalized_statuses.values())
        files_total = len(statuses)
        files_migrated = sum(1 for status in statuses if status in MIGRATED_STATUSES)
        files_validated = statuses.count("validated")
        files_failed = statuses.count("failed")
        files_needs_review = statuses.count("needs_review")

        total_ticks = tick + 1
        terminal_or_failed = (
            files_validated + statuses.count("skipped") + files_needs_review + files_failed
        )
        tokens_per_file = (
            float(total_tokens) / float(terminal_or_failed)
            if terminal_or_failed > 0
            else 0.0
        )
        success_rate = (
            float(files_validated) / float(files_total) if files_total > 0 else 0.0
        )
        rollback_denom = files_validated + files_failed
        rollback_rate = (
            float(files_failed) / float(rollback_denom)
            if rollback_denom > 0
            else 0.0
        )
        human_escalation_rate = (
            float(files_needs_review) / float(files_total)
            if files_total > 0
            else 0.0
        )
        retry_total = len(self._files_with_retry)
        retry_resolution_rate = (
            float(len(self._resolved_retry_files)) / float(retry_total)
            if retry_total > 0
            else 0.0
        )

        starvation_count = sum(
            1
            for file_key, idle_ticks in self._idle_ticks_by_file.items()
            if idle_ticks > self.starvation_threshold
            and normalized_statuses.get(file_key, "pending") not in TERMINAL_STATUSES
        )

        row = {
            "tick": tick,
            "any_agent_acted": bool(any(agents_acted.values())),
            "acted_scout": bool(agents_acted.get("scout", False)),
            "acted_transformer": bool(agents_acted.get("transformer", False)),
            "acted_tester": bool(agents_acted.get("tester", False)),
            "acted_validator": bool(agents_acted.get("validator", False)),
            "files_total": files_total,
            "files_migrated": files_migrated,
            "files_validated": files_validated,
            "files_failed": files_failed,
            "files_needs_review": files_needs_review,
            "total_tokens": int(total_tokens),
            "total_ticks": total_ticks,
            "tokens_per_file": round(tokens_per_file, 6),
            "success_rate": round(success_rate, 6),
            "rollback_rate": round(rollback_rate, 6),
            "human_escalation_rate": round(human_escalation_rate, 6),
            "retry_resolution_rate": round(retry_resolution_rate, 6),
            "starvation_count": starvation_count,
            "audit_completeness": round(self._compute_audit_completeness(), 6),
        }
        self.tick_rows.append(row)

    def build_summary(self, stop_reason: str) -> dict[str, Any]:
        """Build summary payload from collected ticks."""
        if not self.tick_rows:
            return {
                "stop_reason": stop_reason,
                "total_ticks": 0,
                "files_total": 0,
                "files_validated": 0,
                "files_failed": 0,
                "files_needs_review": 0,
                "total_tokens": 0,
                "success_rate": 0.0,
                "rollback_rate": 0.0,
                "human_escalation_rate": 0.0,
                "retry_resolution_rate": 0.0,
                "starvation_count": 0,
                "audit_completeness": 1.0,
            }

        last = self.tick_rows[-1]
        return {
            "stop_reason": stop_reason,
            "total_ticks": last["total_ticks"],
            "files_total": last["files_total"],
            "files_validated": last["files_validated"],
            "files_failed": last["files_failed"],
            "files_needs_review": last["files_needs_review"],
            "total_tokens": last["total_tokens"],
            "success_rate": last["success_rate"],
            "rollback_rate": last["rollback_rate"],
            "human_escalation_rate": last["human_escalation_rate"],
            "retry_resolution_rate": last["retry_resolution_rate"],
            "starvation_count": last["starvation_count"],
            "audit_completeness": last["audit_completeness"],
        }

    def _update_status_tracking(self, current_statuses: Mapping[str, str]) -> None:
        for file_key, current_status in current_statuses.items():
            previous_status = self._previous_statuses.get(file_key)
            if previous_status == current_status:
                self._idle_ticks_by_file[file_key] = (
                    self._idle_ticks_by_file.get(file_key, 0) + 1
                )
            else:
                self._idle_ticks_by_file[file_key] = 0

            if current_status == "retry" and previous_status != "retry":
                self._files_with_retry.add(file_key)

            if current_status == "validated" and file_key in self._files_with_retry:
                self._resolved_retry_files.add(file_key)

            self._previous_statuses[file_key] = current_status

        for file_key in list(self._previous_statuses.keys()):
            if file_key not in current_statuses:
                self._previous_statuses.pop(file_key, None)
                self._idle_ticks_by_file.pop(file_key, None)

    def _compute_audit_completeness(self) -> float:
        if not self.audit_log_path.exists():
            return 1.0

        lines = [line.strip() for line in self.audit_log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        total_events = len(lines)
        if total_events == 0:
            return 1.0

        required_fields = {"timestamp", "agent", "pheromone_type", "file_key", "action"}
        full_trace_events = 0

        for line in lines:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue

            if not isinstance(event, dict):
                continue

            if all(field in event and event.get(field) not in (None, "") for field in required_fields):
                full_trace_events += 1

        return float(full_trace_events) / float(total_events)

