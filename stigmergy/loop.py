"""Round-robin stigmergic loop for Sprint 3."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agents.scout import Scout
from agents.tester import Tester
from agents.transformer import Transformer
from agents.validator import Validator
from environment.pheromone_store import PheromoneStore
from metrics.collector import MetricsCollector
from metrics.export import (
    ensure_output_dir,
    write_manifest_json,
    write_summary_json,
    write_ticks_csv,
)
from stigmergy.llm_client import LLMClient


TERMINAL_STATUSES = {"validated", "skipped", "needs_review"}


def run_loop(
    config: dict[str, Any],
    target_repo_path: Path,
    llm_client: LLMClient | None = None,
    store: PheromoneStore | None = None,
) -> dict[str, Any]:
    """Run the full Scout -> Transformer -> Tester -> Validator loop."""
    runtime = config.setdefault("runtime", {})
    base_path = Path(runtime.get("base_path", Path.cwd()))

    active_store = store or PheromoneStore(config=config, base_path=base_path)
    active_llm_client = llm_client or LLMClient(config=config)
    logger = logging.getLogger("loop")

    agents = [
        Scout(
            name="scout",
            config=config,
            pheromone_store=active_store,
            target_repo_path=target_repo_path,
            llm_client=active_llm_client,
        ),
        Transformer(
            name="transformer",
            config=config,
            pheromone_store=active_store,
            target_repo_path=target_repo_path,
            llm_client=active_llm_client,
        ),
        Tester(
            name="tester",
            config=config,
            pheromone_store=active_store,
            target_repo_path=target_repo_path,
        ),
        Validator(
            name="validator",
            config=config,
            pheromone_store=active_store,
            target_repo_path=target_repo_path,
        ),
    ]

    loop_config = config.get("loop", {})
    max_ticks = int(loop_config.get("max_ticks", 50))
    idle_cycles_to_stop = int(loop_config.get("idle_cycles_to_stop", 2))
    max_tokens_total = int(config.get("llm", {}).get("max_tokens_total", 100000))

    collector = MetricsCollector(audit_log_path=active_store.audit_log_path)

    idle_cycles = 0
    stop_reason = "max_ticks"

    for tick in range(max_ticks):
        runtime["tick"] = tick
        maintenance = active_store.maintain_status(current_tick=tick)
        if maintenance["ttl_released"] or maintenance["retry_requeued"]:
            logger.info(
                "tick=%s maintenance ttl_released=%s retry_requeued=%s",
                tick,
                maintenance["ttl_released"],
                maintenance["retry_requeued"],
            )

        active_store.apply_decay("tasks")
        active_store.apply_decay_inhibition()

        agents_acted: dict[str, bool] = {}
        for agent in agents:
            acted = agent.run()
            agents_acted[agent.name] = acted

        status_entries = active_store.read_all("status")
        total_tokens = int(active_llm_client.total_tokens_used)
        collector.record_tick(
            tick=tick,
            agents_acted=agents_acted,
            status_entries=status_entries,
            total_tokens=total_tokens,
        )

        any_acted = any(agents_acted.values())
        if any_acted:
            idle_cycles = 0
        else:
            idle_cycles += 1

        if _all_terminal(status_entries):
            stop_reason = "all_terminal"
            break
        if total_tokens >= max_tokens_total:
            stop_reason = "budget_exhausted"
            break
        if idle_cycles >= idle_cycles_to_stop:
            stop_reason = "idle_cycles"
            break

    summary = collector.build_summary(stop_reason=stop_reason)
    run_id = str(runtime.get("run_id", _default_run_id()))
    summary["run_id"] = run_id

    output_dir = Path(config.get("metrics", {}).get("output_dir", "metrics/output"))
    if not output_dir.is_absolute():
        output_dir = base_path / output_dir
    ensure_output_dir(output_dir)

    ticks_path = output_dir / f"run_{run_id}_ticks.csv"
    summary_path = output_dir / f"run_{run_id}_summary.json"
    manifest_path = output_dir / f"run_{run_id}_manifest.json"

    write_ticks_csv(path=ticks_path, tick_rows=collector.tick_rows)
    write_summary_json(path=summary_path, summary=summary)

    manifest = runtime.get("manifest")
    if isinstance(manifest, dict) and manifest:
        write_manifest_json(path=manifest_path, manifest=manifest)

    return {
        "run_id": run_id,
        "stop_reason": stop_reason,
        "summary": summary,
        "ticks_path": str(ticks_path),
        "summary_path": str(summary_path),
        "manifest_path": str(manifest_path) if manifest else None,
    }


def _all_terminal(status_entries: dict[str, dict[str, Any]]) -> bool:
    if not status_entries:
        return False
    return all(
        str(entry.get("status", "pending")) in TERMINAL_STATUSES
        for entry in status_entries.values()
    )


def _default_run_id() -> str:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    return now.strftime("%Y%m%dT%H%M%SZ")

