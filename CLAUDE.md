# CLAUDE.md

This file provides guidance to Claude Code when working in this repository.

## Project Overview

Stigmergic orchestration framework V3 for thesis research (EMLV).

The codebase is currently at **Sprint 9 complete** (C1/C2/C3 fully implemented on top of Sprint 8 V6 baseline).

## Sprint 9 Complete Status (2026-04-21)

Implemented modules:
- `core/marker.py`
- `core/marker_store.py`
- `core/decay.py`
- `core/schemas.py`
- `core/dependency.py`
- `core/reinforcement.py`
- `core/emergence.py`
- `core/guardrails.py`
- `core/audit.py`
- `core/config.py`
- `core/tool_registry.py`
- `core/pressure.py`
- `core/environment.py`
- `core/agent.py`
- `core/orchestrator.py`
- `adapters/base.py`
- `adapters/assistant/__init__.py`
- `adapters/assistant/adapter.py`
- `adapters/assistant/workspace.py`
- `adapters/travelplanner/__init__.py`
- `adapters/travelplanner/adapter.py`
- `adapters/travelplanner/workspace.py`
- `adapters/travelplanner/tools.py`
- `adapters/travelplanner/evaluator.py`
- `adapters/travelplanner/langgraph_supervisor.py`
- `tools/__init__.py`
- `tools/file_read.py`
- `tools/file_write.py`
- `tools/bash_exec.py`
- `tools/web_search.py`
- `tools/think.py`
- `tools/decompose.py`
- `llm/client.py`
- `llm/prompts.py`
- `config/default.yaml`
- `config/assistant.yaml`
- `config/travelplanner.yaml`
- `config/travelplanner_adapt.yaml`
- `config/travelplanner_eval.yaml`
- `config/travelplanner_v4_only.yaml`
- `config/ablation/v5_full.yaml`
- `config/ablation/v6_base.yaml`
- `config/ablation/v6_A.yaml`
- `config/ablation/v6_B.yaml`
- `config/ablation/v6_C.yaml`
- `main.py`
- `scripts/setup_travelplanner.py`
- `scripts/run_travelplanner_framework_benchmark.py`
- `scripts/tune_aco_travelplanner.py`
- `tests/unit/*` + `tests/integration/*` (307 passed total, including Sprint 9 skill promotion, protocol persistence, and protocol compiler integration tests)

Validated gate:
- Sprint 8 non-regression: `uv run pytest tests/unit/test_config.py tests/unit/test_marker_store.py tests/unit/test_environment.py tests/unit/test_agent.py tests/unit/test_orchestrator.py tests/unit/test_travelplanner_tools.py -q` -> 81 passed
- Sprint 9 existing: `uv run pytest tests/unit/test_emergence.py tests/unit/test_protocol_compiler.py -q` -> 14 passed
- Sprint 9 new unit: `uv run pytest tests/unit/test_environment_skill_promotion.py tests/unit/test_protocol_persistence.py -q` -> 13 passed
- Sprint 9 integration: `uv run pytest tests/integration/test_skill_persistence.py tests/integration/test_protocol_cross_run.py tests/integration/test_protocol_compiler_integration.py -q` -> 18 passed
- Full suite (excluding optional langgraph): 307 passed

## Design Principles

- Coordination medium first: markers are the single shared trace primitive.
- Separation of concerns: adapters provide domain logic through tool contracts.
- Strong governance: traceability, budget checks, retry limits, lock TTL.
- Auditability by default: append-only JSONL events with before/after payloads.
- Role-free agents: same agent logic, specialization through pressures, local sensing, and marker availability.
- Backward compatibility first: stigmergic-correction features are opt-in via config.
- Extend the medium, not the agent source: Sprint 9 groundwork keeps self-improvement in persistent artifacts and optional protocol compilation paths.

## Runtime Model

```text
snapshot -> decide (parallel, optional local sensing) -> lock arbitration
-> execute (parallel) -> deposit (transactional)
-> maintain (TTL + decay + optional frequentation)
-> optional emergence feedback adaptation
```

Stop conditions:
- `all_terminal`
- `idle_cycles`
- `budget_exhausted`
- `max_ticks`

## Marker State Machine Defaults

```text
pending -> active -> completed -> verified -> terminal
pending -> active -> failed -> retry -> pending
any -> skipped
any -> escalated
```

The state machine remains configurable and validated through `StateMachine`.

## Persistence Model

- Store: SQLite file `pheromones/markers.db`
- Mode: `WAL`
- Transaction model: `BEGIN IMMEDIATE` on all mutations
- Audit stream: `pheromones/audit_log.jsonl`
- Optional read-tracking table: `marker_reads`
- Optional lock-attempt table: `marker_lock_events`

## Current Public API Surface

### `core.marker`
- `Marker`
- `StateMachine`
- `InvalidMarkerError`
- `InvalidTransitionError`

### `core.marker_store`
- `MarkerStore`
- `MarkerStoreError`

Important V6 additions:
- `record_lock_attempt`
- `lock_stats`
- `lock_stats_snapshot`

### `core.guardrails`
- `GuardrailEngine`
- `BudgetExceededError`
- `TraceabilityError`
- `ScopeLockError`

### `core.tool_registry`
- `Decision`
- `ActionResult`
- `RepairRequest`
- `ValidationResult`
- `build_repair_marker_id`
- `Tool`
- `ToolRegistry`

`ActionResult.metadata` may contain `credited_lesson_ids` for lesson-to-skill promotion.

### `core.pressure`
- `compute_pressures`
- `select_action`

`compute_pressures` now accepts optional `heuristic_fn(marker, action)` for ACO heuristic substitution.

### `core.environment`
- `Environment`
- `EnvironmentSnapshot`

### `core.agent`
- `StigmergicAgent`
- `AgentAffinityProfile`
- `AgentMemory`
- `MemoryEntry`

### `core.orchestrator`
- `Orchestrator`
- `TickRow`
- `OrchestratorResult`

`OrchestratorResult` now includes `emergence_summary`, and the runtime can optionally use emergent contention resolution plus in-memory emergence feedback adaptation.
It can also use the V6 `recovery_controller`, dynamic idle, and per-tick `TickRow.control` telemetry.

### `llm.client`
- `LLMClient`
- `LLMResponse`
- `ModelPricing`

### `tools`
- `register_infrastructure_tools`
- `FileReadTool`
- `FileWriteTool`
- `BashExecTool`
- `WebSearchTool`
- `ThinkTool`
- `DecomposeTool`

### `adapters.assistant`
- `AssistantAdapter`
- `LocalWorkspace`

`AssistantAdapter` and `TravelPlannerAdapter` both expose an opt-in `compile_protocol()` path that transforms objectives into executable task DAGs when enabled and backed by an LLM.

### `adapters.travelplanner`
- `TravelPlannerAdapter`
- `TravelPlannerWorkspace`
- `TravelPlannerEvaluator`

## Commands

### Setup

```bash
uv python install 3.11
uv venv --python 3.11 .venv
uv pip install -r requirements.txt
```

### Test (Sprint 9)

```bash
# Non-regression Sprint 8
uv run pytest tests/unit/test_config.py tests/unit/test_marker_store.py tests/unit/test_environment.py tests/unit/test_agent.py tests/unit/test_orchestrator.py tests/unit/test_travelplanner_tools.py -q

# Sprint 9 existing
uv run pytest tests/unit/test_emergence.py tests/unit/test_protocol_compiler.py -q

# Sprint 9 new
uv run pytest tests/unit/test_environment_skill_promotion.py tests/unit/test_protocol_persistence.py -q
uv run pytest tests/integration/test_skill_persistence.py tests/integration/test_protocol_cross_run.py tests/integration/test_protocol_compiler_integration.py -q

# Smoke test
uv run python main.py --adapter travelplanner --config config/travelplanner_adapt.yaml --objective "Query 0"
```

### Benchmark Campaigns (Docker — mandatory)

**All future benchmark campaigns must run inside Docker containers.** See `docker-compose.campaign.yml`.

```bash
# Qwen campaign (Terminal 1)
OPENROUTER_API_KEY=$(grep OPENROUTER_API_KEY .env | cut -d= -f2) \
  docker compose -f docker-compose.campaign.yml up qwen-campaign

# Gemma campaign (Terminal 2)
OPENROUTER_API_KEY_2=$(grep OPENROUTER_API_KEY .env.key2 | cut -d= -f2) \
  docker compose -f docker-compose.campaign.yml up gemma-campaign

# Analyze results
uv run python scripts/analyze_campaign.py campaign_results/qwen
uv run python scripts/analyze_campaign.py campaign_results/gemma
```

## Coding Rules

- Python 3.11+, strict type hints
- explicit exception classes for invalid state/contract violations
- concise docstrings on public classes/methods
- no hidden side-effects in store APIs
- preserve append-only audit semantics

## Documentation and Thesis Traceability

For each significant delivery:
- append `documentation/construction_log.md`
- add/update ADR in `documentation/decisions/`
- keep `AGENTS.md` and `CLAUDE.md` synchronized

For each sprint closure (mandatory):
- update or create `documentation/redisgn_v2/sprint_XX_artifact.md`
- include: sprint scope, current artifact behavior, public interfaces, guardrails, known limits, and validation evidence

## Knowledge Governance

Use project-local knowledge only:
- `.codex/knowledge/captures.md`
- `.codex/knowledge/playbook.md`
- `.codex/knowledge/decision_log.md`

Add exactly one capture per task, with 1-3 reusable patterns and concrete evidence.
