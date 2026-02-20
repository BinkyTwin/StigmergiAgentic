"""Single-agent baseline: one LLM worker handles migration end-to-end per file."""

from __future__ import annotations

import json
import logging
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents.scout import Scout  # noqa: E402
from agents.tester import Tester  # noqa: E402
from baselines.common import (  # noqa: E402
    build_manifest,
    build_run_id,
    load_runtime_config,
    parse_baseline_args,
    persist_run_outputs,
    prepare_run_environment,
    setup_logging,
)
from environment.guardrails import ScopeLockError  # noqa: E402
from environment.pheromone_store import PheromoneStore  # noqa: E402
from metrics.collector import MetricsCollector  # noqa: E402
from stigmergy.llm_client import LLMClient  # noqa: E402


TERMINAL_STATUSES = {"validated", "skipped", "needs_review", "failed"}


@dataclass
class FileTask:
    """Single-agent migration task descriptor."""

    file_key: str
    intensity: float
    patterns: list[str]


class SingleAgentRunner:
    """Run a one-agent baseline with deterministic test and validation gates."""

    def __init__(
        self,
        *,
        config: dict[str, Any],
        target_repo_path: Path,
    ) -> None:
        self.config = config
        self.target_repo_path = target_repo_path
        self.base_path = Path(config.get("runtime", {}).get("base_path", Path.cwd()))
        self.store = PheromoneStore(config=config, base_path=self.base_path)
        self.llm_client = LLMClient(config=config)
        self.collector = MetricsCollector(audit_log_path=self.store.audit_log_path)
        self.logger = logging.getLogger("baseline.single_agent")

        self.validator_high = float(
            config.get("thresholds", {}).get("validator_confidence_high", 0.8)
        )
        self.validator_low = float(
            config.get("thresholds", {}).get("validator_confidence_low", 0.5)
        )
        self.max_retry_count = int(
            config.get("thresholds", {}).get("max_retry_count", 3)
        )

    def run(self, run_id: str) -> dict[str, Any]:
        """Execute baseline and return summary/ticks payload."""
        tasks = self._collect_tasks()
        statuses: dict[str, dict[str, Any]] = {
            task.file_key: {"status": "pending", "retry_count": 0, "inhibition": 0.0}
            for task in tasks
        }
        retries: dict[str, int] = {task.file_key: 0 for task in tasks}

        loop_cfg = self.config.get("loop", {})
        max_ticks = int(loop_cfg.get("max_ticks", max(1, len(tasks) * 2)))
        max_tokens_total = int(
            self.config.get("llm", {}).get("max_tokens_total", 100000)
        )
        max_budget_usd = float(self.config.get("llm", {}).get("max_budget_usd", 0.0))

        stop_reason = "max_ticks"

        for tick in range(max_ticks):
            self.config.setdefault("runtime", {})["tick"] = tick
            acted = {
                "scout": False,
                "transformer": False,
                "tester": False,
                "validator": False,
            }

            next_task = self._next_pending_task(statuses=statuses, tasks=tasks)
            if next_task is not None:
                acted["transformer"] = True
                acted["tester"] = True
                acted["validator"] = True
                self._process_task(task=next_task, statuses=statuses, retries=retries)

            self.collector.record_tick(
                tick=tick,
                agents_acted=acted,
                status_entries=statuses,
                total_tokens=int(self.llm_client.total_tokens_used),
                total_cost_usd=float(self.llm_client.total_cost_usd),
            )

            if self._all_terminal(statuses):
                stop_reason = "all_terminal"
                break
            if int(self.llm_client.total_tokens_used) >= max_tokens_total:
                stop_reason = "budget_exhausted"
                break
            if (
                max_budget_usd > 0.0
                and float(self.llm_client.total_cost_usd) >= max_budget_usd
            ):
                stop_reason = "budget_exhausted"
                break

        summary = self.collector.build_summary(stop_reason=stop_reason)
        summary["run_id"] = run_id
        summary["scheduler"] = "single_agent"
        summary["baseline"] = "single_agent"
        return {"summary": summary, "tick_rows": self.collector.tick_rows}

    def _collect_tasks(self) -> list[FileTask]:
        scout = Scout(
            name="single_agent_scout",
            config=self.config,
            pheromone_store=self.store,
            target_repo_path=self.target_repo_path,
            llm_client=self.llm_client,
        )
        while scout.run():
            continue

        task_entries = self.store.read_all("tasks")
        tasks: list[FileTask] = []
        for file_key, entry in task_entries.items():
            tasks.append(
                FileTask(
                    file_key=file_key,
                    intensity=float(entry.get("intensity", 0.0)),
                    patterns=list(entry.get("patterns_found", [])),
                )
            )
        tasks.sort(key=lambda item: (-item.intensity, item.file_key))
        return tasks

    def _process_task(
        self,
        *,
        task: FileTask,
        statuses: dict[str, dict[str, Any]],
        retries: dict[str, int],
    ) -> None:
        file_path = self.target_repo_path / task.file_key
        source = file_path.read_text(encoding="utf-8", errors="ignore")

        prompt = self._build_prompt(
            file_key=task.file_key,
            patterns=task.patterns,
            source_content=source,
            retries=retries[task.file_key],
        )
        try:
            response = self.llm_client.call(
                prompt=prompt,
                system="You are a single migration engineer. Convert full file Python2 to Python3 and return only code.",
            )
            transformed = self.llm_client.extract_code_block(response.content)
            if not transformed.strip():
                raise ValueError("empty transformed output")

            compile(transformed, str(file_path), "exec")
            file_path.write_text(transformed.rstrip() + "\n", encoding="utf-8")
            confidence, issues = self._evaluate_with_tester(
                file_key=task.file_key,
                retry_count=retries[task.file_key],
                inhibition=float(
                    statuses.get(task.file_key, {}).get("inhibition", 0.0)
                ),
            )

            if confidence >= self.validator_high:
                statuses[task.file_key] = {
                    "status": "validated",
                    "retry_count": retries[task.file_key],
                    "inhibition": 0.0,
                }
            elif confidence <= self.validator_low:
                retries[task.file_key] += 1
                file_path.write_text(source, encoding="utf-8")
                if retries[task.file_key] > self.max_retry_count:
                    statuses[task.file_key] = {
                        "status": "skipped",
                        "retry_count": retries[task.file_key],
                        "inhibition": 1.0,
                    }
                else:
                    statuses[task.file_key] = {
                        "status": "retry",
                        "retry_count": retries[task.file_key],
                        "inhibition": 0.5,
                    }
            else:
                statuses[task.file_key] = {
                    "status": "needs_review",
                    "retry_count": retries[task.file_key],
                    "inhibition": 0.0,
                }

            quality_data = self.store.read_one("quality", task.file_key) or {}
            if confidence >= self.validator_high:
                quality_data["confidence"] = min(1.0, confidence + 0.1)
            self._safe_store_write(
                "quality",
                file_key=task.file_key,
                data=quality_data,
                agent_id="single_agent",
            )
            self._safe_store_write(
                "status",
                file_key=task.file_key,
                data=statuses[task.file_key],
                agent_id="single_agent",
            )
        except Exception as exc:  # noqa: BLE001
            retries[task.file_key] += 1
            if retries[task.file_key] > self.max_retry_count:
                statuses[task.file_key] = {
                    "status": "failed",
                    "retry_count": retries[task.file_key],
                    "inhibition": 1.0,
                }
            else:
                statuses[task.file_key] = {
                    "status": "retry",
                    "retry_count": retries[task.file_key],
                    "inhibition": 0.8,
                }
            self._safe_store_write(
                "status",
                file_key=task.file_key,
                data=statuses[task.file_key],
                agent_id="single_agent",
            )
            self._safe_store_write(
                "quality",
                file_key=task.file_key,
                data={
                    "confidence": 0.0,
                    "tests_total": 1,
                    "tests_passed": 0,
                    "tests_failed": 1,
                    "coverage": 0.0,
                    "issues": [f"{exc}", traceback.format_exc(limit=1)],
                },
                agent_id="single_agent",
            )

    def _build_prompt(
        self, *, file_key: str, patterns: list[str], source_content: str, retries: int
    ) -> str:
        pattern_section = ", ".join(patterns) if patterns else "none"
        return (
            f"Migrate this Python 2 file to Python 3.\\n"
            f"File: {file_key}\\n"
            f"Detected patterns: {pattern_section}\\n"
            f"Retry count: {retries}\\n"
            "Rules:\\n"
            "- Preserve behavior.\\n"
            "- Return complete migrated file only.\\n"
            "- Keep imports valid for Python 3.\\n\\n"
            "Source:\\n"
            f"```python\\n{source_content}\\n```"
        )

    def _evaluate_with_tester(
        self,
        *,
        file_key: str,
        retry_count: int,
        inhibition: float,
    ) -> tuple[float, list[str]]:
        """Run the real Tester agent for evaluation (py_compile + import + pytest + fallback)."""
        try:
            self.store.write(
                "status",
                file_key=file_key,
                data={
                    "status": "transformed",
                    "retry_count": retry_count,
                    "inhibition": inhibition,
                },
                agent_id="single_agent",
            )
        except ScopeLockError as exc:
            self.logger.warning(
                "Scope lock blocked single-agent tester handoff for file=%s: %s",
                file_key,
                exc,
            )
            return 0.0, [str(exc)]
        tester = Tester(
            name="tester",
            config=self.config,
            pheromone_store=self.store,
            target_repo_path=self.target_repo_path,
        )
        tester.run()
        quality = self.store.read_one("quality", file_key) or {}
        confidence = float(quality.get("confidence", 0.0))
        issues = list(quality.get("issues", []))
        return confidence, issues

    def _safe_store_write(
        self,
        pheromone_type: str,
        *,
        file_key: str,
        data: dict[str, Any],
        agent_id: str,
    ) -> None:
        """Best-effort store write to avoid aborting an entire baseline run on stale locks."""
        try:
            self.store.write(
                pheromone_type,
                file_key=file_key,
                data=data,
                agent_id=agent_id,
            )
        except ScopeLockError as exc:
            self.logger.warning(
                "Ignoring scope lock during baseline write type=%s file=%s: %s",
                pheromone_type,
                file_key,
                exc,
            )

    def _next_pending_task(
        self,
        *,
        statuses: dict[str, dict[str, Any]],
        tasks: list[FileTask],
    ) -> FileTask | None:
        for task in tasks:
            status_value = str(statuses.get(task.file_key, {}).get("status", "pending"))
            if status_value in {"pending", "retry"}:
                return task
        return None

    def _all_terminal(self, statuses: dict[str, dict[str, Any]]) -> bool:
        if not statuses:
            return False
        return all(
            str(entry.get("status", "pending")) in TERMINAL_STATUSES
            for entry in statuses.values()
        )


def main() -> int:
    """CLI entrypoint for single-agent baseline runs."""
    args = parse_baseline_args("Run single-agent baseline (one LLM worker)")
    base_path = Path(__file__).resolve().parents[1]
    setup_logging(base_path=base_path, verbose=bool(args.verbose))

    config = load_runtime_config(args=args, base_path=base_path)
    logger = logging.getLogger("baseline.single_agent")

    for run_index in range(1, int(args.runs) + 1):
        run_id = build_run_id(prefix="single_agent", run_index=run_index)
        config.setdefault("runtime", {})["run_id"] = run_id

        target_repo_path, _ = prepare_run_environment(
            args=args,
            base_path=base_path,
            config=config,
            reset_pheromones=True,
        )
        manifest = build_manifest(
            run_id=run_id,
            baseline_name="single_agent",
            config=config,
            target_repo_path=target_repo_path,
            seed=args.seed,
        )
        config["runtime"]["manifest"] = manifest

        logger.info("Starting single-agent run_id=%s", run_id)
        result = SingleAgentRunner(
            config=config, target_repo_path=target_repo_path
        ).run(run_id=run_id)
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
