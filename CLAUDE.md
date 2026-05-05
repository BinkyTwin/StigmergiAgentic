# CLAUDE.md

This file provides guidance to Claude Code when working in this repository.

## Project Overview

Stigmergic orchestration framework for thesis research (EMLV).

**Current direction (2026-05-03)** : pivot V10 *from-scratch* en cours. L'architecture V3 (Sprint 9 complet) est figée comme baseline historique reproductible sur la branche `archive/v3-sprint9`. Le code actif évolue dans une nouvelle ligne `core_v10/` indépendante de `core/` legacy. Voir :
- `documentation/redisgn_v2/plan_v10_from_scratch_rebuild.md` — plan technique canonique (architecture, phases A0..A6, ablations).
- `documentation/redisgn_v2/pivot_v10_documentation_memoire.md` — documentation mémoire (problématique, diagnostic, reformulation scientifique, hypothèses H1/H2/H3/H4).
- `documentation/decisions/20260503-pivot-v10-from-scratch.md` — ADR-018 du pivot.

V3 (Sprint 9) reste documentée ci-dessous comme état du code legacy. Toute nouvelle fonctionnalité doit être implémentée dans `core_v10/` selon le plan canonique.

### Phase 4 V10 livrée (2026-05-04) — MigrationBench V10 + bench harness unifié

L1→L7 du plan canonique livrées : `adapters_v10/migrationbench/{schemas, workspace, maven, verifier, adapter}.py`, `scripts/bench/{harness, telemetry, artifacts, providers, docker}.py`, service Docker `migrationbench-v10-smoke`, config `config/v10/migrationbench_v10_smoke_deepseek.yaml`. **126 tests V10 verts** (121 unit + 5 integration). Le `MigrationBenchVerifier` émet les 8 signaux canoniques (`patch_delivered`, `patch_applies`, `compile_success`, `test_success`, `class_version_ok`, `dependency_policy_ok`, `official_success`, `strict_success`). Invariant strict respecté : `strict_success=True` exige la chaîne complète apply→compile→test→class_version 61→official `Success=True`. Le fallback diagnostique V7.2 `_synthesize_best_partial_payload` n'a aucun équivalent (testé par AST scan). Aucune fuite d'import legacy (`core/`, `adapters/`) dans `core_v10/`, `adapters_v10/`, `scripts/bench/`.

Smoke run via Docker (clone `external/MigrationBench` au premier lancement) :

```bash
DEEPSEEK_API_KEY=$(grep DEEPSEEK_API_KEY .env | cut -d= -f2) \
  docker compose -f docker-compose.campaign.yml up migrationbench-v10-smoke
```

Le summary est dérivé de l'EventLog par `scripts.bench.telemetry.replay_summary_from_dir` ; `live==replay` est testé en intégration (`tests/integration/v10/test_migrationbench_smoke_consistency.py`).

### Phase 5 V10 livrée (2026-05-04) — BranchingRepair A3 (dedup + suppression + selector explicable)

Surface `core_v10/strategy_runner.py` durcie : `_SignatureTracker` (sha256(kind+payload) sur 16 hex), events `candidate.deduped` / `candidate.repeat_failure_suppressed` / `selection.completed`, dataclass `SelectionRationale` (id sélectionné, reason, score, compétiteurs ordonnés). `StrategyResult` expose `selection_rationale`, `dedup_skipped`, `repeat_failure_suppressed`. `scripts/bench/telemetry.py` propage ces compteurs au summary (`dedup_skipped_total`, `repeat_failure_suppressed_total`, `instances[*].selection_rationale`) — toujours reconstructibles depuis l'EventLog. Nouveau module `scripts/bench/compare_strategies.py` exécute A1/A2/A3 sur la même fixture et écrit `comparison.json`. **136 tests V10 verts** (+10 vs Phase 4). A2 livré comme placeholder linear-repair (`branching_repair` avec `max_candidates=1`) ; la couche typed-blackboard complète (capability auto-election) reste un follow-up Phase 3. Voir `documentation/redisgn_v2/phase_05_artifact.md` et ADR-019.

Comparaison A1/A2/A3 sur le smoke MigrationBench :

```bash
.venv/bin/python -m scripts.bench.compare_strategies \
  --adapter migrationbench \
  --subset fixtures/migrationbench/subsets/smoke_5.jsonl \
  --out-dir campaign_results/v10/migrationbench_smoke_compare \
  --extras '{"out_dir": "campaign_results/v10/migrationbench_smoke_compare", "official_eval": false}'
```

### Phase 6 V10 livrée (2026-05-05) — StigmergicBlackboard A4 (`core_v10/signals.py` + `signal_policy.py` + `run_stigmergic_blackboard`)

Plan canonique §"Phase 6 — StigmergicBlackboard A4" (lignes 891-903) livré : `core_v10/signals.py` étendu avec `SignalRecord` / `SignalStore` (active write surface + decay half-life), nouveau module `core_v10/signal_policy.py` (politique pure feedback→signaux : `INHIBIT failure_type:*`, `INHIBIT anti:preserve_existing_tests`, `SUPPORT origin:*`, `REINFORCE kind:*`, `INHIBIT signature:*`, `NOVELTY hypothesis_space`), `StrategyRunner.run_stigmergic_blackboard()` qui réutilise toute la mécanique A3 et ajoute (1) tri/filtrage du frontier par `support_for(origin)`, (2) drop signal-driven si `INHIBIT signature ≥ 0.8`, (3) update policy après chaque verify, (4) digest top-3 attaché à `Observation.data["stigmergic_digest"]` pour le repair_provider, (5) départage finalize par signal_score. Events canoniques : `signal.emitted` (un par mutation, record sérialisé) et `signal.applied` (un par décision modifiée, `effect ∈ {drop, reorder, finalize_tiebreak}`). Telemetry étendue avec `pheromone_hit_rate` (NOVELTY exclus), `feedback_reuse_rate`, `repeated_failure_suppression_total` — toutes reconstructibles depuis l'EventLog. Invariant strict : **A4 ≡ A3 quand le SignalStore reste cosmétique** (vérifié par `test_a4_equals_a3_when_signal_store_stays_empty`). `SignalStore.from_events()` rejoue les `signal.emitted` events vers le store live (parity prouvée par `test_a4_signal_store_snapshot_is_reconstructible_from_events`). ADR pré-registré `documentation/decisions/20260505-phase-6-stigmergic-blackboard-a4.md`. **202 tests V10 verts** (162 + 40 Phase 6).

**Campagne main_30 A3 vs A4 (1 seed × 30 × DeepSeek)** : A3 strict 1/30, A4 strict 1/30 (instance `comic__con`), A4 émet 236 `signal.emitted` et 1 `signal.applied` (instance `citymonstret__rorledning`, `effect=finalize_tiebreak`, `target=origin:llm_repair_deepseek-chat_t0`, `intensity=0.700`). A4 a sélectionné des hypothèses différentes de A3 sur 3/30 instances (toutes celles ayant atteint compile+test). Gain en strict_success = 0 à ce budget × 1 seed (verrou `official_eval` Phase 5 inchangé). Live==replay parity ✓ sur les 2 bras. Voir `documentation/redisgn_v2/phase_06_ablation_main30.md`.

Comparaison A3 vs A4 sur smoke MigrationBench (Docker, DeepSeek `deepseek-chat`, providers LLM activés, sans digest) :

```bash
DEEPSEEK_API_KEY=$(grep DEEPSEEK_API_KEY .env | cut -d= -f2) \
  docker compose -f docker-compose.campaign.yml up ablation-a3-vs-a4-smoke
```

Comparaison A3 vs A4 sur main_30 :

```bash
DEEPSEEK_API_KEY=$(grep DEEPSEEK_API_KEY .env | cut -d= -f2) \
  docker compose -f docker-compose.campaign.yml up ablation-a3-vs-a4-main30
```

Le `comparison.json` final est écrit dans `campaign_results/v10/ablation_a3_vs_a4_<smoke|main30>/`.

## Sprint 9 Complete Status (2026-04-21) — legacy `core/`

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

# MigrationBench V7 (repair colony) — surface opt-in
uv run pytest tests/unit/test_migrationbench_v7_repair_colony.py tests/unit/test_orchestrator.py tests/unit/test_migrationbench_adapter.py tests/unit/test_migrationbench_workspace.py -q

# MigrationBench V7.1 smoke gate — mandatory before main_30
uv run python scripts/migrationbench_smoke_gate.py \
  --config config/migrationbench_v7_repair_colony_deepseek.yaml \
  --subset fixtures/migrationbench/subsets/smoke_5.jsonl \
  --out-dir campaign_results/migrationbench_v7_smoke_gated

# Smoke test
uv run python main.py --adapter travelplanner --config config/travelplanner_adapt.yaml --objective "Query 0"
```

### Benchmark Campaigns (Docker — mandatory)

**All future benchmark campaigns must run inside Docker containers.** See `docker-compose.campaign.yml`.

#### MigrationBench V7 — repair colony (opt-in, 2026-04-30)

Le bras `stigmergic_v7_repair_colony` est branché en parallèle de `stigmergic_v6_static`, sans le remplacer. Il introduit :
- boucle fermée `inspect → localize → propose candidate → apply branch → build → classify failure → repair marker → retest → finalize` ;
- patchs candidats isolés par branche (`MigrationBenchWorkspace.branch_workspace` / `fork_branch_workspace`) ;
- nouveaux outils dans `adapters/migrationbench/tools.py` avec taxonomie `pom_parse_error`, `dependency_resolution_error`, `compile_error`, `test_failure`, `class_version_error`, `patch_apply_error`, `official_eval_failed` ;
- pool d'agents élastique opt-in dans `core/orchestrator.py` (clé `agents.num_agents_mode: elastic`) ;
- métriques `repair_cycles`, `llm_calls`, `branch_count`, `best_branch_id`, `failure_taxonomy`, `dynamic_agents_*`, `caps_hit` exposées dans le contrat de sortie.

V7.1 (2026-05-02) durcit ce bras sans toucher V6 :
- modèle principal conservé : `deepseek-v4-flash` ;
- normalisation/retry des edits typés LLM, rejet des edits vides/hors surface Maven/Java ;
- validation official-like avec class versions Java 17 exactement `{61}` ;
- sélection stricte sauf sortie explicite `best_partial_finalization` ;
- lessons désactivées via `lessons.enabled: false` + garde runtime ;
- `scripts/migrationbench_smoke_gate.py` bloque `main_30` tant que les gates techniques ne passent pas.

Lancement Docker (le service `migrationbench-campaign` accepte `MIGRATION_CONFIG` et `MIGRATION_FRAMEWORKS`). Pour comparer V6 et V7, lancer le service deux fois avec le même `MIGRATION_OUT_DIR` mais des `MIGRATION_CONFIG`/`MIGRATION_FRAMEWORKS` différents :

```bash
# Build une fois si l'image n'existe pas encore
docker compose -f docker-compose.campaign.yml build migrationbench-campaign

# V6 static (référence)
DEEPSEEK_API_KEY=$(grep DEEPSEEK_API_KEY .env | cut -d= -f2) \
MIGRATION_CONFIG=config/migrationbench_v6_static_deepseek.yaml \
MIGRATION_FRAMEWORKS="stigmergic_v6_static" \
MIGRATION_OUT_DIR=campaign_results/migrationbench_v6v7 \
MIGRATION_SUBSET=fixtures/migrationbench/subsets/main_30.jsonl \
  docker compose -f docker-compose.campaign.yml up migrationbench-campaign

# V7 repair colony (opt-in)
DEEPSEEK_API_KEY=$(grep DEEPSEEK_API_KEY .env | cut -d= -f2) \
MIGRATION_CONFIG=config/migrationbench_v7_repair_colony_deepseek.yaml \
MIGRATION_FRAMEWORKS="stigmergic_v7_repair_colony" \
MIGRATION_OUT_DIR=campaign_results/migrationbench_v6v7 \
MIGRATION_SUBSET=fixtures/migrationbench/subsets/main_30.jsonl \
  docker compose -f docker-compose.campaign.yml up migrationbench-campaign

# Agrégation V6 vs V7
uv run python scripts/aggregate_migrationbench_comparison.py \
  --campaign-root campaign_results/migrationbench_v6v7 \
  --output-dir output/migrationbench_v6v7_comparison
```

Smoke test rapide hors Docker (sans evaluator officiel, surface V7 uniquement) :

```bash
uv run python scripts/run_migrationbench_framework_benchmark.py \
  --framework stigmergic_v7_repair_colony \
  --subset fixtures/migrationbench/subsets/smoke_5.jsonl \
  --out-dir campaign_results/migrationbench_v7_smoke \
  --config config/migrationbench_v7_repair_colony_deepseek.yaml \
  --skip-official-eval
```

#### Pilote historique (Qwen / Gemma full-sweep — déprécié, abandonné 2026-04-22)

```bash
OPENROUTER_API_KEY=$(grep OPENROUTER_API_KEY .env | cut -d= -f2) \
  docker compose -f docker-compose.campaign.yml up qwen-campaign
OPENROUTER_API_KEY_2=$(grep OPENROUTER_API_KEY .env.key2 | cut -d= -f2) \
  docker compose -f docker-compose.campaign.yml up gemma-campaign
```

#### Campagne scientifique finale (2026-04-22)

Voir `documentation/redisgn_v2/decision_log_model_switch.md`.

Modèles :
- Principal : Gemma (`google/gemma-4-31b-it` sur OpenRouter).
- Fort (stigmergie uniquement) : DeepSeek V3 (`deepseek-chat`, `https://api.deepseek.com/v1`, clé `DEEPSEEK_API_KEY`).
- Stress-test : Qwen 3.5 9B — **résultat pré-calculé** dans `output/travelplanner_framework_compare/v6c_retry_20260420_seed42/v6_C/seed42/` (23,88 % final_pass, pas de re-run).

Périmètre :
- Stigmergie = **C3 uniquement** (skills + protocols read-only + cross_run).
- Baselines Gemma : `solo_direct`, `solo_cot`, `solo_self_refine`, `planner_executor` (fixé), `langgraph_supervisor`, `metagpt_sequential` (nouveau).
- 1 seed par modèle (limitation assumée, cf. "Threats to validity").

Services Docker (3 clés distinctes, parallélisables) :

```bash
# Terminal 1 — baselines Gemma (clé OPENROUTER_API_KEY_2 via .env.key2)
OPENROUTER_API_KEY_2=$(grep OPENROUTER_API_KEY .env.key2 | cut -d= -f2) \
  docker compose -f docker-compose.campaign.yml up gemma-baselines

# Terminal 2 — stigmergie C3 DeepSeek (clé DEEPSEEK_API_KEY via .env)
docker compose -f docker-compose.campaign.yml up deepseek-stigmergie

# Terminal 3 (parallèle ou séquentiel) — stigmergie C3 Gemma (clé OPENROUTER_API_KEY via .env)
docker compose -f docker-compose.campaign.yml up gemma-stigmergie

# Agrégation
uv run python scripts/aggregate_campaign_comparison.py \
  --gemma campaign_results/gemma-stigmergie \
  --deepseek campaign_results/deepseek-stigmergie \
  --baselines campaign_results/gemma-baselines \
  --qwen-fixture output/travelplanner_framework_compare/v6c_retry_20260420_seed42/v6_C/seed42/benchmark_summary.json
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
