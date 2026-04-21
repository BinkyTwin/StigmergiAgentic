# Sprint 09 — Persistent Skills, Protocol Artifacts, and Protocol Compiler Artifact

## Sprint scope

Sprint 9 implements the three thesis-facing claims on top of the Sprint 8 V6 runtime:

1. **C1 — Objective-conditioned protocol generation** (`T3`)
   - `DomainAdapter.compile_protocol()` optional contract
   - `ProtocolSpec` schema + `SYSTEM_PROTOCOL_COMPILER` prompt
   - `AssistantAdapter.compile_protocol()` and `TravelPlannerAdapter.compile_protocol()`
   - Fallback to `initial_markers()` when compilation fails or is disabled

2. **C2 — Cross-run skill accumulation** (`T1`)
   - `skills_store` (`pheromones/skills.db`) separate from session-isolated run store
   - `Environment._maybe_promote_to_skill()` promotes lesson markers to skill markers when `quality_score >= lesson_threshold` and `usage_count >= promotion_min_uses`
   - `Agent._recall_skills()` reads top-k persistent skills from the cross-run snapshot
   - Config surface: `skill_library.enabled`, `skill_library.read_only`, `reinforcement.promotion_min_uses`

3. **C3 — Cross-run coordination improvement** (`T2`)
   - `protocols_store` (`pheromones/protocols.db`) with three slots per namespace: `baseline`, `latest`, `best`
   - `MarkerStore.save_protocol_marker()` / `load_protocol_marker()`
   - `compute_protocol_score()` and `clamp_cross_run_adaptations()` (helpers already present) now wired in `main.py`
   - `_persist_protocol()` saves `latest`, creates immutable `baseline`, and updates `best` only when score improves
   - `_maybe_apply_cross_run_protocol()` loads `best` and applies clamped adaptations before each run

## Current artifact behavior

### Skill Library (C2)

When `skill_library.enabled=true` and `read_only=false`:
- `Environment.apply_action_result()` calls `_maybe_promote_to_skill()` after each successful action.
- The method inspects `ActionResult.metadata["credited_lesson_ids"]`.
- For each credited lesson, it increments `usage_count` on the lesson marker in the run store.
- When `usage_count >= promotion_min_uses` and `quality_score >= lesson_threshold`, a `skill` marker is upserted into `skills_store`.
- Skill ID format: `skill::{adapter_name}::{lesson_id}`.
- Skill payload carries: `skill_text`, `context_fingerprint`, `quality_score`, `usage_count`, `domain`.
- Skill intensity is initialized from `quality_score` and uses the very low `decay_rates_by_type.skill` (default 0.005).

Agents receive skills through `EnvironmentSnapshot.skills`, populated by `Environment.snapshot()` when `skill_library.enabled=true`.

### Protocol Artifacts (C3)

When `protocol.enabled=true` and `emergence.cross_run.enabled=true`:
- At startup, `main.py` calls `_maybe_apply_cross_run_protocol(config, protocol_store, namespace)`.
- It loads `coordination_protocol::{adapter}::{config_hash}::best` and `::baseline`.
- Adaptations are clamped with `clamp_cross_run_adaptations(adaptations, baseline["config"], max_total_delta)`.
- Clamped values are written back into the live `config` dict via dotted-path `_set_config_path()`.
- After the run, `_persist_protocol()` computes `compute_protocol_score(evaluation)` and saves:
  - `latest` — always overwritten
  - `baseline` — created once, never updated
  - `best` — updated only if current score > best score

### Protocol Compiler (C1)

When `agents.protocol_compiler.enabled=true`:
- `main.py` calls `adapter.compile_protocol(objective, config, llm_client)` before seeding markers.
- The adapter sends a structured compiler prompt to the LLM and expects a `ProtocolSpec`.
- The spec is validated (allowed actions, DAG acyclicity) and converted to seed markers.
- On validation failure or missing LLM, the runtime falls back to `adapter.initial_markers()` without raising.
- Both `AssistantAdapter` and `TravelPlannerAdapter` implement `compile_protocol()`.

## Public interfaces and contracts

### Config surfaces

- `skill_library.enabled` (bool, default false)
- `skill_library.read_only` (bool, default false)
- `skill_library.db_path` (str, default `"pheromones/skills.db"`)
- `protocol.enabled` (bool, default false)
- `protocol.read_only` (bool, default false)
- `protocol.db_path` (str, default `"pheromones/protocols.db"`)
- `reinforcement.promotion_min_uses` (int, default 2)
- `reinforcement.lesson_threshold` (float, default 0.7)
- `emergence.cross_run.enabled` (bool, default false)
- `emergence.cross_run.read_only` (bool, default false)
- `emergence.cross_run.max_total_delta` (float, default 0.15)
- `markers.decay_rates_by_type.skill` (float, default 0.005)
- `markers.decay_rates_by_type.coordination_protocol` (float, default 0.01)

### Core runtime additions

- `core.marker_store.MarkerStore`
  - `save_protocol_marker(slot, namespace, payload, agent_id)` -> `Marker`
  - `load_protocol_marker(slot, namespace)` -> `dict | None`
- `core.environment.Environment`
  - `__init__(..., skills_store: MarkerStore | None, adapter_name: str)`
  - `_maybe_promote_to_skill(agent_id, result, quality_score)`
  - `_build_skill_context_fingerprint(lesson)`
- `core.agent.StigmergicAgent`
  - `_recall_skills(snapshot, top_k)` -> `list[dict]`
  - `perceive_and_decide()` now includes skills in `Decision.lesson_markers`
- `core.tool_registry.ActionResult`
  - `metadata` may contain `credited_lesson_ids: list[str]` (convention now documented in dataclass)

### Main.py runtime wiring

- `_maybe_build_skills_store(config)` -> `MarkerStore | None`
- `_maybe_build_protocol_store(config)` -> `MarkerStore | None`
- `_build_protocol_namespace(config, adapter_name)` -> `str`
- `_maybe_apply_cross_run_protocol(config, protocol_store, namespace)` -> `bool`
- `_persist_protocol(result, evaluation, config, protocol_store, namespace, session_id)` -> `None`
- `_set_config_path(config, path, value)` -> `None`

## Guardrails and constraints

- All Sprint 9 features are **opt-in** and **disabled by default**; Sprint 8 behavior is preserved when configs are absent or false.
- `skill_library.read_only=true` prevents skill promotion but still allows skill recall.
- `emergence.cross_run.read_only=true` prevents protocol persistence but still allows loading.
- `MarkerStore(session_isolation=False)` is used for both `skills_store` and `protocol_store` to guarantee cross-run visibility.
- Baseline protocol markers are append-only semantics: once written, they are never overwritten by `_persist_protocol()`.
- `clamp_cross_run_adaptations` enforces `max_total_delta` per config path to prevent runaway drift.

## Known limits / not executed in this session

- No benchmark campaign was executed in this session (operator-run next step).
- Pareto instrumentation aligned with V2 runtime is still pending.
- CodeMigration adapter (V2) and SWE-bench adapter are not implemented.
- Full 3-seed paired validation for V5-full vs V6-base is still operator-run.
- `langgraph` dependency is optional; the supervisor baseline test is skipped when absent.

## Validation evidence

- Sprint 8 non-regression: `uv run pytest tests/unit/test_config.py tests/unit/test_marker_store.py tests/unit/test_environment.py tests/unit/test_agent.py tests/unit/test_orchestrator.py tests/unit/test_travelplanner_tools.py -q` -> **81 passed** (threshold ≥ 77)
- Sprint 9 existing tests: `uv run pytest tests/unit/test_emergence.py tests/unit/test_protocol_compiler.py -q` -> **14 passed**
- Sprint 9 new unit tests: `uv run pytest tests/unit/test_environment_skill_promotion.py tests/unit/test_protocol_persistence.py -q` -> **13 passed**
- Sprint 9 integration tests: `uv run pytest tests/integration/test_skill_persistence.py tests/integration/test_protocol_cross_run.py tests/integration/test_protocol_compiler_integration.py -q` -> **18 passed**
- **Full suite** (excluding optional langgraph): **307 passed**

## Files created or modified

- `core/tool_registry.py` — document `credited_lesson_ids` convention
- `core/environment.py` — add `skills_store`, `_maybe_promote_to_skill()`, `_build_skill_context_fingerprint()`
- `core/agent.py` — add `_recall_skills()`, include skills in decision context
- `core/marker_store.py` — add `save_protocol_marker()`, `load_protocol_marker()`
- `main.py` — wire skills_store, protocol_store, cross-run apply/persist helpers
- `adapters/travelplanner/adapter.py` — implement `compile_protocol()`
- `tests/unit/test_environment_skill_promotion.py` — new
- `tests/unit/test_protocol_persistence.py` — new
- `tests/integration/test_skill_persistence.py` — new
- `tests/integration/test_protocol_cross_run.py` — new
- `tests/integration/test_protocol_compiler_integration.py` — new
