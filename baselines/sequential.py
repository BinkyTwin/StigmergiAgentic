"""Sequential baseline: fixed stage-by-stage pipeline without stigmergic round-robin."""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents.scout import Scout  # noqa: E402
from agents.tester import Tester  # noqa: E402
from agents.transformer import Transformer  # noqa: E402
from agents.validator import Validator  # noqa: E402
from baselines.common import (  # noqa: E402
    build_manifest,
    build_run_id,
    load_runtime_config,
    parse_baseline_args,
    persist_run_outputs,
    prepare_run_environment,
    setup_logging,
)
from environment.pheromone_store import PheromoneStore  # noqa: E402
from metrics.collector import MetricsCollector  # noqa: E402
from stigmergy.llm_client import LLMClient  # noqa: E402


TERMINAL_STATUSES = {"validated", "skipped", "needs_review"}


def run_sequential_baseline(
    *,
    config: dict[str, Any],
    target_repo_path: Path,
    pheromone_store: PheromoneStore,
    run_id: str,
) -> dict[str, Any]:
    """Run Scout->Transformer->Tester->Validator in fixed-stage batches."""
    llm_client = LLMClient(config=config)

    scout = Scout(
        name="scout",
        config=config,
        pheromone_store=pheromone_store,
        target_repo_path=target_repo_path,
        llm_client=llm_client,
    )
    transformer = Transformer(
        name="transformer",
        config=config,
        pheromone_store=pheromone_store,
        target_repo_path=target_repo_path,
        llm_client=llm_client,
    )
    tester = Tester(
        name="tester",
        config=config,
        pheromone_store=pheromone_store,
        target_repo_path=target_repo_path,
    )
    validator = Validator(
        name="validator",
        config=config,
        pheromone_store=pheromone_store,
        target_repo_path=target_repo_path,
    )

    collector = MetricsCollector(audit_log_path=pheromone_store.audit_log_path)
    logger = logging.getLogger("baseline.sequential")

    loop_cfg = config.get("loop", {})
    max_ticks = int(loop_cfg.get("max_ticks", 50))
    idle_cycles_to_stop = int(loop_cfg.get("idle_cycles_to_stop", 2))
    python_file_count = sum(1 for _ in target_repo_path.rglob("*.py"))
    default_stage_action_cap = max(25, python_file_count * 2)
    max_stage_actions_per_tick = int(
        loop_cfg.get("sequential_stage_action_cap", default_stage_action_cap)
    )
    max_tokens_total = int(config.get("llm", {}).get("max_tokens_total", 100000))
    max_budget_usd = float(config.get("llm", {}).get("max_budget_usd", 0.0))

    idle_cycles = 0
    stop_reason = "max_ticks"

    for tick in range(max_ticks):
        config.setdefault("runtime", {})["tick"] = tick

        maintenance = pheromone_store.maintain_status(current_tick=tick)
        if maintenance["ttl_released"] or maintenance["retry_requeued"]:
            logger.info("tick=%s maintenance=%s", tick, maintenance)

        pheromone_store.apply_decay("tasks")
        pheromone_store.apply_decay_inhibition()

        stage_acted = {
            "scout": False,
            "transformer": False,
            "tester": False,
            "validator": False,
        }
        budget_exhausted_mid_tick = False

        for stage_name, stage_runner in (
            ("scout", scout),
            ("transformer", transformer),
            ("tester", tester),
            ("validator", validator),
        ):
            stage_actions = 0
            while stage_runner.run():
                stage_actions += 1
                stage_acted[stage_name] = True
                if _budget_exhausted(
                    total_tokens=int(llm_client.total_tokens_used),
                    total_cost_usd=float(llm_client.total_cost_usd),
                    max_tokens_total=max_tokens_total,
                    max_budget_usd=max_budget_usd,
                ):
                    budget_exhausted_mid_tick = True
                    break
                if stage_actions >= max_stage_actions_per_tick:
                    logger.warning(
                        "tick=%s stage=%s action cap reached (%s), breaking stage loop",
                        tick,
                        stage_name,
                        max_stage_actions_per_tick,
                    )
                    break

            if budget_exhausted_mid_tick:
                break

        statuses = pheromone_store.read_all("status")
        total_tokens = int(llm_client.total_tokens_used)
        total_cost_usd = float(llm_client.total_cost_usd)
        collector.record_tick(
            tick=tick,
            agents_acted=stage_acted,
            status_entries=statuses,
            total_tokens=total_tokens,
            total_cost_usd=total_cost_usd,
        )

        if any(stage_acted.values()):
            idle_cycles = 0
        else:
            idle_cycles += 1

        if budget_exhausted_mid_tick:
            stop_reason = "budget_exhausted"
            break
        if _all_terminal(statuses):
            stop_reason = "all_terminal"
            break
        if total_tokens >= max_tokens_total:
            stop_reason = "budget_exhausted"
            break
        if max_budget_usd > 0.0 and total_cost_usd >= max_budget_usd:
            stop_reason = "budget_exhausted"
            break
        if idle_cycles >= idle_cycles_to_stop:
            stop_reason = "idle_cycles"
            break

    summary = collector.build_summary(stop_reason=stop_reason)
    summary["run_id"] = run_id
    summary["scheduler"] = "sequential"
    summary["baseline"] = "sequential"

    return {"summary": summary, "tick_rows": collector.tick_rows}


def _budget_exhausted(
    *,
    total_tokens: int,
    total_cost_usd: float,
    max_tokens_total: int,
    max_budget_usd: float,
) -> bool:
    if total_tokens >= max_tokens_total:
        return True
    if max_budget_usd > 0.0 and total_cost_usd >= max_budget_usd:
        return True
    return False


def _all_terminal(status_entries: dict[str, dict[str, Any]]) -> bool:
    if not status_entries:
        return False
    return all(
        str(entry.get("status", "pending")) in TERMINAL_STATUSES
        for entry in status_entries.values()
    )


def main() -> int:
    """CLI entrypoint for sequential baseline runs."""
    args = parse_baseline_args("Run sequential baseline (fixed-stage pipeline)")
    base_path = Path(__file__).resolve().parents[1]
    setup_logging(base_path=base_path, verbose=bool(args.verbose))

    config = load_runtime_config(args=args, base_path=base_path)
    logger = logging.getLogger("baseline.sequential")

    for run_index in range(1, int(args.runs) + 1):
        run_id = build_run_id(prefix="sequential", run_index=run_index)
        config.setdefault("runtime", {})["run_id"] = run_id

        target_repo_path, store = prepare_run_environment(
            args=args,
            base_path=base_path,
            config=config,
            reset_pheromones=True,
        )

        manifest = build_manifest(
            run_id=run_id,
            baseline_name="sequential",
            config=config,
            target_repo_path=target_repo_path,
            seed=args.seed,
        )
        config["runtime"]["manifest"] = manifest

        logger.info("Starting sequential run_id=%s", run_id)
        result = run_sequential_baseline(
            config=config,
            target_repo_path=target_repo_path,
            pheromone_store=store,
            run_id=run_id,
        )
        persist_run_outputs(
            config=config,
            run_id=run_id,
            manifest=manifest,
            summary=result["summary"],
            tick_rows=result["tick_rows"],
        )
        print(json.dumps(result["summary"], indent=2, sort_keys=True))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
