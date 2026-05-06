"""V10 unified bench harness — CLI and library entry points.

Thin orchestrator: build a :class:`DomainAdapterV10`, instantiate a
:class:`StrategyRunner`, run it once per benchmark instance, persist
events / hypotheses / artifacts, then derive ``summary.json`` from the
EventLog via :mod:`scripts.bench.telemetry`.

This module is deliberately strategy-agnostic and adapter-agnostic.
Concrete candidate providers live in :mod:`scripts.bench.providers` and
adapter constructors in :mod:`scripts.bench.adapters`.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence

from core_v10.contracts import DomainAdapterV10, RunInstance
from core_v10.event_log import JsonlEventLog
from core_v10.hypothesis_graph import HypothesisGraph
from core_v10.strategy_runner import (
    StrategyConfig,
    StrategyResult,
    StrategyRunner,
)

from scripts.bench.artifacts import (
    Manifest,
    RunRow,
    load_subset,
    write_manifest,
    write_runs_jsonl,
)
from scripts.bench.telemetry import (
    SCORE_EVENT,
    Summary,
    build_summary,
    write_summary,
)


AdapterFactory = Callable[[dict[str, Any]], DomainAdapterV10]
"""Factory taking the campaign config dict and returning a fresh adapter."""

CandidateProviderFactory = Callable[[DomainAdapterV10, dict[str, Any]], Any]
RepairProviderFactory = Callable[[DomainAdapterV10, dict[str, Any]], Any]
OperatorProviderFactory = Callable[[DomainAdapterV10, dict[str, Any]], Any]
RunInstanceFactory = Callable[[dict[str, Any], dict[str, Any]], RunInstance]


@dataclass
class HarnessOptions:
    """All knobs the harness needs at run time."""

    adapter_name: str
    strategy_name: str
    subset_path: Path
    out_dir: Path
    seed: int = 42
    limit: int | None = None
    max_candidates: int = 1
    max_repair_rounds: int = 0
    max_repairs_per_candidate: int = 1
    extras: dict[str, Any] | None = None


@dataclass
class HarnessRegistry:
    """Pluggable factories for adapters and providers."""

    adapter_factories: dict[str, AdapterFactory]
    candidate_provider_factories: dict[str, CandidateProviderFactory]
    repair_provider_factories: dict[str, RepairProviderFactory]
    operator_provider_factories: dict[str, OperatorProviderFactory]
    run_instance_factories: dict[str, RunInstanceFactory]


class BenchHarness:
    """Run one strategy on one subset, write a self-contained campaign tree."""

    def __init__(self, options: HarnessOptions, registry: HarnessRegistry) -> None:
        self.options = options
        self.registry = registry

    # ------------------------------------------------------------------
    # Public entry
    # ------------------------------------------------------------------

    def run(self) -> Summary:
        opts = self.options
        opts.out_dir.mkdir(parents=True, exist_ok=True)
        records = load_subset(opts.subset_path)
        if opts.limit is not None:
            records = records[: int(opts.limit)]

        if opts.adapter_name not in self.registry.adapter_factories:
            raise KeyError(f"unknown adapter: {opts.adapter_name}")
        if opts.adapter_name not in self.registry.run_instance_factories:
            raise KeyError(f"no RunInstance factory for adapter: {opts.adapter_name}")

        instance_factory = self.registry.run_instance_factories[opts.adapter_name]
        candidate_factory = self.registry.candidate_provider_factories.get(opts.adapter_name)
        repair_factory = self.registry.repair_provider_factories.get(opts.adapter_name)
        operator_factory = self.registry.operator_provider_factories.get(opts.adapter_name)
        adapter_factory = self.registry.adapter_factories[opts.adapter_name]

        campaign_id = uuid.uuid4().hex
        campaign_extras = dict(opts.extras or {})
        manifest = Manifest(
            campaign_id=campaign_id,
            adapter_name=opts.adapter_name,
            strategy_name=opts.strategy_name,
            subset_path=str(opts.subset_path),
            instance_ids=[str(r["instance_id"]) for r in records],
            out_dir=str(opts.out_dir),
            seed=opts.seed,
            extras=campaign_extras,
        )
        write_manifest(opts.out_dir, manifest)

        rows: list[RunRow] = []
        events_by_instance: dict[str, list] = {}

        for record in records:
            instance_id = str(record["instance_id"])
            run_instance = instance_factory(record, campaign_extras)

            event_path = opts.out_dir / "events" / instance_id / "eventlog.jsonl"
            event_path.parent.mkdir(parents=True, exist_ok=True)
            adapter = adapter_factory(campaign_extras)
            graph = HypothesisGraph()
            runner = StrategyRunner(
                adapter=adapter,
                event_log_path=event_path,
                graph=graph,
            )

            candidate_provider = (
                candidate_factory(adapter, campaign_extras)
                if candidate_factory
                else None
            )
            operator_provider = (
                operator_factory(adapter, campaign_extras)
                if operator_factory
                else None
            )
            if candidate_provider is None:
                raise KeyError(
                    f"no candidate_provider factory for adapter: {opts.adapter_name}"
                )

            config = StrategyConfig(
                name=opts.strategy_name,
                max_candidates=opts.max_candidates,
                max_repair_rounds=opts.max_repair_rounds,
                max_repairs_per_candidate=opts.max_repairs_per_candidate,
            )

            run_id = f"{campaign_id}:{instance_id}"
            if opts.strategy_name in (
                "branching_repair",
                "stigmergic_blackboard",
                "stigmergic_scheduler",
                "operator_search",
            ):
                if repair_factory is None:
                    raise KeyError(
                        f"no repair_provider factory for adapter: {opts.adapter_name}"
                    )
                repair_provider = repair_factory(adapter, campaign_extras)
                if opts.strategy_name == "stigmergic_blackboard":
                    result = runner.run_stigmergic_blackboard(
                        run_id=run_id,
                        instance=run_instance,
                        candidate_provider=candidate_provider,
                        repair_provider=repair_provider,
                        config=config,
                    )
                elif opts.strategy_name == "stigmergic_scheduler":
                    result = runner.run_stigmergic_scheduler(
                        run_id=run_id,
                        instance=run_instance,
                        candidate_provider=candidate_provider,
                        repair_provider=repair_provider,
                        operator_provider=operator_provider,
                        config=config,
                    )
                elif opts.strategy_name == "operator_search":
                    result = runner.run_operator_search(
                        run_id=run_id,
                        instance=run_instance,
                        candidate_provider=candidate_provider,
                        repair_provider=repair_provider,
                        operator_provider=operator_provider,
                        config=config,
                    )
                else:
                    result = runner.run_branching_repair(
                        run_id=run_id,
                        instance=run_instance,
                        candidate_provider=candidate_provider,
                        repair_provider=repair_provider,
                        config=config,
                    )
            else:
                result = runner.run_agentless(
                    run_id=run_id,
                    instance=run_instance,
                    candidate_provider=candidate_provider,
                    config=config,
                )

            # StrategyRunner resets its graph at strategy start, so persist
            # the runner-owned graph after execution rather than the initially
            # injected object.
            self._persist_graph(opts.out_dir, instance_id, runner.graph)
            row = self._make_row(result, runner.event_log)
            rows.append(row)
            events_by_instance[instance_id] = runner.event_log.for_run(run_id)

        write_runs_jsonl(opts.out_dir, rows)
        summary = build_summary(
            campaign_id=campaign_id,
            adapter_name=opts.adapter_name,
            strategy_name=opts.strategy_name,
            instance_ids=manifest.instance_ids,
            events_by_instance=events_by_instance,
        )
        write_summary(opts.out_dir, summary)
        return summary

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _persist_graph(
        self, out_dir: Path, instance_id: str, graph: HypothesisGraph
    ) -> None:
        path = out_dir / "hypotheses" / instance_id / "graph.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(graph.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def _make_row(self, result: StrategyResult, event_log: JsonlEventLog) -> RunRow:
        signals: dict[str, Any] = {}
        score_event = None
        for event in reversed(event_log.for_run(result.run_id)):
            if event.event_type == SCORE_EVENT:
                score_event = event
                break
        if score_event is not None:
            score = score_event.payload.get("score") or {}
            metrics = score.get("metrics") if isinstance(score, dict) else None
            if isinstance(metrics, dict):
                signals = dict(metrics)

        artifact_paths: dict[str, str] = {}
        if result.finalization is not None:
            for key, value in result.finalization.artifact.artifacts.items():
                artifact_paths[str(key)] = str(value)

        return RunRow(
            instance_id=result.instance_id,
            strategy_name=result.strategy_name,
            stop_reason=result.stop_reason.value,
            strict_success=result.strict_success,
            selected_hypothesis_id=result.selected_hypothesis_id,
            candidate_count=result.candidate_count,
            signals=signals,
            artifact_paths=artifact_paths,
        )


# ---------------------------------------------------------------------------
# Built-in registry
# ---------------------------------------------------------------------------


def _toy_adapter_factory(_extras: dict[str, Any]):
    from adapters_v10.toy import ToyTextAdapter

    return ToyTextAdapter()


def _toy_run_instance_factory(record: dict[str, Any], extras: dict[str, Any]) -> RunInstance:
    raw_workspace_root = str(extras.get("workspace_root_root", "") or "").strip()
    if raw_workspace_root:
        workspace_root = Path(raw_workspace_root).expanduser()
    else:
        workspace_root = Path(extras.get("out_dir", ".")) / "_toy_ws"
    workspace_root = Path(workspace_root) / str(record["instance_id"])
    workspace_root.mkdir(parents=True, exist_ok=True)
    return RunInstance(
        instance_id=str(record["instance_id"]),
        adapter_name="toy_text",
        objective=str(record.get("objective", "echo expected")),
        metadata={
            "workspace_root": str(workspace_root),
            "expected": str(record.get("expected", "")),
        },
    )


def _toy_candidate_provider_factory(adapter, extras: dict[str, Any]):
    from core_v10.contracts import Candidate, CandidateKind

    def provide(observation, instance):
        expected = observation.data.get("expected", "")
        answer = (
            str(extras.get("toy_wrong_answer", "__wrong__"))
            if extras.get("toy_initial_wrong", False)
            else expected
        )
        return [
            Candidate(
                candidate_id=f"{instance.instance_id}-c0",
                kind=CandidateKind.TEXT,
                payload={"answer": answer},
                origin="builtin_toy",
            )
        ]

    return provide


def _toy_repair_provider_factory(adapter, extras: dict[str, Any]):
    from core_v10.contracts import Candidate, CandidateKind

    def provide(feedback, original, observation, instance):
        return [
            Candidate(
                candidate_id=f"{original.candidate_id}-repair",
                kind=CandidateKind.TEXT,
                payload={"answer": observation.data.get("expected", "")},
                origin="builtin_toy_repair",
            )
        ]

    return provide


def _toy_operator_provider_factory(adapter, extras: dict[str, Any]):
    from scripts.bench.providers import make_toy_exact_answer_operator_provider

    return make_toy_exact_answer_operator_provider(adapter, extras)


def _migrationbench_adapter_factory(extras: dict[str, Any]):
    from adapters_v10.migrationbench.adapter import MigrationBenchAdapterV10
    from adapters_v10.migrationbench.verifier import OfficialEvaluator

    evaluator: OfficialEvaluator | None = None
    if extras.get("official_eval", True):
        root = extras.get("migrationbench_root", "external/MigrationBench")
        evaluator = OfficialEvaluator(
            migrationbench_root=root,
            timeout_seconds=float(extras.get("official_timeout_seconds", 1800.0)),
        )
    return MigrationBenchAdapterV10(
        official_evaluator=evaluator,
        timeout_seconds=float(extras.get("workspace_timeout_seconds", 600.0)),
    )


def _migrationbench_run_instance_factory(
    record: dict[str, Any], extras: dict[str, Any]
) -> RunInstance:
    workspace_root = Path(
        extras.get(
            "workspace_root_root",
            Path(extras.get("out_dir", ".")) / "_workspaces",
        )
    ).expanduser()
    instance_root = workspace_root / str(record["instance_id"])
    instance_root.mkdir(parents=True, exist_ok=True)
    artifacts_root = Path(
        extras.get(
            "artifacts_root",
            Path(extras.get("out_dir", ".")) / "artifacts",
        )
    ).expanduser()
    artifacts_dir = artifacts_root / str(record["instance_id"])
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    return RunInstance(
        instance_id=str(record["instance_id"]),
        adapter_name="migrationbench_v10",
        objective=str(
            record.get(
                "objective",
                f"Migrate {record.get('repo_url', '?')} to Java {record.get('target_java', 17)}",
            )
        ),
        metadata={
            "workspace_root": str(instance_root),
            "artifacts_dir": str(artifacts_dir),
            "instance": {
                "instance_id": str(record["instance_id"]),
                "repo_url": str(record["repo_url"]),
                "base_commit": str(record["base_commit"]),
                "target_java": int(record.get("target_java", 17)),
                "migration_mode": str(record.get("migration_mode", "minimal")),
                "stratum": dict(record.get("stratum") or {}),
                "stats": dict(record.get("stats") or {}),
                "source": str(record.get("source", "migrationbench_selected")),
            },
            "prepare": bool(extras.get("prepare", True)),
        },
    )


def _migrationbench_candidate_provider_factory(adapter, extras: dict[str, Any]):
    if extras.get("use_llm_providers", False):
        from scripts.bench.providers_llm import (
            make_migrationbench_llm_initial_provider,
        )
        return make_migrationbench_llm_initial_provider(adapter, extras)
    from scripts.bench.providers import make_migrationbench_deterministic_provider

    return make_migrationbench_deterministic_provider(adapter, extras)


def _migrationbench_repair_provider_factory(adapter, extras: dict[str, Any]):
    if extras.get("use_llm_providers", False):
        from scripts.bench.providers_llm import (
            make_migrationbench_llm_repair_provider,
        )
        return make_migrationbench_llm_repair_provider(adapter, extras)
    from scripts.bench.providers import make_migrationbench_noop_repair_provider

    return make_migrationbench_noop_repair_provider(adapter, extras)


def _migrationbench_operator_provider_factory(adapter, extras: dict[str, Any]):
    from scripts.bench.providers import make_migrationbench_operator_provider

    return make_migrationbench_operator_provider(adapter, extras)


def default_registry() -> HarnessRegistry:
    """Return the built-in registry wired with the toy and MigrationBench adapters."""

    return HarnessRegistry(
        adapter_factories={
            "toy": _toy_adapter_factory,
            "migrationbench": _migrationbench_adapter_factory,
        },
        candidate_provider_factories={
            "toy": _toy_candidate_provider_factory,
            "migrationbench": _migrationbench_candidate_provider_factory,
        },
        repair_provider_factories={
            "toy": _toy_repair_provider_factory,
            "migrationbench": _migrationbench_repair_provider_factory,
        },
        operator_provider_factories={
            "toy": _toy_operator_provider_factory,
            "migrationbench": _migrationbench_operator_provider_factory,
        },
        run_instance_factories={
            "toy": _toy_run_instance_factory,
            "migrationbench": _migrationbench_run_instance_factory,
        },
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="scripts.bench.harness", description=__doc__)
    parser.add_argument("--adapter", required=True, help="Adapter name registered in the registry.")
    parser.add_argument(
        "--strategy",
        default="agentless_basic",
        choices=(
            "agentless_basic",
            "branching_repair",
            "stigmergic_blackboard",
            "stigmergic_scheduler",
            "operator_search",
        ),
    )
    parser.add_argument("--subset", required=True, type=Path, help="Path to a JSONL subset.")
    parser.add_argument("--out-dir", required=True, type=Path, help="Campaign output directory.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--max-candidates", type=int, default=1)
    parser.add_argument("--max-repair-rounds", type=int, default=0)
    parser.add_argument("--max-repairs-per-candidate", type=int, default=1)
    parser.add_argument(
        "--extras",
        default="{}",
        help="JSON string with adapter-specific extras (workspace roots, etc.).",
    )
    return parser


def main(argv: Sequence[str] | None = None, *, registry: HarnessRegistry | None = None) -> int:
    args = build_parser().parse_args(argv)
    extras = json.loads(args.extras or "{}")
    extras.setdefault("out_dir", str(args.out_dir))
    options = HarnessOptions(
        adapter_name=args.adapter,
        strategy_name=args.strategy,
        subset_path=Path(args.subset),
        out_dir=Path(args.out_dir),
        seed=int(args.seed),
        limit=args.limit,
        max_candidates=int(args.max_candidates),
        max_repair_rounds=int(args.max_repair_rounds),
        max_repairs_per_candidate=int(args.max_repairs_per_candidate),
        extras=extras,
    )
    used_registry = registry or default_registry()
    summary = BenchHarness(options, used_registry).run()
    print(json.dumps(summary.to_dict(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())


__all__ = [
    "BenchHarness",
    "HarnessOptions",
    "HarnessRegistry",
    "build_parser",
    "default_registry",
    "main",
]
