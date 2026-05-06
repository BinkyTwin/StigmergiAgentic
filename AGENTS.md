# AGENTS.md

This file provides guidance to GitHub Copilot / Codex when working in this repository.

## Project Overview

Stigmergic orchestration framework for a Master's thesis (EMLV).

**Current direction (2026-05-03)** : pivot V10 *from-scratch* en cours. L'architecture V3 (Sprint 9 complet) est figée comme baseline historique reproductible sur la branche `archive/v3-sprint9`. Le code actif évolue dans une nouvelle ligne `core_v10/` indépendante de `core/` legacy. Voir :
- `documentation/redisgn_v2/plan_v10_from_scratch_rebuild.md` — plan technique canonique (architecture, phases A0..A6, ablations).
- `documentation/redisgn_v2/pivot_v10_documentation_memoire.md` — documentation mémoire (problématique, diagnostic, reformulation scientifique, hypothèses H1/H2/H3/H4).
- `documentation/decisions/20260503-pivot-v10-from-scratch.md` — ADR-018 du pivot.

Justification scientifique du pivot : les campagnes V6/V7/V7.1/V7.2 sur MigrationBench main_30 ont plafonné à 0–1/30 strict_success ; la télémétrie V3 a été identifiée comme mécaniquement incohérente (divergence de 73 points entre `patch_applies` et `artifact_delivery` sur V7.2) ; l'apprentissage cross-run du Sprint 9 n'a jamais produit de promotion de skill sur >1000 runs. La nouvelle question de recherche reformule la contribution autour de l'hybridation mesurable entre coordination explicite (blackboard typé + verifier loop + HypothesisGraph) et coordination indirecte (couche stigmergique opt-in mesurée par ablation A4 vs A3).

V3 (Sprint 9) reste documentée ci-dessous comme état du code legacy. Toute nouvelle fonctionnalité doit être implémentée dans `core_v10/` selon le plan canonique.

### Phase 4 V10 livrée (2026-05-04) — MigrationBench V10 + bench harness unifié

L1→L7 du plan canonique livrées en 7 itérations `/loop` autonomes. Modules ajoutés :
- `adapters_v10/migrationbench/{schemas, workspace, _runtime, maven, verifier, adapter}.py` — adapter V10 complet implémentant `DomainAdapterV10` (setup/observe/capabilities/apply/validate/diagnose/finalize/score), `MigrationBenchVerifier` qui exécute la chaîne stricte `mvn dependency:resolve → clean compile → test → class_version 61 → official run_eval.py` et émet les 8 signaux canoniques.
- `scripts/bench/{harness, telemetry, artifacts, providers, docker}.py` — harness CLI unifié, registry pluggable adapter+provider+run_instance, deterministic POM Java 17 candidate provider sans LLM, reconstruction télémétrique pure depuis EventLog.
- `config/v10/migrationbench_v10_smoke_deepseek.yaml` + service Docker `migrationbench-v10-smoke` dans `docker-compose.campaign.yml`.

Invariants prouvés :
- 126 tests V10 verts (121 unit + 5 integration golden).
- `strict_success=True` exige la chaîne complète ; aucun fallback diagnostique passif n'existe (testé par AST scan dans `tests/integration/v10/test_migrationbench_smoke_consistency.py::test_no_passive_partial_payload_fallback_anywhere_in_adapters_v10`).
- `live_summary == replay_summary_from_dir(out_dir)` (testé golden) — la télémétrie ne ment pas.
- Cloison étanche : aucun `from core.` ou `from adapters.` dans `core_v10/`, `adapters_v10/`, `scripts/bench/`.

### Phase 5 V10 livrée (2026-05-04) — BranchingRepair A3

Modules durcis / ajoutés :
- `core_v10/strategy_runner.py` : dataclass `SelectionRationale` (id, reason, score, compétiteurs ordonnés), classe interne `_SignatureTracker` (sha256(kind+payload), 16 hex), events `candidate.deduped` / `candidate.repeat_failure_suppressed` / `selection.completed`, payload `run.completed` étendu (`dedup_skipped`, `repeat_failure_suppressed`).
- `scripts/bench/telemetry.py` : `InstanceSummary` et `Summary` étendues (`dedup_skipped`, `repeat_failure_suppressed`, `selection_rationale`, `dedup_skipped_total`, `repeat_failure_suppressed_total`). Reconstructibles depuis EventLog → `live==replay` invariant préservé même sur les campagnes legacy pré-Phase 5.
- `scripts/bench/compare_strategies.py` (nouveau) : ablation harness A1 `agentless_basic` / A2 placeholder linear-repair / A3 branching parallel. CLI + API programmatique avec `arms=[AblationArm(...)]` configurable. Écrit un campaign tree par bras + un `comparison.json` agrégé.
- Tests : `tests/unit/v10/test_strategy_runner_phase5.py` (6) + `tests/unit/v10/bench/test_compare_strategies.py` (4) → **136 V10 verts** (+10).

Limites assumées :
- A2 = placeholder `branching_repair` avec `max_candidates=1` (linear-repair). La couche typed-blackboard complète (capability auto-election, knowledge sources) relève d'un follow-up Phase 3.
- Comparaison MigrationBench `main_30` non exécutée ici (campagne Docker LLM). Le harness `compare_strategies` est prêt à être pointé vers `fixtures/migrationbench/subsets/main_30.jsonl`.

ADR : `documentation/decisions/20260504-phase5-a3-branching-repair.md`.
Artifact : `documentation/redisgn_v2/phase_05_artifact.md`.

### Phase 7 V11 livrée (2026-05-06) — Stigmergic Medium Kernel MVP

V11 garde V10 comme socle de vérification/replay et ajoute un médium
stigmergique causal actif, conformément à
`documentation/redisgn_v2/plan_v11_stigmergic_medium_kernel.md`.

Modules ajoutés :
- `core_v10/stigmergy/{events,records,affordances,medium,scheduler}.py` :
  `StigmergicMediumKernel`, `Affordance`, `SignalRead`,
  `DecisionInfluence`, `TrajectoryDivergence`, `WorkerActivation`.
- `core_v10/operators/text_operator.py` : `ExactReplaceText` guardé
  (aucun replace_text si l'ancien span n'est pas présent).
- `adapters_v10/migrationbench/operators/maven.py` : operators Maven
  exact-match (`MavenSetCompilerRelease`, compiler/surefire upgrades,
  JAXB dependency insertion).
- `core_v10/strategy_runner.py` : nouveaux bras
  `run_stigmergic_scheduler()` (B5) et `run_operator_search()` (B6),
  events `signal.read`, `affordance.created/consumed`,
  `worker.eligible/selected/activated/output`, `decision.influenced`,
  `trajectory.diverged`, `operator.invoked/applied/failed`.
- `scripts/bench/telemetry.py` : métriques causales replayables
  (`signal_read_total`, `decision_influenced_total`,
  `trajectory_divergence_total`, `stigmergic_causality_rate`,
  `unused_signal_rate`, `unused_affordance_rate`, `operator_*`).
- `scripts/bench/compare_strategies.py --ladder v11` : ladder B2/B5/B6.
- `scripts/v11/run_v11_smoke.py` + service Docker `v11-smoke`.

Invariants prouvés :
- B2 contrôle sans événements causaux V11 ; B5/B6 produisent la chaîne
  `signal.emitted -> signal.read -> worker.activated ->
  decision.influenced -> trajectory.diverged`.
- B6 invoque et applique des operators typés sur le microbench toy, avec
  `live_summary == replay_summary_from_dir(out_dir)`.
- 9 tests V11 verts, 40 tests Phase 6 V10 verts, 43 tests ciblés
  harness/MigrationBench/import-boundaries verts.

Durcissement post-audit (2026-05-06) :
- `StigmergicScheduler` score tous les couples `(worker, affordance)`.
- `StigmergicMediumKernel.from_events()` rejoue
  `affordance.consumed/expired/inhibited`, `signal.retired` et
  `signal.decayed`.
- Les operator candidates MigrationBench ont `parent_id=original.candidate_id`;
  les upgrades Maven plugin sont scopés au bloc `<plugin>`.
- La télémétrie V11 compte seulement les influences `changed=true` et détecte
  les harms dans les deltas structurés.
- `scripts/v11/run_v11_smoke.py` nettoie les sorties réutilisées pour préserver
  `live==replay`.
- Validation hardening : 15 tests V11 verts, 41 tests runner/harness ciblés,
  40 tests V10 signal/strategy/imports verts, Docker `v11-smoke` vert après
  rebuild.

Gate MigrationBench `main_30` (2026-05-06) :
- `scripts/v11/run_v11_migrationbench_campaign.py` est le chemin de lancement
  B2/B5/B6 : nettoyage workspace, isolation par bras, replay parity, rapport
  `v11_readiness_report.json`, divergence pairwise B2-vs-B5/B6.
- `scripts/bench/compare_strategies.py` scope automatiquement
  `workspace_root_root`, `artifacts_root` et `out_dir` par `arm_id`.
- `scripts/bench/telemetry.py` expose
  `replacement_count_too_low_total/rate`.
- Services Docker : `v11-migrationbench-smoke` (smoke contrôlé) et
  `v11-migrationbench-main30` (subset `main_30`, official eval + LLM par
  défaut).
- Commande main_30 :
  `DEEPSEEK_API_KEY=$(grep DEEPSEEK_API_KEY .env | cut -d= -f2) docker compose -f docker-compose.campaign.yml up v11-migrationbench-main30`.

Limites assumées :
- B3/B4 passifs et B7 memory verifier-gated restent des follow-ups.
- Aucun claim MigrationBench `main_30` V11 n'est formulé avant smoke causal
  réel et comparaison contrôlée.

ADR : `documentation/decisions/20260506-v11-stigmergic-medium-kernel.md`.
Artifact : `documentation/redisgn_v2/phase_07_artifact.md`.

## Sprint 9 Complete (Legacy `core/`)

## Current Scope (Sprint 9 Complete — C1/C2/C3)

Implemented:
- `core/marker.py` — generic marker model + configurable state machine + `last_active_at`
- `core/marker_store.py` — SQLite (WAL) transactional marker store + locks + lock-attempt telemetry + differential decay + read tracking/frequentation + pruning + SQL queries + optional session isolation + `save_protocol_marker` / `load_protocol_marker`
- `core/decay.py` — intensity/inhibition decay + per-marker-type decay + read-time effective intensity
- `core/schemas.py` — Pydantic schemas for structured LLM/tool outputs + `ProtocolSpec`
- `core/dependency.py` — DAG validation, topological ordering, unblocked filtering
- `core/reinforcement.py` — success reinforcement + backward propagation + frequentation boost
- `core/emergence.py` — 8-run emergence metrics from tick rows + audit collaboration parsing + feedback adaptations + cross-run protocol score/clamp helpers
- `core/guardrails.py` — deep norms (budget, retry limit, lock TTL, traceability)
- `core/audit.py` — append-only JSONL audit trail
- `core/config.py` + `config/default.yaml` — V3 config sections + V6 recovery/stickiness/targeted-repair validation + Sprint 9 opt-in sections (`skill_library`, `protocol`, `cross_run`, `protocol_compiler`)
- `core/tool_registry.py` — tool contracts + action registry + generic validation/repair contract
- `core/pressure.py` — pressure computation + softmax action selection + optional ACO `heuristic_fn`
- `core/environment.py` — runtime wrapper with reinforcement + propagation + time-decayed snapshots + control overlays + targeted repair-marker deposit + `_maybe_promote_to_skill`
- `core/agent.py` — dependency-aware candidate selection (`unblocked_markers`) + episodic memory recall/reinforcement + local-sensing affinity profile + V6 stickiness/recovery-aware targeting + `_recall_skills` from cross-run store
- `core/orchestrator.py` — parallel tick loop + async execution + session_id + emergence summary + emergent conflict resolution + feedback loop + V6 recovery controller/dynamic idle
- `adapters/base.py` — domain adapter/objective/workspace contracts + optional `compile_protocol()`
- `adapters/assistant/*` — generic assistant adapter + local workspace context summarization + objective-conditioned protocol compiler
- `adapters/travelplanner/*` — TravelPlanner workspace + domain tools + adapter + evaluator + `compile_protocol()`
- `adapters/travelplanner/langgraph_supervisor.py` — LangGraph supervisor scientific baseline
- `tools/*` — infrastructure tools (`file_read`, `file_write`, async `bash_exec`, `web_search`, typed `think`, bounded DAG-aware `decompose`)
- `llm/client.py` + `llm/prompts.py` — provider-aware sync+async client with structured response validation, memory/lesson prompt contexts, and protocol-compiler prompt
- `main.py` — multi-adapter CLI (`assistant`, `travelplanner`) with per-run session_id, session DB path, DAG/reinforcement metadata + emergence dashboard + compile/fallback seeding path
- `config/assistant.yaml` — assistant mode overrides
- `config/travelplanner.yaml` — TravelPlanner mode overrides
- `config/travelplanner_adapt.yaml` — Sprint 9 adaptation/train preset scaffold
- `config/travelplanner_eval.yaml` — Sprint 9 frozen-eval preset scaffold
- `config/travelplanner_v4_only.yaml` — V4-only ablation preset
- `config/ablation/v5_full.yaml` — V5-full execution preset (`max_ticks=80`, `num_agents=6`)
- `config/ablation/v6_base.yaml` / `v6_A.yaml` / `v6_B.yaml` / `v6_C.yaml` — V6 phase-1 ablation presets
- `scripts/setup_travelplanner.py` — dataset/database setup helper
- `scripts/run_travelplanner_framework_benchmark.py` — framework benchmark runner with inclusive `--start/--end` aliases and subset-aware official scoring
- `scripts/tune_aco_travelplanner.py` — train-only ACO grid tuner that updates `config/ablation/v5_full.yaml`
- `tests/unit/*` + `tests/integration/*` — V6 runtime tests + Sprint 9 skill promotion, protocol persistence, and protocol compiler integration tests (307 passed total)

Not implemented yet:
- CodeMigration adapter (V2)
- SWE-bench adapter
- Pareto instrumentation aligned with V2 runtime

Opt-in extension (2026-04-30):
- `adapters/migrationbench/*` — MigrationBench adapter with two coexisting bras :
  - `stigmergic_v6_static` (existant) — `inspect → propose_patch → run_build → finalize_patch`.
  - `stigmergic_v7_repair_colony` (nouveau, opt-in via `migrationbench.framework` ou `migrationbench.workflow`) — boucle fermée `inspect → localize → propose candidate → apply branch → build → classify failure → repair marker → retest → finalize`, patchs candidats isolés par branche (`branch_workspace` / `fork_branch_workspace`), taxonomie d'échecs typée (`pom_parse_error`, `dependency_resolution_error`, `compile_error`, `test_failure`, `class_version_error`, `patch_apply_error`, `official_eval_failed`).
- `core/orchestrator.py` — pool d'agents homogènes élastique opt-in via `agents.num_agents_mode: elastic` + bloc `agents.elastic` (`min_agents`, `max_agents`, `markers_per_agent`, `scale_up_utilization`, `scale_down_contention`, `scale_down_idle_utilization`). Resize audité (`agent_pool_resize`) et exposé via `OrchestratorResult.emergence_summary["agent_pool"]`.
- `config/migrationbench_v7_repair_colony_deepseek.yaml` — preset du bras V7 avec DeepSeek + safety caps (`max_tokens_per_instance`, `max_runtime_per_instance_seconds`, `max_llm_calls_per_instance`, `max_repair_cycles_per_instance`).
- `docker-compose.campaign.yml` — service `migrationbench-campaign` accepte `MIGRATION_CONFIG` et `MIGRATION_FRAMEWORKS` (override pour V7 sans nouvelle image).
- Métriques de sortie additionnelles : `repair_cycles`, `llm_calls`, `branch_count`, `best_branch_id`, `failure_taxonomy`, `dynamic_agents_min/max/avg`, `caps_hit`.

V7.1 hardening (2026-05-02):
- `deepseek-v4-flash` remains the MigrationBench primary model for V7.1.
- V7 edit parsing normalizes common LLM variants before strict `TypedEditSet` validation, retries schema failures once, and rejects empty/irrelevant edits.
- Official-like validation now requires Java 17 class major versions exactly `{61}` before normal patch selection.
- V7 lessons are explicitly disabled through `lessons.enabled: false` and a runtime workflow guard.
- `scripts/migrationbench_smoke_gate.py` is the required technical gate before rerunning `main_30`.

## Campaign Execution (Docker — Mandatory)

**All future benchmark campaigns must run inside Docker containers.** The `docker-compose.campaign.yml` provides isolated services with separate `skills.db`, `protocols.db`, and `campaign_results/` per container. This prevents:
- macOS bash expansion bugs (`{a,b,c}` not supported on default `/bin/sh`)
- File-system conflicts between parallel runs
- Cross-contamination of protocol namespaces between presets

Since 2026-04-22 the final scientific campaign uses three new services: `gemma-stigmergie`, `gemma-baselines`, `deepseek-stigmergie`. Legacy `qwen-campaign` / `gemma-campaign` services remain for pilot work but are no longer used for memoir-grade comparisons. See `documentation/redisgn_v2/decision_log_model_switch.md` for design decisions and `## Commands` below for usage.

## Architecture Baseline

### Marker Model

All inter-agent coordination traces are represented as `Marker` objects.

Required fields include:
- identity: `id`, `marker_type`, `target`
- signal: `intensity`, `state`, `payload`
- traceability: `created_by`, `created_at`, `updated_by`, `updated_at`, `last_active_at`
- coordination: `lock_owner`, `lock_tick`, `inhibition`, `retry_count`, `history`

### Marker Store

`core.marker_store.MarkerStore` is the persistence API:
- SQLite file: `pheromones/markers.db`
- `PRAGMA journal_mode=WAL`
- atomic mutations (`BEGIN IMMEDIATE`)
- append-only audit in `pheromones/audit_log.jsonl`

Public methods:
- `upsert_marker`
- `get_marker`
- `get_by_type_target`
- `query_markers`
- `acquire_lock`
- `release_lock`
- `record_lock_attempt`
- `apply_decay`
- `apply_frequentation`
- `maintain_locks`
- `record_read`
- `read_count`
- `lock_stats`
- `lock_stats_snapshot`
- `snapshot`

### Agent Runtime

`core.orchestrator.Orchestrator` executes the tick loop:
1. environment maintenance (TTL + decay)
   - optional frequentation reinforcement during maintenance
2. snapshot
   - optional recovery-control overlay on top of the persisted marker field
3. parallel `perceive_and_decide`
4. lock arbitration (sequential or emergent weighted contention resolution)
5. parallel `execute`
6. sequential deposit via `Environment.apply_action_result`
   - optional targeted repair-marker materialization
7. optional emergence feedback adaptation
8. stop-condition checks (`all_terminal`, `idle_cycles`, `budget_exhausted`, `max_ticks`)

### Guardrails

Deep norms are environment-enforced, not agent-enforced:
- token/cost budget ceilings
- retry overflow (`retry_count > max_retry_count`)
- lock TTL expiration
- traceability metadata checks

## Project Structure (Current)

```text
core/
  __init__.py
  marker.py
  marker_store.py
  decay.py
  schemas.py
  dependency.py
  reinforcement.py
  emergence.py
  guardrails.py
  audit.py
  config.py
  tool_registry.py
  pressure.py
  environment.py
  agent.py
  orchestrator.py

adapters/
  __init__.py
  base.py
  assistant/
    __init__.py
    adapter.py
    workspace.py
  travelplanner/
    __init__.py
    adapter.py
    workspace.py
    tools.py
    evaluator.py

tools/
  __init__.py
  file_read.py
  file_write.py
  bash_exec.py
  web_search.py
  think.py
  decompose.py

llm/
  __init__.py
  client.py
  prompts.py

config/
  default.yaml
  assistant.yaml
  travelplanner.yaml
  travelplanner_adapt.yaml
  travelplanner_eval.yaml
  travelplanner_v4_only.yaml
  ablation/
    v5_full.yaml

scripts/
  setup_travelplanner.py
  run_travelplanner_framework_benchmark.py
  tune_aco_travelplanner.py

tests/
  conftest.py
  fixtures/
    mock_adapter.py
  unit/
    test_marker.py
    test_decay.py
    test_guardrails.py
    test_audit.py
    test_marker_store.py
    test_pressure.py
    test_agent.py
    test_orchestrator.py
    test_llm_client.py
    test_file_tools.py
    test_bash_tool.py
    test_assistant_adapter.py
    test_travelplanner_workspace.py
    test_travelplanner_tools.py
    test_travelplanner_adapter.py
    test_travelplanner_evaluator.py
    test_agent_memory.py
    test_emergence.py
    test_config.py
    test_protocol_compiler.py
  integration/
    test_assistant_run.py
    test_travelplanner.py
```

## Commands

### Environment

```bash
uv python install 3.11
uv venv --python 3.11 .venv
uv pip install -r requirements.txt
```

### Sprint 8 validation

```bash
uv run pytest tests/unit/test_config.py tests/unit/test_marker_store.py tests/unit/test_environment.py tests/unit/test_agent.py tests/unit/test_orchestrator.py tests/unit/test_travelplanner_tools.py -q
uv run pytest tests/integration/test_travelplanner.py -q
uv run python main.py --adapter travelplanner --config config/ablation/v6_A.yaml --objective "Query 0"
```

### Benchmark Campaigns (Docker — mandatory for parallel multi-model runs)

**All future benchmark campaigns must run inside Docker containers.** This guarantees:
- Isolation between models (separate `skills.db`, `protocols.db`, `campaign_results/`)
- GNU bash compatibility (avoids macOS `{a,b,c}` expansion bugs)
- Full reproducibility (same environment everywhere)
- True parallelism (no file-system conflicts)

```bash
# Build image once
docker compose -f docker-compose.campaign.yml build
```

#### Legacy pilot services (Qwen / Gemma full-sweep, déprécié 2026-04-22)

```bash
# Qwen full-sweep (pilot — no longer used for final comparisons)
OPENROUTER_API_KEY=$(grep OPENROUTER_API_KEY .env | cut -d= -f2) \
  docker compose -f docker-compose.campaign.yml up qwen-campaign

# Gemma full-sweep (pilot)
OPENROUTER_API_KEY_2=$(grep OPENROUTER_API_KEY .env.key2 | cut -d= -f2) \
  docker compose -f docker-compose.campaign.yml up gemma-campaign
```

#### Final scientific campaign (2026-04-22)

Design decisions in `documentation/redisgn_v2/decision_log_model_switch.md`.

Primary model: **Gemma** (`google/gemma-4-31b-it` via OpenRouter).
Strong model (stigmergy only): **DeepSeek V3** (`deepseek-chat`,
`DEEPSEEK_API_KEY`, `https://api.deepseek.com/v1`).
Stress-test model: **Qwen 3.5 9B** — pre-computed, reused from
`output/travelplanner_framework_compare/v6c_retry_20260420_seed42/v6_C/seed42/`
(23.88% final_pass, no re-run).

Scope: stigmergy = **C3 only**. Baselines (Gemma): `solo_direct`, `solo_cot`,
`solo_self_refine`, `planner_executor` (fixed 2026-04-22),
`langgraph_supervisor`, `metagpt_sequential` (new).

Limitation: **1 seed per model** (to be cited in "Threats to validity").

```bash
# Terminal 1 — Gemma baselines (OPENROUTER_API_KEY_2)
OPENROUTER_API_KEY_2=$(grep OPENROUTER_API_KEY .env.key2 | cut -d= -f2) \
  docker compose -f docker-compose.campaign.yml up gemma-baselines

# Terminal 2 — DeepSeek × stigmergy C3 (DEEPSEEK_API_KEY from .env)
docker compose -f docker-compose.campaign.yml up deepseek-stigmergie

# Terminal 3 — Gemma × stigmergy C3 (OPENROUTER_API_KEY from .env)
docker compose -f docker-compose.campaign.yml up gemma-stigmergie
```

**Analyze results:**

```bash
uv run python scripts/aggregate_campaign_comparison.py \
  --gemma campaign_results/gemma-stigmergie \
  --deepseek campaign_results/deepseek-stigmergie \
  --baselines campaign_results/gemma-baselines \
  --qwen-fixture output/travelplanner_framework_compare/v6c_retry_20260420_seed42/v6_C/seed42/benchmark_summary.json
```

#### MigrationBench V7 repair colony (opt-in, 2026-04-30)

Le bras `stigmergic_v7_repair_colony` est branché sur le service Docker `migrationbench-campaign`. Le service accepte deux variables d'environnement supplémentaires : `MIGRATION_CONFIG` (chemin du YAML) et `MIGRATION_FRAMEWORKS` (liste). Pour comparer V6 et V7, lancer le service deux fois avec un `MIGRATION_OUT_DIR` distinct par bras.

```bash
# V6 static (DeepSeek) — référence dans campaign_results/migrationbench_v6v7/
DEEPSEEK_API_KEY=$(grep DEEPSEEK_API_KEY .env | cut -d= -f2) \
MIGRATION_CONFIG=config/migrationbench_v6_static_deepseek.yaml \
MIGRATION_FRAMEWORKS="stigmergic_v6_static" \
MIGRATION_OUT_DIR=campaign_results/migrationbench_v6v7 \
MIGRATION_SUBSET=fixtures/migrationbench/subsets/main_30.jsonl \
  docker compose -f docker-compose.campaign.yml up migrationbench-campaign

# V7 repair colony (DeepSeek) — second run dans le même MIGRATION_OUT_DIR
DEEPSEEK_API_KEY=$(grep DEEPSEEK_API_KEY .env | cut -d= -f2) \
MIGRATION_CONFIG=config/migrationbench_v7_repair_colony_deepseek.yaml \
MIGRATION_FRAMEWORKS="stigmergic_v7_repair_colony" \
MIGRATION_OUT_DIR=campaign_results/migrationbench_v6v7 \
MIGRATION_SUBSET=fixtures/migrationbench/subsets/main_30.jsonl \
  docker compose -f docker-compose.campaign.yml up migrationbench-campaign

# Agrégation V6 vs V7 (référence par défaut = stigmergic_v6_static)
uv run python scripts/aggregate_migrationbench_comparison.py \
  --campaign-root campaign_results/migrationbench_v6v7 \
  --output-dir output/migrationbench_v6v7_comparison
```

Smoke test rapide (sans evaluator officiel, surface V7) :

```bash
uv run python scripts/run_migrationbench_framework_benchmark.py \
  --framework stigmergic_v7_repair_colony \
  --subset fixtures/migrationbench/subsets/smoke_5.jsonl \
  --out-dir campaign_results/migrationbench_v7_smoke \
  --config config/migrationbench_v7_repair_colony_deepseek.yaml \
  --skip-official-eval
```

Smoke gate V7.1 obligatoire avant `main_30` :

```bash
DEEPSEEK_API_KEY=$(grep DEEPSEEK_API_KEY .env | cut -d= -f2) \
  uv run python scripts/migrationbench_smoke_gate.py \
    --config config/migrationbench_v7_repair_colony_deepseek.yaml \
    --subset fixtures/migrationbench/subsets/smoke_5.jsonl \
    --out-dir campaign_results/migrationbench_v7_smoke_gated
```

## Code Style Guidelines

- Python 3.11+
- type hints on public functions/methods
- PEP 8
- focused functions and explicit errors
- all comments and docs in English

## Error Handling Policy

- Validation errors: raise explicit `ValueError` subclasses
- Store runtime errors: raise `MarkerStoreError`
- Guardrail breaches: raise dedicated guardrail exceptions
- Preserve append-only audit semantics for all marker mutations

## Documentation Requirements

When Sprint scope changes, update all of:
- `AGENTS.md`
- `CLAUDE.md`
- `documentation/construction_log.md`
- relevant ADR in `documentation/decisions/`

For every sprint closure (mandatory):
- update or create `documentation/redisgn_v2/sprint_XX_artifact.md`
- describe the current artifact behavior, interfaces, guardrails, limits, and validation evidence
- keep file naming as `sprint_XX_artifact.md`

## Knowledge Loop (Mandatory)

At end of task:
1. Add exactly one capture entry in `.codex/knowledge/captures.md`
2. Update reusable patterns in `.codex/knowledge/playbook.md`
3. Append one decision in `.codex/knowledge/decision_log.md`

## Git Workflow

- Branch prefix: `codex/`
- Commit convention: `type(scope): description`
- Keep atomic commits by concern (`chore`, `feat`, `test`, `docs`)
