# Project Captures

## 2026-05-04 — Phase 4 V10 MigrationBench + Bench Harness Unified (L1→L7)

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `9/10`
- `confidence`: `high`
- `scope`: `Port MigrationBench to V10 stack with verifier-first contract and EventLog-derived telemetry, in 7 autonomous /loop iterations.`

### Outcome
Livré Phase 4 du plan canonique en 7 itérations `/loop` autonomes. `adapters_v10/migrationbench/` implémente `DomainAdapterV10` complet (workspace isolé, verifier émettant 8 signaux canoniques, invariant strict_success non-contournable). `scripts/bench/` unifie le harness CLI Docker-first avec télémétrie reconstructible depuis EventLog seul. Service Docker `migrationbench-v10-smoke` prêt. **126 tests V10 verts** (121 unit + 5 integration golden). Aucune fuite legacy `core/`/`adapters/`. Aucun équivalent du fallback V7.2 `_synthesize_best_partial_payload` (testé par AST scan dédié).

### Reusable Patterns (1-3)
1. **Validation locale ≠ scoring strict** : la `ValidationResult.PASSED` peut se contenter de la chaîne locale verte ; le score final reste gate par l'official evaluator dans `score()`. Permet à `_finalize_best_validated` d'avancer sans court-circuiter le verifier-first contract.
2. **Telemetry pure-EventLog** : tout métrique scientifique doit être reconstructible par `replay_summary_from_dir(out_dir) == live_summary`. Les compteurs runtime sont interdits — c'est l'invariant qui rend impossible de répéter le bug V7.2 d'écart `patch_applies` vs `artifact_delivery`.
3. **AST scan anti-shortcut** : pour interdire un pattern legacy par contrat de test, viser `FunctionDef.name`/`Assign.targets` plutôt que substring grep — sinon les docstrings qui documentent l'absence du pattern produisent des faux positifs.

### Evidence
- `adapters_v10/migrationbench/{schemas, workspace, _runtime, maven, verifier, adapter}.py`
- `scripts/bench/{harness, telemetry, artifacts, providers, docker}.py`
- `config/v10/migrationbench_v10_smoke_deepseek.yaml`
- `docker-compose.campaign.yml` (service `migrationbench-v10-smoke`)
- `tests/integration/v10/test_migrationbench_smoke_consistency.py`
- `documentation/construction_log.md` (entrée 2026-05-04)

## 2026-05-03 — V10 Blackboard, Branching Repair, and Toy Adapter Completion

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `9/10`
- `confidence`: `high`
- `scope`: `Extend the V10 bootstrap runtime with reconstructible blackboard state, minimal stigmergic signals, branching repair, and a deterministic toy adapter`

### Outcome

Extended the isolated V10 runtime with a reconstructible blackboard projection, typed coordination signals, A3-style branching repair, process-reward scoring from validation signals, fallback finalization across validated candidates, and a deterministic `ToyTextAdapter` for end-to-end verification before any real benchmark adapter is connected. Independent review found that repairs were not starting from parent workspaces, duplicate candidate IDs could corrupt lineage, blackboard reconstruction still depended on an in-memory graph, and artifact validation was too permissive. These issues were fixed with regression tests before closure.

### Reusable Patterns (1-3)

1. **Branching repair must execute child candidates from the parent hypothesis workspace, not from the original root workspace, or lineage becomes a lie.**
2. **A blackboard can remain a projection only if it can be rebuilt from durable events or validates the provenance of any supplied graph state.**
3. **Selectors should finalize validated candidates by evidence priority with fallback, because local validation and strict artifact success are related but not identical.**

### Evidence

- `core_v10/blackboard.py`
- `core_v10/signals.py`
- `core_v10/strategy_runner.py`
- `core_v10/verifier.py`
- `adapters_v10/toy.py`
- `tests/unit/v10/test_blackboard.py`
- `tests/unit/v10/test_strategy_runner.py`
- `tests/unit/v10/test_toy_adapter.py`
- `PYTHONDONTWRITEBYTECODE=1 uv run --isolated pytest -p no:cacheprovider tests/unit/v10 -q` -> 39 passed

## 2026-05-03 — V10 Bootstrap Runtime Implementation

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `9/10`
- `confidence`: `high`
- `scope`: `Implement the first isolated V10 runtime increment from the framework rebuild plan`

### Outcome

Created an isolated V10 namespace with domain-neutral contracts, append-only event logging, replay snapshots, explicit hypothesis graphs, verifier-gated finalization, and a minimal workflow-first `StrategyRunner`. The implementation deliberately avoids importing the legacy `core`/`adapters` packages or embedding benchmark-specific rules. Independent review found early architecture risks around branch workspace handling, graph reuse, score logging, artifact contract weakness, and append concurrency; these were fixed with regression tests before proceeding.

### Reusable Patterns (1-3)

1. **Bootstrap major runtime rewrites in an isolated namespace with import-boundary tests before touching the legacy engine.**
2. **Verifier loops must validate and finalize in the workspace returned by apply, not the original workspace, so branch isolation remains real.**
3. **Event logs and artifact contracts need hard mechanical invariants early: locked appends, non-empty required artifacts, score-aware strict success, and per-run hypothesis graphs.**

### Evidence

- `core_v10/contracts.py`
- `core_v10/event_log.py`
- `core_v10/hypothesis_graph.py`
- `core_v10/verifier.py`
- `core_v10/strategy_runner.py`
- `adapters_v10/base.py`
- `documentation/redisgn_v2/v10_starts_here.md`
- `tests/unit/v10/`
- `PYTHONDONTWRITEBYTECODE=1 uv run --isolated pytest -p no:cacheprovider tests/unit/v10 -q` -> 29 passed

## 2026-05-03 — V10 Pivot Documented With Memoir Narrative and ADR-018

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `9/10`
- `confidence`: `high`
- `scope`: `Document the V3 → V10 pivot in repository artifacts so the thesis defense can reference a coherent memoir-grade narrative, an ADR with three considered alternatives, and synchronized CLAUDE.md/AGENTS.md pointers`

### Outcome

Produced `documentation/redisgn_v2/pivot_v10_documentation_memoire.md` (7-section memoir-grade narrative covering original hypothesis, V3/V7 empirical diagnosis with three converging findings, V10 reformulation with H1/H2/H3/H4 hypotheses, ablation ladder A0..A6, threats to validity, link to thesis sections, and one-sentence defense synthesis) and `documentation/decisions/20260503-pivot-v10-from-scratch.md` (ADR-018 with three considered alternatives, academic citations, and validation criteria). Updated `CLAUDE.md`, `AGENTS.md`, `documentation/construction_log.md`, `documentation/decisions/INDEX.md` (Sprint 9 ADR-017 marked superseded), and `.codex/knowledge/decision_log.md` to point at the V10 plan and explain the scientific rationale of the pivot. The Sprint 9 status remains documented as legacy so the V3 baseline stays reproducible on `archive/v3-sprint9`.

### Reusable Patterns (1-3)

1. **When a research project pivots its founding hypothesis, write the memoir narrative before the technical plan — the academic story becomes the contract that the new architecture must serve.**
2. **Pair every architectural rupture with an ADR that names three considered alternatives, with the rejected ones argued on equal footing, so the chosen path is defensible against post-hoc reviewer challenges.**
3. **Synchronize agent-facing files (CLAUDE.md, AGENTS.md) with a one-line "Current direction" pointer plus a link to the canonical plan, before deprecating the legacy section — agents resuming work from snapshots otherwise default to the prior architecture.**

### Evidence

- `documentation/redisgn_v2/pivot_v10_documentation_memoire.md`
- `documentation/decisions/20260503-pivot-v10-from-scratch.md`
- `documentation/construction_log.md` (entrée 2026-05-03)
- `documentation/decisions/INDEX.md` (ADR 018, ADR 017 marqué déprécié)
- `CLAUDE.md`, `AGENTS.md` (sections « Current direction »)

## 2026-05-03 — V10 From-Scratch Rebuild Canonical Plan

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `10/10`
- `confidence`: `high`
- `scope`: `Rewrite Claude's StigmergiAgentic 2.0 proposal into a canonical from-scratch V10 plan with a stronger architectural rupture`

### Outcome

Created `documentation/redisgn_v2/plan_v10_from_scratch_rebuild.md` as the canonical V10 rebuild plan. The revised plan accepts Claude's hybrid blackboard plus verifier-loop pivot, but changes the architecture to a new `core_v10` line where EventLog and HypothesisGraph are the source-of-truth layers, the typed Blackboard is a reconstructible projection, strict success is verifier-gated, simple branching precedes MCTS-style search, and the stigmergic layer is tested before verifier-guided tree search so the thesis contribution is not hidden by a generic optimizer.

### Reusable Patterns (1-3)

1. **When a redesign needs a real rupture, create a new core namespace and treat legacy modules as optional references rather than architectural constraints.**
2. **Put replayable EventLog and explicit HypothesisGraph before active blackboard projections so coordination state remains auditable instead of becoming another marker soup.**
3. **Order ablations so the thesis mechanism is measured before generic optimizers that could mask its effect.**

### Evidence

- `documentation/redisgn_v2/plan_v10_from_scratch_rebuild.md`
- `documentation/redisgn_v2/plan_v10_framework_rebuild.md`

## 2026-05-03 — V10 Plug-and-Play Framework Rebuild Plan

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `9/10`
- `confidence`: `high`
- `scope`: `Create a detailed StigmergiAgentic 2.0 / V10 architecture plan after the V6/V7 MigrationBench strict-success plateau`

### Outcome

Created a detailed V10 rebuild plan that reframes StigmergiAgentic as a plug-and-play verified-resolution runtime rather than a decorative multi-agent marker loop. The plan separates adapter contracts, append-only events, active blackboard signals, hypothesis graphs, strategy runners, structured feedback, clean memory modes, and ablation arms. It also preserves the stigmergic philosophy by moving the colony claim from agent count to indirect coordination through validated traces, pheromone-like signals, branch lineages, reinforcement, inhibition, and evidence-based selection.

### Reusable Patterns (1-3)

1. **For major agent-framework rewrites, start from a contract-first architecture and an ablation ladder before adding autonomous or multi-agent complexity.**
2. **Preserve stigmergic claims through inspectable shared traces, reinforcement/inhibition signals, and hypothesis selection metrics rather than through raw agent population size.**
3. **Treat benchmarks as plug-in evaluators behind stable adapter contracts so benchmark-specific tooling cannot leak into the core runtime.**

### Evidence

- `documentation/redisgn_v2/plan_v10_framework_rebuild.md`
- Sources cited in the plan: SWE-agent, Agentless, Anthropic Effective Agents, AutoCodeRover, OpenHands, OpenAI Agents SDK, LangGraph persistence, MigrationBench, SWE-bench Pro, Multi-SWE-bench, and Heylighen's stigmergy work.

## 2026-05-03 — MigrationBench V7.2 Strict-Success Contract Repair

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `9/10`
- `confidence`: `high`
- `scope`: `Diagnosis and repair of V7.2 best-partial finalization and nested repair-marker loops after the DeepSeek main_30 strict-success plateau`

### Outcome

Diagnosed why V7.2 could report high `patch_applies` while remaining at zero `strict_success`: best-partial payloads were synthesized after orchestration without exporting `patch.diff` or running the official evaluator, so they had no path to strict success. A second bug created nested `repair::repair::...` marker chains when repair attempts emitted empty/irrelevant edits, wasting repair cycles on repair markers instead of root patch hypotheses. The adapter now evaluates best-partial branches through the common strict contract, and repair validation collapses retries back to the root patch marker while new branch payloads strip repair bookkeeping.

### Reusable Patterns (1-3)

1. **Never count an internal best-partial patch as benchmark-delivered unless it has gone through the same artifact export and official-eval contract as normal finalization.**
2. **When repair requests can repair repair markers, collapse retry targeting back to the root domain artifact to avoid recursive coordination artifacts.**
3. **For strict-success plateaus, compare `patch_applies`, local build/test flags, artifact delivery, and official eval coverage before blaming the model.**

### Evidence

- `adapters/migrationbench/adapter.py`
- `adapters/migrationbench/tools.py`
- `tests/unit/test_migrationbench_adapter.py`
- `tests/unit/test_migrationbench_v7_repair_colony.py`
- `uv run --isolated pytest tests/unit/test_migrationbench_adapter.py tests/unit/test_migrationbench_evaluator.py tests/unit/test_migrationbench_v7_repair_colony.py -q` -> 21 passed

## 2026-05-02 — MigrationBench V7.1 Repair Colony Hardening

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `9/10`
- `confidence`: `high`
- `scope`: `Implementation of the V7.1 MigrationBench repair-colony hardening plan across edit schema handling, official-like validation, finalization, lessons, isolation, smoke gating, and tests`

### Outcome

Implemented the V7.1 hardening pass for `stigmergic_v7_repair_colony` without changing V6. The arm now normalizes common LLM edit variants before strict typed validation, retries schema failures, rejects empty or irrelevant edits, extracts useful Maven feedback, traces repair history, blocks repeated repair loops, requires exact Java 17 class major versions `{61}` for normal selection, allows only explicit best-partial finalization when caps are reached, disables lessons for V7, cleans stale per-instance artifacts under `--force`, and adds a smoke-gate script before `main_30`.

### Reusable Patterns (1-3)

1. **For LLM-generated code edits, normalize permissive model output into a single strict internal schema before applying anything.** This preserves scientific comparability while avoiding artificial failures from harmless key-name variants.
2. **For hard repair benchmarks, separate technical mechanics gates from success gates.** Smoke gates should verify branch telemetry, isolation, schema recovery, and finalize paths without requiring benchmark success on a difficult corpus.
3. **For adaptive systems, disable learning artifacts during early repair-loop validation unless they are the treatment under study.** This prevents in-run lessons or skills from contaminating the mechanism being diagnosed.

### Evidence

- `adapters/migrationbench/tools.py`
- `scripts/run_migrationbench_query_export.py`
- `scripts/migrationbench_cleanup.py`
- `scripts/migrationbench_smoke_gate.py`
- `config/migrationbench_v7_repair_colony_deepseek.yaml`
- `tests/unit/test_migrationbench_v7_repair_colony.py`
- `tests/unit/test_orchestrator.py`
- `documentation/redisgn_v2/v7_1_implementation_handoff.md`
- `documentation/redisgn_v2/sprint_09_artifact.md`
- `uv run pytest tests/unit/test_migrationbench_v7_repair_colony.py tests/unit/test_orchestrator.py -q` -> 29 passed
- `uv run pytest tests/unit/test_migrationbench_adapter.py tests/unit/test_migrationbench_workspace.py tests/unit/test_migrationbench_evaluator.py -q` -> 6 passed

## 2026-04-27 — MigrationBench Handoff V2 Review

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `8/10`
- `confidence`: `high`
- `scope`: `Review of the improved MigrationBench handoff and scientific plan after agent revisions`

### Outcome

Reviewed the updated MigrationBench handoff and scientific campaign plan. The handoff now addresses the main implementation risks from the previous review: official evaluator preflight is blocking, `repo_url` is declared as the new schema field, `run_migrationbench_query_export.py` is included, workspace/patch isolation is specified, raw LLM diff generation is discouraged, SD-Feedback is prioritized over a weak local imitation, and aggregation is manifest-driven. The remaining issue is consistency debt in the long plan: older sections still mention `github_url`, Gemma-first commands/config names, and `stigmergic_v6_clean`, while the handoff now uses DeepSeek `deepseek-v4-flash` and `stigmergic_v6_static`.

### Reusable Patterns (1-3)

1. **After a handoff is tightened, scan the long master plan for stale conflicting names.** The implementation agent will follow the shortest path, but thesis readers and future scripts may still pick up older `Gemma`, `github_url`, or `v6_clean` references.
2. **When switching primary models, verify both external docs and local client support.** DeepSeek V4 Flash is documented with 1M context and 384K output, but the local client still needs pricing and reasoning-mode alignment for the new model ID.
3. **Treat official-baseline availability as an experimental artifact.** Trying SD-Feedback first and documenting failure is stronger than silently substituting a local agentless approximation.

### Evidence

- `documentation/redisgn_v2/migrationbench_implementation_handoff.md`
- `documentation/redisgn_v2/plan_migrationbench_scientific_campaign.md`
- `llm/client.py`
- DeepSeek API docs: `https://api-docs.deepseek.com/quick_start/pricing`

---

## 2026-04-27 — MigrationBench Implementation Handoff Review

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `8/10`
- `confidence`: `high`
- `scope`: `Critical review of the MigrationBench implementation handoff before execution`

### Outcome

Reviewed `documentation/redisgn_v2/migrationbench_implementation_handoff.md` against the MigrationBench scientific plan, the Deep Research integration notes, the current config toggles, and existing TravelPlanner runner/aggregator patterns. The handoff is scientifically sound because it prioritizes official evaluation, patch artifacts, strong baselines, V6 static execution, and frozen cross-run learning before any V7/C3 complexity. The main improvements are to make the external MigrationBench preflight a first-class milestone, enforce a single instance schema (`repo_url` vs `github_url`), specify patch/repository isolation semantics, and require the aggregator to use requested-instance denominators rather than only successfully parsed rows.

### Reusable Patterns (1-3)

1. **For benchmark pivots, make the official evaluator preflight a blocking artifact before adapter intelligence.** This prevents a new domain adapter from hiding scorer or environment failures.
2. **For patch-centric benchmarks, define artifact invariants before model prompts.** Empty, non-applying, unevaluated, or missing patches must be failures across every arm.
3. **For migration campaigns, reuse runner resilience patterns but harden denominators around requested instances.** Resume/checkpoint logic should never make missing outputs disappear from the scientific denominator.

### Evidence

- `documentation/redisgn_v2/migrationbench_implementation_handoff.md`
- `documentation/redisgn_v2/deep_research_report_integration.md`
- `documentation/redisgn_v2/plan_migrationbench_scientific_campaign.md`
- `scripts/run_travelplanner_framework_benchmark.py`
- `scripts/aggregate_campaign_comparison.py`

---

## 2026-04-23 — Framework Expert Guide for Thesis Documentation

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `8/10`
- `confidence`: `high`
- `scope`: `Pedagogical documentation of the StigmergiAgentic runtime, adapters, memory loops, emergence controls, and campaign workflow`

### Outcome

Created `documentation/framework_guide_expert.md` as a thesis-facing expert guide that explains the framework from first principles through concrete code paths: marker model, SQLite/WAL store, environment gatekeeping, homogeneous agent decision flow, orchestrator tick loop, pressure formulas, locks, decay/frequentation, reinforcement, lessons, skills, protocol compiler, cross-run coordination protocols, emergence metrics, adapters, tools, TravelPlanner evaluation, configs, campaign hygiene, diagnostics, and extension procedures. Added the guide to `documentation/README.md` so it is discoverable from the documentation index.

### Reusable Patterns (1-3)

1. **For thesis-facing framework documentation, explain the runtime as a signal flow before listing modules.** The reader needs the mental model `markers -> pressure -> lock -> tool -> deposited markers` before file-by-file details become meaningful.
2. **Document adaptive mechanisms by separating in-run, cross-run, and evaluation-phase state.** This keeps episodic memory, lessons, skills, and coordination protocols scientifically distinguishable.
3. **Pair architecture explanation with diagnostics.** A framework guide is more reusable when it tells future readers how to inspect summaries, marker DBs, audit logs, and persistent stores after a run.

### Evidence

- `documentation/framework_guide_expert.md`
- `documentation/README.md`

---

## 2026-04-23 — V9 Plan Implementation: Clean Train/Eval, Activated C3 Persistence, and Correct Delivery Metrics

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `9/10`
- `confidence`: `high`
- `scope`: `Implementation of the V9 campaign behavior-analysis plan across TravelPlanner campaign configs, runtime memory activation, aggregation, and tests`

### Outcome

Implemented the V9 campaign plan by moving adaptation presets to the published TravelPlanner `train` split, defaulting final Docker campaigns to `45` train-adapt queries plus `180` validation-eval queries, enabling scientific adapt-side cross-run writes, keeping C3 evaluation read-only, and separating `artifact_delivery_rate` from `official_delivery_rate` in the final aggregate exporter. The runtime now creates reusable lessons from successful `terminal` TravelPlanner markers while excluding failed validations and unvalidated terminal plans, agents credit recalled lessons on successful tool execution, and the planner context now prioritizes lower-cost candidates before prompt truncation.

### Reusable Patterns (1-3)

1. **When changing campaign denominators, update script defaults, config split overrides, and stale-output cleanup together.** Otherwise old query JSON can silently contaminate the new run.
2. **For cross-run skill promotion, gate learning on success semantics rather than terminal state alone.** TravelPlanner uses `terminal` for both successes and exhausted failures, so promotion must reject `failed` / `final_pass=false` outcomes.
3. **Keep compatibility columns but redefine public metrics around official semantics.** `delivery_rate` can remain present for downstream scripts while `artifact_delivery_rate` and `official_delivery_rate` make the ambiguity auditable.

### Evidence

- `documentation/redisgn_v2/v9_campaign_behavior_analysis.md`
- `documentation/redisgn_v2/tuto_campagne_finale.md`
- `scripts/run_gemma_stigmergie_c3_docker.sh`
- `scripts/run_deepseek_stigmergie_docker.sh`
- `scripts/run_gemma_baselines_docker.sh`
- `scripts/aggregate_campaign_comparison.py`
- `core/environment.py`
- `core/agent.py`
- `adapters/travelplanner/tools.py`
- `tests/unit/test_aggregate_campaign_comparison.py`

---

## 2026-04-23 — Sprint 9 Campaign Protocol Should Move Adaptation to TravelPlanner Train and Evaluate on Full Validation

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `9/10`
- `confidence`: `high`
- `scope`: `Methodology correction for Sprint 9/V9 TravelPlanner adaptation and evaluation split`

### Outcome

Verified locally that SwarmAgentic uses `train_45.jsonl` with `sample_step=5` (9 effective train examples) and evaluates on `validation.jsonl` with 180 queries, while the current Sprint 9 scripts split the validation set into `validation[0:90]` for adaptation and `validation[90:180]` for evaluation. The clean protocol for the next final campaign is to run adaptation on the TravelPlanner `train` split (`0-44`, or an explicit 9-query subset for SwarmAgentic parity) and evaluate C2/C3/baselines on the full validation split (`0-179`).

### Reusable Patterns (1-3)

1. **When a benchmark publishes train and validation splits, use the published train split for any persistent adaptation stage.** Manual validation slicing is weaker even if the two slices do not share exact query IDs.
2. **Distinguish split hygiene from memory toggles.** Disabling `cross_run` does not fix train/test leakage if evaluation consumes `skills.db` or `protocols.db` learned from validation queries.
3. **For TravelPlanner thesis tables, prefer full 180-query validation readouts.** This keeps comparisons aligned with SwarmAgentic, official TravelPlanner reporting, and prior Qwen V6_C evidence.

### Evidence

- `documentation/redisgn_v2/v9_campaign_behavior_analysis.md`
- `scripts/run_swarmagentic_benchmark.py`
- `scripts/run_sprint9_scientific_campaign.sh`
- `scripts/run_gemma_stigmergie_c3_docker.sh`
- `scripts/run_deepseek_stigmergie_docker.sh`
- `config/travelplanner.yaml`

---

## 2026-04-23 — V9 Campaign Readout: C3 Scores Are Usable, but Sprint 9 Persistence Was Not Activated

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `9/10`
- `confidence`: `high`
- `scope`: `Post-hoc analysis of current V9/Sprint 9 TravelPlanner campaign outputs in campaign_results/`

### Outcome

The current V9 campaign has usable Gemma/DeepSeek C3 results, but it should be treated as a diagnostic run rather than evidence for Sprint 9 cross-run self-optimization. Both C3 sets are complete at 90/90 parseable results, yet `skills.db` and `protocols.db` are empty for both models, every row reports `skills_promoted=0`, and every row reports `coordination_protocol_applied=false`. The observed behavioral frontier remains split between multi-city no-plan `idle_cycles` collapse (32/90 per model) and emitted plans that fail mostly on hard budget constraints.

### Reusable Patterns (1-3)

1. **Before interpreting a self-optimization campaign, verify store activation, not just result-file counts.** Empty `skills.db` / `protocols.db` means C2/C3 mechanisms were not empirically exercised even if config labels say C3.
2. **Separate artifact delivery from official delivery.** In this campaign, `query_results[0].delivered=true` can coexist with `evaluated_queries=0` and `No travel plan generated`, so aggregate scripts must guard against nested-field optimism.
3. **When C3 remains around the low-20% range across stronger models, prioritize orchestration and adapter repair over model swapping.** DeepSeek only improved Gemma by one query on the same slice.

### Evidence

- `documentation/redisgn_v2/v9_campaign_behavior_analysis.md`
- `campaign_results/gemma-stigmergie/c3/`
- `campaign_results/deepseek-stigmergie/c3/`
- `campaign_results/gemma-stigmergie/pheromones/skills.db`
- `campaign_results/gemma-stigmergie/pheromones/protocols.db`
- `output/final_campaign_v9_check/`

---

## 2026-04-21 — Sprint 9 Complete: Persistent Skills, Protocol Artifacts, and Protocol Compiler Are Wired and Tested

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `9/10`
- `confidence`: `high`
- `scope`: `Implementation completion of Sprint 9 C1/C2/C3: skill promotion, protocol persistence, and objective-conditioned protocol compilation`

### Outcome

All three thesis claims now have end-to-end code paths:
- C2 (skill accumulation): lesson markers are promoted to `skill` markers in `skills.db` after `usage_count >= promotion_min_uses` and `quality_score >= lesson_threshold`; agents recall them cross-run via `EnvironmentSnapshot.skills`.
- C3 (coordination improvement): emergence metrics are persisted as `coordination_protocol` markers in `protocols.db` with `baseline`/`latest`/`best` slots; the best protocol is loaded and clamped before the next run.
- C1 (protocol compilation): both `AssistantAdapter` and `TravelPlannerAdapter` implement `compile_protocol()`, with fallback to `initial_markers()` on failure.

### Reusable Patterns (1-3)

1. **When wiring cross-run persistence into an existing session-isolated store, create separate `MarkerStore` instances with `session_isolation=False` rather than mixing scopes in one database.** This avoids schema changes and keeps per-run audit semantics intact.
2. **Keep a `baseline` slot immutable when persisting adaptive protocol artifacts.** It provides a stable reference for clamping and prevents runaway config drift across long campaigns.
3. **Implement promotion side-effects in the environment (`apply_action_result`) rather than in agents.** This makes promotion policy a global guardrail, not an agent heuristic, preserving role-freeness.

### Evidence

- `core/environment.py` (`_maybe_promote_to_skill`)
- `core/agent.py` (`_recall_skills`)
- `core/marker_store.py` (`save_protocol_marker`, `load_protocol_marker`)
- `main.py` (`_maybe_build_skills_store`, `_maybe_build_protocol_store`, `_maybe_apply_cross_run_protocol`, `_persist_protocol`)
- `tests/unit/test_environment_skill_promotion.py`
- `tests/unit/test_protocol_persistence.py`
- `tests/integration/test_skill_persistence.py`
- `tests/integration/test_protocol_cross_run.py`
- `tests/integration/test_protocol_compiler_integration.py`

---

## 2026-04-20 — Revised Sprint 9 Plan: Strong Thesis Alignment Once Adaptation Is Split from Evaluation and C1 Is Framed as Protocol Generation

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `9/10`
- `confidence`: `high`
- `scope`: `Review of the revised Sprint 9 architecture for skill persistence, coordination protocols, and objective-conditioned protocol generation`

### Outcome

The revised Sprint 9 plan is substantially stronger than the initial draft. It fixes the main methodological flaw by separating `travelplanner_adapt.yaml` from `travelplanner_eval.yaml`, which keeps persistent self-optimization compatible with benchmark credibility. It also replaces manual specialist seeding with a much more defensible `objective-conditioned protocol generation` concept, and moves both functional improvement and collaboration improvement into the stigmergic medium through persistent `skill` and `coordination_protocol` artifacts. The main remaining caution is that C1 should still be defended as automatic protocol generation over a fixed tool substrate, not as unrestricted from-scratch generation of arbitrary agent systems.

### Reusable Patterns (1-3)

1. **When adding cross-run self-optimization to a thesis benchmark, always split adaptation mode from frozen evaluation mode at the config level.** This keeps learning visible without making the reported benchmark path-dependent.
2. **If a thesis claim concerns stigmergic self-organization, prefer persistent medium-level artifacts (`skill`, `coordination_protocol`) over manual specialist templates or direct code self-modification.**
3. **For "from-scratch" claims in agentic systems, the defensible unit is often protocol generation over a fixed substrate, not total generation of agents, tools, and evaluators.**

### Evidence

- `config/default.yaml`
- `config/travelplanner.yaml`
- `core/agent.py`
- `core/emergence.py`
- `core/orchestrator.py`
- `main.py`

## 2026-04-20 — Sprint 9 Auto-Organization Plan: Strong Direction, but C1 Is Too Manual and Cross-Run Adaptation Needs Strict Evaluation Hygiene

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `8/10`
- `confidence`: `high`
- `scope`: `Architectural review of the proposed Sprint 9 plan for from-scratch agent generation, inter-run agent persistence, and cross-run emergence feedback`

### Outcome

Reviewed the proposed Sprint 9 auto-organization plan against the current runtime. The overall direction is strong and philosophically aligned if adaptation stays environment-mediated and bounded, but the plan should not be implemented unchanged. Two diagnostic claims are overstated: lesson markers are already recalled by agents in-run through `StigmergicAgent._recall_lessons`, and the emergence feedback loop already exists and is enabled in ablation presets even if disabled in the default TravelPlanner config. The largest design issue is C1: manual `transport/accommodation/planning` seed templates do not validate "from-scratch agent generation" and partially reintroduce hidden roles. The largest scientific issue is C3: persistent cross-run adaptation must not be enabled in the main benchmark path without a train/adaptation vs frozen-eval protocol, otherwise evaluation becomes path-dependent and methodologically fragile.

### Reusable Patterns (1-3)

1. **Do not claim from-scratch agent generation when the domain adapter manually provides specialist templates.** That is seeded specialization, not agent-system generation from objective.
2. **Separate adaptive-training runs from frozen evaluation runs whenever cross-run memory or feedback is introduced.** Persistent adaptation across validation runs otherwise creates hidden state and weakens benchmark credibility.
3. **When seeding specialization in this runtime, distinguish `marker_type` from `action_type`.** Current local affinity is marker-type plus target-based, so seeding with action labels like `search_flights` does not shape behavior unless the affinity model itself is extended.

### Evidence

- `core/agent.py`
- `core/emergence.py`
- `core/orchestrator.py`
- `config/default.yaml`
- `config/travelplanner.yaml`
- `config/ablation/v5_full.yaml`

## 2026-04-19 — Paired-Seed V6 Readout: Stagnation Relief Shifted the Residual Failure Mass Toward Terminal-Invalid Plans

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `9/10`
- `confidence`: `high`
- `scope`: `Post-hoc analysis of the paired-seed TravelPlanner campaign v5_full vs v6_base vs v6_A over the 2026-04-18 overnight run set`

### Outcome

Analyzed the paired-seed benchmark artifacts in `output/travelplanner_framework_compare/v6_overnight_20260418/` and established a clear V6 progression. `v6_base` confirms the anti-stagnation hypothesis by cutting `idle_cycles` failures and raising delivery plus hard-constraint adherence, but it often converts early collapse into `all_terminal` yet still invalid plans rather than directly into passes. `v6_A` is the best current balance: it raises `final_pass_rate` to `23.6%`, restores delivered-plan quality close to `v5_full`, and reduces runtime plus coordination overhead relative to `v6_base`. The key insight is that the frontier has moved: the main residual problem is no longer only search continuation, but repair of terminal-invalid outputs, which makes `v6_C` the highest-value next ablation.

### Reusable Patterns (1-3)

1. **When an anti-stagnation change reduces `idle_cycles`, always track where the rescued failures migrate next.** If they mostly become `all_terminal` failures instead of passes, the next lever should be repair quality rather than more exploration time.
2. **Read `final_pass_given_delivery` together with `delivery_rate`.** A preset can look better on coverage while quietly degrading the quality of delivered plans; this distinction was essential to separate `v6_base` from `v6_A`.
3. **In this TravelPlanner stigmergic regime, better emergence looks like lower switching and higher realized parallelism, not higher collaboration density.** Successful runs consistently used fewer ticks, switched actions less, and realized more parallel work.

### Evidence

- `analysis/travelplanner_v6_benchmark_report_20260419.md`
- `output/travelplanner_framework_compare/v6_overnight_20260418/v5_full/seed42/runs.json`
- `output/travelplanner_framework_compare/v6_overnight_20260418/v5_full/seed43/runs.json`
- `output/travelplanner_framework_compare/v6_overnight_20260418/v6_base/seed42/runs.json`
- `output/travelplanner_framework_compare/v6_overnight_20260418/v6_base/seed43/runs.json`
- `output/travelplanner_framework_compare/v6_overnight_20260418/v6_A/seed42/runs.json`
- `output/travelplanner_framework_compare/v6_overnight_20260418/v6_A/seed43/runs.json`

## 2026-04-17 — Expériences idle_cycles 8/16 et découvertes sur la stagnation différentielle

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `9/10`
- `confidence`: `high`
- `scope`: `Expériences contrôlées idle_cycles_to_stop={4,8,16} sur seed44, même benchmark validation 180 queries, backbone qwen3.5-9b`

### Outcome

Trois découvertes empiriques majeures issues des expériences idle_cycles sur le même seed (seed44) :

**Découverte 1 — Le bénéfice d'idle_cycles est non-uniforme selon la complexité de la query.**
idle=16 améliore fortement les 7j (+8pp, 11.7% → 20.0%) mais dégrade légèrement les 5j (20.0% → 16.7%) et est neutre sur les 3j. Cela confirme que la stagnation a deux causes distinctes : pour les 7j, le swarm a besoin de temps pour résoudre les dépendances inter-city via decay et réactivation ; pour les 5j, le problème est structurel (sous-objectifs perdus dans le DAG) et plus de temps ne suffit pas.

**Découverte 2 — Le seuil idle_cycles a un effet de palier, pas continu.**
Entre idle=4 et idle=8 : aucun gain net (20.6% vs 21.7% — variance seed). Entre idle=8 et idle=16 : gain net sur 7j. Il existe un seuil minimal à franchir pour que le mécanisme de decay+réactivation ait le temps d'agir. idle=8 est en dessous du seuil pour les 7j.

**Découverte 3 — `num_agents: 6` est sur-dimensionné pour le DAG TravelPlanner.**
Avec 6 agents, seulement ~1.5 travaillent simultanément (`parallel_utilization ≈ 0.22`, soit 1.49/6). `lock_contention_rate ≈ 0.75` indique que 75% des tentatives de lock sont bloquées. Cause structurelle : le DAG TravelPlanner est principalement séquentiel (search → plan → validate → finalize). Ajouter des agents n'augmente pas le parallélisme réel — cela augmente seulement la contention. Le levier est la largeur du DAG (T2), pas le nombre d'agents.

### Chiffres de référence

| Config | 3j | 5j | 7j | Global | Ticks moy | Idle% |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| v5_full idle=4 (seed42) | 33.3% | 20.0% | 11.7% | 21.7% | 19.4 | 50.0% |
| v5_idle8 idle=8 (seed44) | 33.3% | 20.0% | 8.3% | 20.6% | 24.6 | 52.8% |
| v5_idle16 idle=16 (seed44) | 31.7% | 16.7% | **20.0%** | **22.8%** | 34.9 | 42.8% |

### Reusable Patterns (1-3)

1. **Toujours stratifier par complexité avant de tuner `idle_cycles_to_stop`.** Un paramètre global unique est sous-optimal : l'optimum pour les 7j est différent de celui pour les 3j. Implémenter un `idle_cycles` dynamique basé sur la taille du DAG (nombre de nodes pending) est la direction correcte.
2. **`lock_contention_rate > 0.7` + `parallel_utilization < 0.25` est un signal de goulot DAG, pas un signal d'insuffisance d'agents.** Ne pas répondre à ce signal en augmentant `num_agents` — répondre en élargissant le DAG (décomposition plus riche, sous-objectifs persistants).
3. **Pour les systèmes stigmergiques multi-tâches, l'effet de temps supplémentaire (idle cycles) est utile uniquement si le mécanisme de decay et réactivation a des markers à réactiver.** Si le DAG est épuisé (sous-objectifs perdus), plus de temps ne fait que retarder l'échec.

### Evidence
- `output/travelplanner_framework_compare/v5_idle8/seed44/official_eval.json`
- `output/travelplanner_framework_compare/v5_idle16/seed44/official_eval.json`
- `scripts/analyze_emergence.py`
- `documentation/redisgn_v2/plan_v6_framework_general_improvement.md`

## 2026-04-17 — Review-Ready V6 Plan for General Framework Improvement Without Benchmark Drift

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `8/10`
- `confidence`: `high`
- `scope`: `Planning document for the next framework-improvement cycle after the ~21% TravelPlanner V5-full validation regime`

### Outcome
Produced a review-ready plan in `documentation/redisgn_v2/plan_v6_framework_general_improvement.md` that converts the latest emergence analysis into a methodology-safe improvement roadmap. The plan explicitly freezes the benchmark and official scorer, separates framework-general workstreams (anti-stagnation, persistent decomposition, validator-guided repair, anti-thrashing, richer emergence adaptation) from TravelPlanner-only follow-ups, and proposes a clean V6 ablation ladder over the same benchmark conditions.

### Reusable Patterns (1-3)
1. When benchmark analysis reveals multiple failure regimes, write the next improvement plan around `general framework mechanisms` first and quarantine `adapter-specific heuristics` into a separate section.
2. For article-grade benchmark work, freeze the scorer, runner semantics, validation split, and baseline config before proposing implementation tasks; review confidence depends on preserving the thermometer.
3. If the goal is scientific credibility, require every proposed improvement cycle to include its own ablation ladder from the frozen baseline rather than bundling several changes into one un-attributable preset.

### Evidence
- `documentation/redisgn_v2/plan_v6_framework_general_improvement.md`
- `output/travelplanner_framework_compare/v5_full/seed42/runs.json`
- `output/travelplanner_framework_compare/v5_full/seed43/runs.json`

## 2026-04-17 — Query-Type Emergence Failure Regimes in V5-Full Validation

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `8/10`
- `confidence`: `high`
- `scope`: `Type-stratified post-hoc analysis of the latest TravelPlanner V5-full validation seeds around the 21% pass-rate regime`

### Outcome
Stratified the latest `v5_full` validation results (`seed42`, `seed43`) by TravelPlanner query type using the dataset’s structured fields (`days`, `visiting_city_number`, `level`, `local_constraint`). The analysis shows two distinct failure regimes. `3-day / 1-city` queries mostly produce non-empty plans and fail on constraint satisfaction, especially for hard cases such as `no self-driving`, `private room`, `pets`, or `4 cuisines`. By contrast, `5-day / 2-city` and especially `7-day / 3-city` queries fail primarily through empty-plan collapse and `idle_cycles`, with much later convergence (`14` then `19` ticks on average) and weaker success rates even when the colony remains collaborative. This indicates that the next framework gains should come from type-specific control: constraint-repair hardening for single-city hard queries, and anti-stagnation / stronger decomposition for multi-city queries.

### Reusable Patterns (1-3)
1. When TravelPlanner pass rate is around the low-20% range, always separate `single-city constraint failure` from `multi-city empty-plan collapse`; the aggregate score mixes two different bottlenecks that require different fixes.
2. Use `empty_plan_rate ~= idle_cycle_rate` as a practical signature of coordination exhaustion in multi-city runs; if those ratios rise together, the issue is search/decomposition rather than final-plan validation.
3. Hard constraints can either overload the planner or provide useful scaffolding depending on query topology: in `3/1` they mostly expose weak constraint handling, while in `7/3` they can outperform easier prompts by giving the colony a more explicit search structure.

### Evidence
- `output/travelplanner_framework_compare/v5_full/seed42/runs.json`
- `output/travelplanner_framework_compare/v5_full/seed43/runs.json`
- `config/ablation/v5_full.yaml`
- `adapters/travelplanner/workspace.py`

## 2026-04-17 — V5-Full Emergence Signal Analysis on Validation Seeds 42 and 43

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `7/10`
- `confidence`: `high`
- `scope`: `Post-hoc analysis of TravelPlanner V5-full validation run emergence metrics for the latest stigmergic benchmark seeds`

### Outcome
Analyzed `summary.emergence` for all 180 queries in the latest `v5_full` validation runs (`seed42`, `seed43`) and compared the emergent metrics against `final_pass`, `stop_reason`, and seed-to-seed flips. The strongest positive signals for query success were high `pressure_entropy` and high `parallel_utilization`, while late `convergence_tick` consistently tracked worse outcomes. `action_switching_rate` behaved differently across seeds but was clearly harmful in `seed42` when it became too high, suggesting that useful emergence in this preset looks more like sustained diversified pressure with actual parallel work than like rapid role thrashing or maximal collaboration density.

### Reusable Patterns (1-3)
1. For TravelPlanner post-hoc analysis, treat `pressure_entropy` and `parallel_utilization` as the primary positive emergence indicators; they separated pass/fail far more clearly than `collaboration_density` or `colony_specialization` in the latest validation seeds.
2. Interpret a high `convergence_tick` as delayed colony stabilization rather than automatically as “more exploration”; in `v5_full`, later convergence coincided with more `idle_cycles` failures and lower final pass.
3. When two seeds disagree on a query outcome, inspect the joint profile `{convergence_tick, pressure_entropy, parallel_utilization, action_switching_rate}` before reading the difference as random variance; the flip cases often show a coherent shift in those signals.

### Evidence
- `output/travelplanner_framework_compare/v5_full/seed42/runs.json`
- `output/travelplanner_framework_compare/v5_full/seed43/runs.json`
- `output/travelplanner_framework_compare/v5_full/seed42/queries/query_063.json`
- `output/travelplanner_framework_compare/v5_full/seed43/queries/query_063.json`
- `output/travelplanner_framework_compare/v5_full/seed42/queries/query_170.json`
- `output/travelplanner_framework_compare/v5_full/seed43/queries/query_170.json`

## 2026-04-13 — Self-Refine Baseline Transport-Failure Hardening

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `8/10`
- `confidence`: `high`
- `scope`: `Implementation of T3 for the TravelPlanner solo_self_refine scientific baseline`

### Outcome
Confirmed from the historical run artifacts that `solo_self_refine` seed 43 failed on `query_idx=139` because `self_refine_draft` propagated an `openai.APIConnectionError` out of `scientific_baselines.py:_call_llm`. Hardened the baseline by adding one extra node-level retry in `TravelPlannerScientificBaselineRunner`, broadening critique fallback from parse-only failures to all provider exceptions, and adding explicit Self-Refine fallbacks so a draft failure returns an empty query payload and a reviser failure reuses the draft instead of aborting the full seed.

### Reusable Patterns (1-3)
1. In long scientific baseline batches, treat provider transport failures as query-local degradations whenever the method can still emit a scorer-compatible payload; otherwise one network blip invalidates the whole seed.
2. For Self-Refine specifically, `critic` can fall back to validator-derived repair instructions and `reviser` can fall back to the last valid draft without violating the method’s overall draft-critique-revise structure.
3. Add resilience first at the orchestration-node boundary (`_call_llm` wrapper + stage-specific fallback) rather than changing the shared LLM client when the client already handles transport retries generically.

### Evidence
- `output/travelplanner_framework_compare/20260409_233919/scientific_pack/run_registry.csv`
- `output/travelplanner_framework_compare/20260409_233919/runs/solo_self_refine/seed_43/full/logs/query_139.log`
- `adapters/travelplanner/scientific_baselines.py`
- `tests/unit/test_travelplanner_scientific_baselines.py`
- `uv run pytest tests/unit/test_travelplanner_scientific_baselines.py -q`

## 2026-04-13 — TravelPlanner V4-Only Preset and Query-Level Failure Taxonomy

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `8/10`
- `confidence`: `high`
- `scope`: `Implementation of T1/T2 from the V5 framework-improvement plan for TravelPlanner`

### Outcome
Implemented a clean `config/travelplanner_v4_only.yaml` preset that activates only the five opt-in V4 stigmergic corrections, and added query-level runtime failure taxonomy for TravelPlanner by persisting planning/validation failure reasons on markers, surfacing `failure_reason` in adapter evaluation and single-query exports, and propagating the same field into benchmark `runs.json` plus failure-reason summaries.

### Reusable Patterns (1-3)
1. Persist operational failure causes on workflow markers (`failure_reason`, `last_failure_reason`, `failure_history`) rather than only in transient tool metadata; adapter-level post-processing can then reconstruct query outcomes without touching the core orchestrator.
2. In benchmark domains, distinguish `operational failure taxonomy` from `quality scoring`: a non-empty evaluated plan can remain `ok` operationally even when `final_pass` is false, while empty-plan and control-flow breakdowns get explicit machine-readable reasons.
3. Keep pure ablation presets as dedicated config files that only flip the intended feature gates and preserve agent count, pressure parameters, and tick budget unchanged.

### Evidence
- `config/travelplanner_v4_only.yaml`
- `adapters/travelplanner/tools.py`
- `adapters/travelplanner/adapter.py`
- `scripts/run_travelplanner_query_export.py`
- `scripts/run_travelplanner_framework_benchmark.py`
- `uv run pytest tests/unit/test_config.py tests/unit/test_travelplanner_tools.py tests/unit/test_travelplanner_adapter.py tests/unit/test_travelplanner_benchmark_runner.py -q`
- `uv run pytest tests/integration/test_travelplanner.py -q`

## 2026-04-12 — V5 Plan Review for TravelPlanner Scientific Campaign

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `8/10`
- `confidence`: `high`
- `scope`: `Review of the proposed V5 framework-improvement plan before execution`

### Outcome
Reviewed `documentation/redisgn_v2/plan_v5_framework_improvement.md` against the current codebase and benchmark evidence. The plan has strong scientific hygiene (train-only tuning, explicit anti-cheating constraints, ablation intent), but should not be executed unchanged because it mixes ablation with optimization, targets some already-implemented mechanisms (`stop_reason`, LLM retry/backoff), points one prompt task at the wrong file (`llm/prompts.py` instead of TravelPlanner tool prompts), and still underweights the main structural failure mode: the current TravelPlanner adapter is effectively single-destination and therefore collapses on multi-city queries.

### Reusable Patterns (1-3)
1. Before launching a new scientific campaign plan, verify each proposed task against the current codebase so the plan does not spend effort re-adding already-present observability or retry mechanisms.
2. Keep pure ablation campaigns isolated from optimization campaigns; once heuristics, prompt tuning, or agent-count changes enter the same preset, the result no longer measures the ablated feature alone.
3. When benchmark failures are dominated by representation mismatch in the adapter, prioritize adapter redesign before local heuristics or hyperparameter tuning; otherwise the plan optimizes around a structural bottleneck.

### Evidence
- `documentation/redisgn_v2/plan_v5_framework_improvement.md`
- `core/orchestrator.py`
- `main.py`
- `llm/client.py`
- `adapters/travelplanner/tools.py`
- `adapters/travelplanner/scientific_baselines.py`

## 2026-04-11 — TravelPlanner Framework Failure Regime Analysis (Run 20260409_233919)

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `9/10`
- `confidence`: `high`
- `scope`: `Post-hoc analysis of the scientific TravelPlanner framework comparison pack for StigmergiAgentic failure modes`

### Outcome
Analyzed the final scientific pack and raw per-query artifacts for `output/travelplanner_framework_compare/20260409_233919` and isolated a two-layer failure regime for `StigmergiAgentic`: first, all benchmark gains are confined to `3-day / 1-city` queries, while `5-day / 2-city` and `7-day / 3-city` requests collapse to zero final-pass; second, the TravelPlanner adapter is structurally single-destination because search markers, fallback search payloads, and routing context all bind to one `dest` value, so multi-city requests frequently end as `No travel plan generated.` with `status=ok`, `stop_reason=all_terminal`, and `final_plan=[]`.

### Reusable Patterns (1-3)
1. When analyzing TravelPlanner benchmark runs, separate failures into `empty-plan delivery collapse` and `non-empty but invalid itinerary`; aggregate `final_pass_rate` alone hides whether the planner failed to synthesize any route at all.
2. If the adapter searches hotels, restaurants, attractions, and route legs only against a single `dest`, treat the implementation as single-destination even when prompts mention `visiting_city_number`; multi-city benchmark failure is then structural, not stochastic.
3. Export `empty_plan_after_max_attempts` as an explicit query-level failure artifact instead of a nominally successful run with `final_plan=[]`, otherwise post-hoc scientific analysis loses the true cause of failure.

### Evidence
- `output/travelplanner_framework_compare/20260409_233919/scientific_pack/paper_table_main.md`
- `output/travelplanner_framework_compare/20260409_233919/scientific_pack/pairwise_final_pass_stats.md`
- `output/travelplanner_framework_compare/20260409_233919/runs/stigmergiagentic/seed_42/full/runs.json`
- `output/travelplanner_framework_compare/20260409_233919/runs/stigmergiagentic/seed_42/full/queries/query_022.json`
- `output/travelplanner_framework_compare/20260409_233919/runs/stigmergiagentic/seed_42/full/queries/query_040.json`
- `adapters/travelplanner/adapter.py`
- `adapters/travelplanner/tools.py`

## 2026-04-09 — LangGraph Structured-Output Fallback Hardening

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `8/10`
- `confidence`: `high`
- `scope`: `TravelPlanner LangGraph supervisor resilience against malformed provider JSON during batch benchmark execution`

### Outcome
Hardened the LangGraph TravelPlanner baseline so malformed or truncated provider JSON in intermediate supervisor nodes no longer aborts the full benchmark batch by default: intermediate prompts were compacted, structured-output calls now retry after schema-parse failures, and deterministic node-specific fallbacks keep the query export alive when parsing still fails.

### Reusable Patterns (1-3)
1. For graph-based LLM benchmarks, separate transport-level retries from schema-parse retries; provider success does not imply usable structured output.
2. Keep intermediate supervisor node outputs minimal and explanation-free when the values are only used for downstream machine consumption.
3. In long batch benchmarks, add deterministic node-level fallbacks for non-final planner stages so one malformed JSON blob does not invalidate the entire campaign.

### Evidence
- `adapters/travelplanner/langgraph_supervisor.py`
- `scripts/run_travelplanner_framework_benchmark.py`
- `output/travelplanner_framework_compare/20260409_144039/langgraph_supervisor/logs/query_006.log`
- `pytest tests/unit/test_travelplanner_langgraph_supervisor.py -q`

## 2026-04-09 — Notebook Docker Build Visibility and Cache Fix

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `7/10`
- `confidence`: `high`
- `scope`: `TravelPlanner comparison notebook setup-cell reliability for Docker-based benchmark startup`

### Outcome
Fixed the principal TravelPlanner comparison notebook so Docker build and run commands stream output live in Jupyter, and repeated runs skip the `travelplanner-smoke` image rebuild when `Dockerfile`, `docker-compose.yml`, and `requirements.txt` are unchanged.

### Reusable Patterns (1-3)
1. In notebook orchestration cells, never hide long-running container build output behind `subprocess.run(capture_output=True)`; stream it live so users can distinguish progress from a hang.
2. Cache Docker build readiness on dependency-level inputs when the runtime source code is bind-mounted into the container; rebuilding the image on every notebook run only wastes wall time.
3. If a notebook depends on external CLIs such as Docker, fail early with a direct PATH/availability message instead of leaving the user at a silent command banner.

### Evidence
- `scripts/create_langgraph_travelplanner_comparison_notebook.py`
- `output/jupyter-notebook/travelplanner-framework-comparison-openrouter-qwen35-9b.ipynb`
- `/opt/miniconda3/bin/python -m py_compile scripts/create_langgraph_travelplanner_comparison_notebook.py`
- `/opt/miniconda3/bin/python - <<'PY' ... compile notebook cells ... PY`

## 2026-04-08 — LangGraph Supervisor TravelPlanner Benchmark Pivot

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `9/10`
- `confidence`: `high`
- `scope`: `Replacement of the principal SwarmAgentic comparison path with a Docker-first LangGraph supervisor baseline for TravelPlanner`

### Outcome
Implemented a reproducible three-arm TravelPlanner comparison path centered on `Solo`, `LangGraph Supervisor`, and `StigmergiAgentic`, with a new LangGraph baseline, a shared Docker-first batch benchmark runner, a regenerated comparison notebook, and thesis-methodology updates that remove SwarmAgentic from the main experimental claim path.

### Reusable Patterns (1-3)
1. When an external baseline becomes operationally non-reproducible, replace it with an in-repo controlled baseline that matches backbone, scorer, split, and output contract before continuing the comparison campaign.
2. Keep benchmark notebooks orchestration-only: route provider-facing execution through one Docker-first batch script and persist `query_XXX.json`, `runs.json`, and `official_eval.json` for resumability and post-hoc analysis.
3. When adding a new orchestration baseline in an existing benchmark domain, reuse the canonical prompt construction, search-payload shaping, normalization, and evaluator paths to avoid scorer drift between methods.

### Evidence
- `adapters/travelplanner/langgraph_supervisor.py`
- `scripts/run_travelplanner_langgraph_query_export.py`
- `scripts/run_travelplanner_framework_benchmark.py`
- `scripts/create_langgraph_travelplanner_comparison_notebook.py`
- `output/jupyter-notebook/travelplanner-framework-comparison-openrouter-qwen35-9b.ipynb`
- `consigne/revue_litterature_v2_DSR.tex`
- `pytest tests/unit/test_travelplanner_langgraph_supervisor.py -q`

## 2026-03-17 — TravelPlanner Official Eval Failure Pattern Analysis

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `8/10`
- `confidence`: `high`
- `scope`: `TravelPlanner validation benchmark result analysis for run 20260317_112916`

### Outcome
Analyzed the official TravelPlanner validation run and isolated a structural regime split: the runtime is viable on single-destination 3-day queries, degrades on 5-day 2-city queries, and collapses to zero delivery on 7-day 3-city queries, with the main bottlenecks shifting from delivery failure to closed-circle and budget/cuisine constraint failures.

### Reusable Patterns (1-3)
1. Segment TravelPlanner benchmark analysis first by `(days, visiting_city_number)` before reading aggregate pass rates; this immediately distinguishes planner-format collapse from constraint-level quality issues.
2. When `final_pass_rate` is low but `delivery_rate` is moderate, inspect `official_detailed` and a few re-evaluated representative queries to separate commonsense route failures from hard-constraint failures.
3. Treat a planner that only searches and injects inventory for `dest` as structurally single-destination, even if prompts mention multi-city travel; benchmark failures on 2-city/3-city tasks will then be expected behavior, not random variance.

### Evidence
- `output/travelplanner_official_full_eval/20260317_112916/official_eval.json`
- `output/travelplanner_official_full_eval/20260317_112916/runs.json`
- Replay of representative queries with `OfficialTravelPlannerEvaluator` (`query_013`, `query_055`, `query_072`, `query_120`, `query_128`, `query_151`)

## 2026-03-17 — Controlled GPT-4o Framework Comparison Notebook for TravelPlanner

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `8/10`
- `confidence`: `high`
- `scope`: `Notebook-driven framework comparison pipeline for StigmergiAgentic vs SwarmAgentic on OpenRouter-routed GPT-4o with the official TravelPlanner scorer`

### Outcome
Prepared a reproducible notebook workflow that compares StigmergiAgentic and SwarmAgentic under the same routed model (`openai/gpt-4o` on OpenRouter) and the same official TravelPlanner scorer, while explicitly documenting the remaining non-controlled dimension that SwarmAgentic performs a PSO optimization phase before evaluation.

### Reusable Patterns (1-3)
1. For cross-framework LLM comparisons, separate `shared evaluation controls` (provider, routed model, split, scorer) from `framework-native steps` (for example PSO training) and state the uncontrolled remainder explicitly in the notebook header.
2. When an external benchmark repo is not directly OpenRouter-compatible, patch only the provider/model adapter layer in a throwaway clone and keep framework logic unchanged.
3. Normalize third-party result files into one local `runs.json` contract before official scoring so downstream analysis, notebooks, and tables can reuse a single scorer path.

### Evidence
- `output/jupyter-notebook/travelplanner-framework-comparison-openrouter-gpt4o.ipynb`
- `scripts/prepare_swarmagentic_openrouter.py`
- `scripts/export_swarmagentic_save_jsonl.py`
- `scripts/convert_swarmagentic_travelplanner_results.py`
- `scripts/render_travelplanner_comparison_table.py`

## 2026-04-01 — SwarmAgentic OpenRouter PSO Resilience Hardening

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `8/10`
- `confidence`: `high`
- `scope`: `TravelPlanner SwarmAgentic OpenRouter adapter hardening for Qwen3.5-9B notebook runs`

### Outcome
Hardened the SwarmAgentic OpenRouter patch path and the Qwen comparison notebook so transient OpenRouter `504` and empty structured-output failures no longer abort the full PSO/evaluation workflow by default, checkpoints are written after each completed PSO iteration, and notebook reruns reuse the existing clone/venv with a lower default concurrency.

### Reusable Patterns (1-3)
1. For long-running third-party LLM optimizers, write resumable checkpoints immediately after each completed evaluation iteration instead of only at the very end of the run.
2. When a hosted provider can return transient `5xx` or null structured outputs, degrade failing tasks to zero-score placeholders and continue the campaign rather than crashing the whole batch.
3. In notebook-driven benchmark reruns, default clone/dependency steps to reuse existing artifacts and lower concurrency first on smaller routed models before increasing throughput.

### Evidence
- `scripts/prepare_swarmagentic_openrouter.py`
- `output/jupyter-notebook/travelplanner-framework-comparison-openrouter-qwen35-9b.ipynb`
- `python -m py_compile scripts/prepare_swarmagentic_openrouter.py`
- `python -m py_compile output/travelplanner_framework_compare/20260401_115306/swarmagentic/repo/travelplanner/swarm/pso.py output/travelplanner_framework_compare/20260401_115306/swarmagentic/repo/travelplanner/swarm/test.py`
- `python -m json.tool output/jupyter-notebook/travelplanner-framework-comparison-openrouter-qwen35-9b.ipynb`

## 2026-03-22 — Opt-In Stigmergic Corrections for V3 Runtime

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `9/10`
- `confidence`: `high`
- `scope`: `Implementation of V4 stigmergic corrections (local sensing, temporal decay, frequentation, emergent conflict resolution, emergence feedback) on top of Sprint 6 V3`

### Outcome
Implemented the full V4 correction plan as opt-in runtime capabilities, preserving backward compatibility while strengthening the framework's stigmergic semantics through local perception, time-aware evaporation, read-traffic reinforcement, and adaptive emergence reuse.

### Reusable Patterns (1-3)
1. When hardening a research runtime against theory-alignment critiques, add new mechanisms behind explicit config gates first, then validate that the legacy path still passes the full suite unchanged.
2. Separate `updated_at` from `last_active_at` when introducing time-based read semantics, so maintenance writes do not accidentally reset temporal dynamics.
3. If agent perception should become observable for later reinforcement, connect read tracking at the orchestrator callback boundary rather than coupling agents directly to store APIs.

### Evidence
- `consigne/V4-correction-plan.md`
- `uv run pytest tests/unit tests/integration -q` (`235 passed`)
- `uv run pytest tests/ -q` (`235 passed`)

## 2026-02-10 — Sprint 1 Environment Foundation

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `9/10`
- `confidence`: `high`
- `scope`: `Sprint 1 environment medium (store, decay, guardrails, tests)`

### Outcome
Implemented a fully testable JSON-based stigmergic medium with POSIX file locking, append-only audit trail, and guardrails enforced by environment primitives.

### Reusable Patterns (1-3)
1. Use a single environment guardrail layer to enforce token budget, retry ceiling, scope lock, and TTL instead of distributing those checks across agents.
2. Persist pheromones as inspectable JSON artifacts and pair every mutation with an append-only JSONL audit event for traceability.
3. Standardize local execution with `uv` + pinned Python minor version and run all validation through `uv run` for reproducible results.

### Evidence
- `uv run pytest tests/test_pheromone_store.py -v` (passed)
- `uv run pytest tests/test_guardrails.py -v` (passed)
- `uv run pytest tests -v -k "pheromone or guardrails"` run twice with stable green results

## 2026-02-11 — Sprint 2 Agent Layer and Deterministic Validation

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `9/10`
- `confidence`: `high`
- `scope`: `Sprint 2 agents, llm client, synthetic fixture repository, unit+integration tests`

### Outcome
Implemented all Sprint 2 units end-to-end: OpenRouter client, four isolated agents, synthetic Python 2 fixture repository, and deterministic handoff tests across the pheromone medium.

### Reusable Patterns (1-3)
1. Keep core orchestration tests deterministic with mocked LLM responses while providing an optional non-blocking live API smoke test.
2. Encode cross-agent coordination only through pheromone transitions (`pending -> in_progress -> transformed -> tested -> validated|needs_review|retry`), never direct agent calls.
3. Store a versioned synthetic legacy-code fixture in `tests/fixtures/` and explicitly exclude it from project-level pytest collection.

### Evidence
- `uv run pytest tests/ -v` (`29 passed, 1 skipped`)
- `uv run pytest tests/test_agents_integration.py -v` (all handoff scenarios passed)

## 2026-02-12 — Sprint 3 Full Loop + Blocking Gate Validation

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `9/10`
- `confidence`: `high`
- `scope`: `Sprint 3 orchestration loop, CLI, metrics, adaptive tester fallback, Docker gate execution`

### Outcome
Implemented and validated the full Sprint 3 runtime with deterministic stop conditions, per-run artifacts, adaptive quality fallback, and successful blocking gates on both synthetic and real repositories (local + Docker).

### Reusable Patterns (1-3)
1. For mixed script/library repos, treat compile-success + usage/optional-dependency import failures as `inconclusive` signals instead of hard failures, while keeping legacy stdlib misses (for example `urllib2`) as related failures.
2. Sanitize LLM outputs before file writes by stripping markdown fence wrappers (including unclosed fences) to avoid test/code corruption on retries.
3. In Docker on macOS, avoid bind-mount churn for actively rewritten repos by using a named volume for the working tree and implementing mountpoint-safe cleanup logic.

### Evidence
- Local: `uv run pytest tests/ -q` (`49 passed, 1 skipped`)
- Local synthetic gate: `metrics/output/run_20260212T170852Z_summary.json` (`success_rate=0.95`)
- Local real gate: `metrics/output/run_20260212T170936Z_summary.json` (`success_rate=0.913043`)
- Docker synthetic gate: `metrics/output/run_20260212T173610Z_summary.json` (`success_rate=0.95`)
- Docker real gate: `metrics/output/run_20260212T173704Z_summary.json` (`success_rate=0.869565`)

## 2026-02-12 — Sprint 3 Patch: Uncapped Output and USD Cost Budget

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `8/10`
- `confidence`: `high`
- `scope`: `LLM client budget model, loop/metrics propagation, CLI budget override`

### Outcome
Removed hard completion capping by default and introduced an optional USD budget control based on OpenRouter model pricing (pre-call estimate) and `usage.cost` (post-call accounting), with cost metrics exported per run.

### Reusable Patterns (1-3)
1. For thinking-heavy LLM workflows, prefer uncapped completion output (`max_tokens` omitted) and control spend with a separate budget mechanism instead of truncation.
2. Combine two budget layers: token ceiling for deterministic guardrails and cost ceiling for monetary governance.
3. Persist cumulative run cost in the same metrics stream as token usage to enable direct cost-quality analysis.

### Evidence
- `uv run pytest tests/ -q` (`60 passed, 1 skipped`)
- `uv run python main.py --repo tests/fixtures/synthetic_py2_repo --config stigmergy/config.yaml --seed 42 --max-ticks 1 --verbose` (`total_cost_usd` present, uncapped request payload)

## 2026-02-12 — Runtime Hard-Disable of `max_tokens` + Docker Image Freshness

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `8/10`
- `confidence`: `high`
- `scope`: `LLM client request payload policy and Docker execution consistency`

### Outcome
Hardened runtime behavior so the client never sends `max_tokens` to OpenRouter (even if configured), preventing accidental output truncation from local configuration drift and stale Docker images.

### Reusable Patterns (1-3)
1. For reasoning-heavy migrations, enforce uncapped completion at client layer instead of trusting config defaults.
2. Keep budget control separate from generation caps (`max_tokens_total`/`max_budget_usd` without per-call output limit).
3. Rebuild Docker image before benchmark/gate runs when runtime policy changes to avoid executing stale logic.

### Evidence
- `uv run pytest tests/test_llm_client.py -q` (`10 passed, 1 skipped`)
- `uv run pytest tests/ -q` (`60 passed, 1 skipped`)
- Docker verbose request payload confirms no `max_tokens` field in `json_data`.

## 2026-02-17 — Sprint 4 Readiness Audit (Tooling vs Benchmark Completion)

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `8/10`
- `confidence`: `high`
- `scope`: `Sprint 4 closure audit (baselines, Pareto, validation gates, thesis-readiness gaps)`

### Outcome
Validated that Sprint 4 code tooling is operational (`baselines/*`, `metrics/pareto.py`) and the full test suite is green, while identifying that thesis-grade Sprint 4 evidence remains incomplete (multi-run fairness benchmark and Pareto methodology alignment).

### Reusable Patterns (1-3)
1. Separate sprint closure into two explicit gates: `tooling complete` (code/tests) and `evidence complete` (benchmark protocol + reproducibility artifacts).
2. Run validation in layered order: target-scope tests, full suite, then static quality gates (`ruff`, `black --check`, `mypy`) to isolate regressions faster.
3. Before Pareto aggregation, verify input summaries contain all compared baselines and enough repetitions per mode; otherwise, treat results as smoke-only.

### Evidence
- `uv run pytest tests/test_loop.py tests/test_metrics.py tests/test_main.py tests/test_pareto.py -v --tb=short` (`17 passed`)
- `uv run pytest tests/ -v --tb=short` (`62 passed, 1 skipped`)
- `uv run pytest tests/ --cov --cov-report=term-missing --no-cov-on-fail` (`TOTAL 86%`)
- `uv run ruff check . --exclude tests/fixtures` (fails: `E402` in `baselines/*`, `F401` in `main.py`)
- `uv run mypy agents/ environment/ stigmergy/ --ignore-missing-imports` (type issues in `environment/pheromone_store.py`, `agents/scout.py`)
- `uv run python metrics/pareto.py --input-dir metrics/output --output /tmp/stigmergiagentic_pareto_check.png --export-json /tmp/stigmergiagentic_pareto_check.json` (`points=13`, `baselines=1`)

## 2026-02-17 — Sprint 4 Closure Implementation (Pareto V2 + 5x3 Benchmark)

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `9/10`
- `confidence`: `high`
- `scope`: `Sprint 4 execution closure (static quality, baseline tests, Pareto CLI V2, bounded 5x3 benchmark, docs sync)`

### Outcome
Completed Sprint 4 closure work end-to-end: static gates green (`ruff`, `black --check`, `mypy`), expanded baseline/Pareto tests, upgraded Pareto tooling (per-run mode + baseline coverage check + CI95 export), and executed a 5x3 bounded benchmark on `docopt/docopt@0.6.2` with refreshed mobile/documentation outputs.

### Reusable Patterns (1-3)
1. Add explicit baseline coverage guards (`--require-baselines`) to analysis tooling so incomplete experiment folders fail fast instead of producing misleading charts.
2. Keep both visualization layers in Pareto workflows: per-run scatter for transparency and aggregate CI95 overlays for comparability.
3. When runtime/cost constraints prevent full unconstrained campaigns, run a bounded protocol with identical caps across configurations and document bounds directly in the results artifact.

### Evidence
- `uv run ruff check . --exclude tests/fixtures` (`All checks passed`)
- `uv run black --check . --exclude '/tests/fixtures/'` (`4985 files would be left unchanged`)
- `uv run mypy agents/ environment/ stigmergy/ --ignore-missing-imports` (`Success: no issues found`)
- `uv run pytest tests/ -v --tb=short` (`72 passed, 1 skipped`)
- `make docker-test` (`72 passed, 1 skipped`)
- Benchmark (5 runs each):
  - `uv run python baselines/single_agent.py ... --max-ticks 1 --max-tokens 5000 --runs 5`
  - `uv run python baselines/sequential.py ... --max-ticks 1 --max-tokens 5000 --runs 5`
  - `for i in 1..5: uv run python main.py ... --max-ticks 1 --max-tokens 5000`
- `uv run python metrics/pareto.py --input-dir metrics/output/sprint4_20260217_benchmark --plot-mode per-run --require-baselines stigmergic,single_agent,sequential --export-json ...` (`points=15`, `baselines=3`)

## 2026-02-17 — Benchmark Stability Hardening (Timeout + Sequential Stage Cap)

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `8/10`
- `confidence`: `medium`
- `scope`: `Runtime stability during repeated baseline benchmarking`

### Outcome
Added explicit OpenRouter request timeout wiring in `LLMClient` and introduced a per-stage action cap in the sequential baseline loop to reduce non-terminating benchmark runs.

### Reusable Patterns (1-3)
1. For repeated LLM benchmark campaigns, set explicit provider request timeouts instead of relying on SDK defaults.
2. Bound nested `while agent.run()` stage loops with configurable action caps to prevent runaway per-tick execution.
3. Validate stability guardrails with focused unit tests before resuming long benchmark batches.

### Evidence
- `uv run pytest tests/test_llm_client.py tests/test_baselines_sequential.py -v --tb=short` (`14 passed, 1 skipped`)
- `uv run ruff check baselines/sequential.py stigmergy/llm_client.py tests/test_baselines_sequential.py tests/test_llm_client.py` (`All checks passed`)

## 2026-02-17 — Unbounded 5x3 Completion (Parallel Isolated Runs + Pareto Final)

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `9/10`
- `confidence`: `high`
- `scope`: `Finalize Sprint 4 evidence batch and close end-of-sprint gates`

### Outcome
Completed the full unbounded benchmark set (`5 x 3` runs) by launching missing runs in parallel from isolated temporary workspaces, then generated final Pareto artifacts and passed the sprint end gate.

### Reusable Patterns (1-3)
1. For concurrent campaign runs, isolate each process in its own copied workspace to avoid collisions on `target_repo`, `.target_repo_clone_tmp`, and `pheromones`.
2. Count completion from `run_*_summary.json` (not manifests) to avoid false-positive progress when runs start but have not finished.
3. After benchmark completion, regenerate Pareto with `--require-baselines` and immediately run `./scripts/sprint_end.sh` to lock both evidence and code-quality gates.

### Evidence
- Final counts in `metrics/output/sprint4_20260217_full`: `{'single_agent': 5, 'sequential': 5, 'stigmergic': 5}`
- `uv run python metrics/pareto.py --input-dir metrics/output/sprint4_20260217_full --plot-mode per-run --require-baselines stigmergic,single_agent,sequential --export-json metrics/output/sprint4_20260217_full/pareto_summary.json`
- `uv run pytest tests/ -v` (`74 passed, 1 skipped`)
- `./scripts/sprint_end.sh` (pass: tests, coverage, lint, format, mypy)

## 2026-02-19 — Sprint 5 Prep: Z.ai `glm-5` Integration

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `8/10`
- `confidence`: `high`
- `scope`: `Provider-aware LLM wiring, config defaults update, provider smoke validation`

### Outcome
Introduced provider-aware LLM routing (`openrouter` and `zai`) with provider-specific API key/base URL resolution, switched Sprint 5 default model to `glm-5` on Z.ai coding endpoint, and validated connectivity with a live smoke call.

### Reusable Patterns (1-3)
1. Centralize provider routing in one client (`provider -> env var + base_url + pricing capability`) instead of scattering provider checks across agents.
2. Keep pricing pre-check optional and provider-gated so token/cost guardrails remain stable even when a provider lacks pricing endpoint integration.
3. Validate provider switches with one deterministic smoke prompt (`Reply with exactly: pong`) before launching full migration loops.

### Evidence
- `uv run pytest tests/test_llm_client.py -q` (`13 passed, 1 skipped`)
- `uv run pytest tests/test_main.py tests/test_loop.py -q` (`12 passed`)
- `uv run python - <<'PY' ... provider='zai', model='glm-5' ...` (`ok=1`, content `pong`)

## 2026-02-19 — Anti-429 Hardening for Z.ai Campaign Runs

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `8/10`
- `confidence`: `high`
- `scope`: `Runtime retry pacing to mitigate provider rate limiting during repeated runs`

### Outcome
Added built-in anti-429 controls to the shared LLM client (inter-call pacing, 429-specific minimum backoff, and retry jitter), then enabled those controls in default config for Sprint 5 Z.ai usage.

### Reusable Patterns (1-3)
1. Combine request pacing (`min_call_interval_seconds`) with retry backoff to reduce bursty provider traffic during agent loops.
2. Treat HTTP 429 separately from generic retryable errors by applying a stronger floor and honoring `Retry-After` when available.
3. Keep anti-rate-limit behavior in the shared LLM client so all orchestration modes inherit it without per-agent patches.

### Evidence
- `uv run pytest tests/test_llm_client.py -q` (`15 passed, 1 skipped`)
- `uv run ruff check stigmergy/llm_client.py tests/test_llm_client.py tests/conftest.py` (`All checks passed`)

## 2026-02-19 — Default Runtime Switch Back to OpenRouter

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `7/10`
- `confidence`: `high`
- `scope`: `Provider default reconfiguration for faster repeated runs`

### Outcome
Switched project defaults back to OpenRouter (`qwen/qwen3-235b-a22b-2507`) and disabled inter-call pacing by default to reduce wall-clock time for benchmark batches, while keeping anti-429 controls available.

### Reusable Patterns (1-3)
1. Keep provider-specific resilience controls configurable so defaults can be tuned quickly per provider behavior.
2. For throughput-focused benchmark phases, disable global pacing and rely on retry/backoff floors only.
3. Validate provider switches immediately with a one-shot smoke call and token accounting check.

### Evidence
- `uv run python - <<'PY' ... provider='openrouter' ...` (`ok=1`, `tokens=24`, `content=pong`)

## 2026-02-19 — GPT-5-nano Trial Batch (5 Stigmergic Runs, No Max Tokens)

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `8/10`
- `confidence`: `high`
- `scope`: `Model A/B trial before Sprint 4 comparison lock`

### Outcome
Executed 5 complete stigmergic runs on `docopt/docopt@0.6.2` using `openai/gpt-5-nano` via OpenRouter with no `--max-tokens`, and generated a curated 5-run Pareto artifact set for clean comparison.

### Reusable Patterns (1-3)
1. When a long sequential batch is interrupted, isolate and re-run the missing runs in parallel workspaces to finish quickly without corrupting outputs.
2. Keep a curated output subset when accidental extra runs are produced, so analysis stays exactly on the requested sample size.
3. Verify model/repo/ref consistency from manifest files for each run before comparing metrics.

### Evidence
- `metrics/output/pre_sprint4_gpt5nano_20260219_stigmergic_5runs_curated` (5 manifests, 5 summaries, 5 ticks CSV)
- `uv run python metrics/pareto.py --input-dir metrics/output/pre_sprint4_gpt5nano_20260219_stigmergic_5runs_curated --output .../pareto.png --plot-mode per-run --export-json .../pareto_summary.json` (`points=5`, `baselines=1`)

## 2026-02-26 — V2 Sprint 1 Core Environment Reset (SQLite WAL)

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `9/10`
- `confidence`: `high`
- `scope`: `Hard reset V0.1 runtime and implement V2 Sprint 1 generic environment core`

### Outcome
Delivered a clean V2 baseline with a generic `Marker` contract, transactional SQLite/WAL `MarkerStore`, append-only JSONL audit, guardrails, strict config validation, and a complete 31-test Sprint 1 unit gate.

### Reusable Patterns (1-3)
1. For architecture resets, remove legacy runtime paths early in a dedicated branch to prevent hybrid coupling and simplify acceptance gates.
2. Use SQLite `WAL` + `BEGIN IMMEDIATE` for coordination state to keep write integrity while preserving concurrent read scalability.
3. Treat audit logging as a first-class write-path invariant (`before/after` per mutation) rather than a post-processing export.

### Evidence
- `uv run pytest tests/unit -v` (`31 passed`)
- `uv run pytest tests/unit/test_marker_store.py -v` (`12 passed`)
- `uv run pytest tests/unit/test_guardrails.py -v` (`6 passed`)

## 2026-02-26 — V2 Sprint Documentation Rule (`documentation/redisgn_v2`)

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `8/10`
- `confidence`: `high`
- `scope`: `Process governance for per-sprint artifact-state documentation`

### Outcome
Established a mandatory sprint-close documentation protocol in `documentation/redisgn_v2`, with a reusable template and a first concrete artifact status document for Sprint 1.

### Reusable Patterns (1-3)
1. Introduce a dedicated sprint-state folder to separate architecture evolution notes from generic construction logs.
2. Enforce one fixed file naming convention (`sprint_XX_artifact.md`) to make cross-sprint retrieval deterministic.
3. Make the protocol executable by embedding it directly in agent instruction files (`AGENTS.md`, `CLAUDE.md`).

### Evidence
- `documentation/redisgn_v2/README.md`
- `documentation/redisgn_v2/sprint_01_artifact.md`
- Rule references added in `AGENTS.md` and `CLAUDE.md`

## 2026-02-26 — Sprint 2 V2 Generic Runtime Closure

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `9/10`
- `confidence`: `high`
- `scope`: `Sprint 2 V2 runtime (agent, pressure, orchestrator, tool contracts, llm client port, unit validation)`

### Outcome
Delivered a generic, testable multi-agent runtime on top of the Sprint 1 marker environment, including asynchronous orchestration with deterministic sync entrypoints, lock-safe conflict resolution, and provider-aware LLM client integration.

### Reusable Patterns (1-3)
1. Keep async orchestration core with a synchronous wrapper for deterministic unit tests and low-friction local validation.
2. Enforce marker-state transitions and budget checks in the environment layer so tools stay domain-focused and side effects remain auditable.
3. Test orchestration deterministically with a mock adapter exposing simple staged tools (`increment/check/finalize`) to validate conflicts, stop conditions, and parallel tick behavior.

### Evidence
- `uv run pytest tests/unit/test_pressure.py tests/unit/test_agent.py tests/unit/test_orchestrator.py tests/unit/test_llm_client.py -q` (`30 passed`)
- `uv run pytest tests/unit -v` (`61 passed`)

## 2026-02-26 — Sprint 3 V2 Infrastructure Tools + Assistant Mode

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `9/10`
- `confidence`: `high`
- `scope`: `Sprint 3 V2 tools layer, assistant adapter, CLI runtime, unit+integration validation`

### Outcome
Implemented Sprint 3 end-to-end by adding reusable infrastructure tools, a sandboxed assistant adapter, and a CLI execution path that runs the stigmergic orchestrator without domain-specific adapters.

### Reusable Patterns (1-3)
1. Keep infrastructure tools under the same `Tool` contract as domain tools so pressure-driven action selection remains uniform across adapters.
2. Enforce workspace safety at the workspace layer (path resolution + size constraints + allowlists), then let tools focus on action semantics.
3. Combine deterministic integration runs (`num_agents=1`, `temperature=0`) with mock LLM outputs to validate full tick-loop behavior without external API coupling.

### Evidence
- `uv run pytest tests/unit -q` (`81 passed`)
- `uv run pytest tests/integration/test_assistant_run.py -q` (`4 passed`)
- `uv run pytest tests/unit tests/integration -q` (`85 passed`)
- `uv run python main.py --adapter assistant --objective "Create a short checklist" --max-ticks 12 --agents 1 --seed 7` (`stop_reason=all_terminal`)

## 2026-03-04 — Assistant Action Eligibility Rework (Execution-First)

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `9/10`
- `confidence`: `high`
- `scope`: `assistant adapter marker seeding, tool eligibility policy, response synthesis, Sprint 3 tests`

### Outcome
Reworked assistant marker/tool eligibility so explicit `eligible_actions` remains optional, while default behavior now enables action selection from marker context (instead of hard-locking to `decompose/think`), and expanded CLI response synthesis to include concrete tool outputs (`last_read`, `last_bash`, `last_write`, `last_search`) alongside reasoning.

### Reusable Patterns (1-3)
1. Treat marker action filters as optional override contracts; when omitted, infer tool eligibility from marker payload prerequisites (`path`, `command`, `query`, `write`) instead of forcing one hardcoded action.
2. Keep `decompose` root-only by default using marker-local context (`decomposed` + `parent_id`) to avoid recursive decomposition loops without adding central orchestration branches.
3. Build assistant final responses from execution artifacts first (file/bash/write/search outputs), then include reasoning text as supporting context.

### Evidence
- `uv run pytest tests/unit -q` (`83 passed`)
- `uv run pytest tests/integration/test_assistant_run.py -q` (`4 passed`)
- `uv run pytest tests/unit/test_assistant_adapter.py tests/unit/test_file_tools.py tests/unit/test_pressure.py tests/integration/test_assistant_run.py -q` (`26 passed`)

## 2026-03-04 — Think-Then-Act Gate + `.env`-Aware CLI

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `9/10`
- `confidence`: `high`
- `scope`: `think/decompose runtime gating, assistant config provider defaults, integration/runtime reliability`

### Outcome
Implemented a think-then-act execution gate: `think` no longer advances generic active subtasks, active subtasks must be progressed by concrete tools, decomposed root markers retain a controlled completion path, and CLI now auto-loads `.env` so API keys used in notebooks are also available in direct `main.py` runs.

### Reusable Patterns (1-3)
1. Prevent plan-only loops by blocking planner actions on active subtasks and requiring concrete tool outputs for `active -> completed` progression.
2. Handle coordinator/root markers as a distinct lifecycle class (decomposed-root exception) to avoid deadlocking orchestration after decomposition.
3. Call `load_dotenv()` at CLI entrypoints to align notebook and shell execution environments for provider credentials.

### Evidence
- `uv run pytest tests/unit/test_think_tool.py tests/integration/test_assistant_run.py -q` (`7 passed`)
- `uv run pytest tests/unit tests/integration/test_assistant_run.py -q` (`92 passed`)
- `uv run pytest tests/unit/test_main_response.py tests/integration/test_assistant_run.py -q` (`6 passed`)

## 2026-03-04 — Emergent Decomposition + LLM-Only Tool Hinting

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `9/10`
- `confidence`: `high`
- `scope`: `assistant decomposition policy, think prompt contract, configurable intensity dynamics, test/integration stabilization`

### Outcome
Removed structural hardcoding that forced planning shape and fallback hints: decomposition no longer enforces a fixed default subtask count, think no longer auto-infers tool hints from heuristics, prompts now expose optional fields dynamically based on declared available tools, and all intensity decrements/floors are configurable from marker settings.

### Reusable Patterns (1-3)
1. Keep `subtask_count` as an optional operator hint, not a required runtime invariant, so decomposition shape can emerge from objective complexity.
2. Prefer strict LLM JSON contracts over local heuristic hint injection when execution eligibility should reflect model intent rather than adapter guesswork.
3. Move marker intensity constants to config keys to tune planning/execution pressure without code edits.

### Evidence
- `uv run pytest tests/unit tests/integration/test_assistant_run.py -v` (`94 passed`)

## 2026-03-04 — Sprint 4 V3 Runtime Overhaul (Structured Async + DAG)

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `9/10`
- `confidence`: `high`
- `scope`: `V3 runtime hardening (typed LLM outputs, async execution, dependency gating, reinforcement, session isolation)`

### Outcome
Implemented Sprint 4 V3 end-to-end with schema-validated async LLM calls, dependency-aware scheduling, reinforcement propagation, session-isolated storage, and expanded test coverage validated at 128 passing tests.

### Reusable Patterns (1-3)
1. Keep sync and async LLM paths side-by-side (`call` + `acall`) to preserve backward compatibility while enabling typed structured-output enforcement in new runtime flows.
2. Treat marker dependencies as first-class runtime constraints (`depends_on` + unblocked filtering) instead of soft conventions in prompts.
3. Pair per-run `session_id` with isolated persistence path (`pheromones/<session_id>/markers.db`) to avoid cross-run contamination during concurrent experiments.

### Evidence
- `uv run pytest tests/unit -q` (`127 passed`)
- `uv run pytest tests/integration/test_assistant_run.py -q` (`4 passed`)
- `uv run pytest tests/unit tests/integration -q` (`131 passed`)
- `uv run pytest tests/unit/test_llm_client.py tests/unit/test_dependency.py tests/unit/test_reinforcement.py -q` (structured async + DAG + reinforcement focus)

## 2026-03-04 — Sprint 5 V3 Memory + Emergence + Lesson Runtime

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `9/10`
- `confidence`: `high`
- `scope`: `agent episodic memory, emergence metrics, lesson marker deposition, heuristic-aware pressure, CLI dashboard`

### Outcome
Implemented Sprint 5 V3 end-to-end with bounded episodic memory in agents, run-level emergence telemetry from tick rows and audit traces, automatic lesson marker deposition on high-quality transitions, heuristic-aware ACO pressure extension, and CLI emergence dashboard integration.

### Reusable Patterns (1-3)
1. Add cognitive extensions at decision boundaries (`perceive_and_decide`/`execute`) by passing contextual payload through decision contracts instead of mutating persistent marker schema.
2. Compute collaboration metrics from append-only audit logs to avoid storage schema churn while still quantifying cross-agent interaction density.
3. Promote high-quality transitions into durable `lesson` markers so reusable coordination knowledge can outlive local agent memory decay.

### Evidence
- `uv run pytest tests/ -v` (`168 passed`)
- `uv run python main.py --adapter assistant --objective "Summarize workspace status" --max-ticks 10 --agents 2` (emergence dashboard shown; JSON includes `emergence`)
- `sqlite3 pheromones/<session_id>/markers.db "SELECT id, marker_type, state, target FROM markers WHERE marker_type='lesson';"` (lesson marker present)

## 2026-03-05 — Sprint 6 V3 TravelPlanner Adapter (DSR Iteration 1)

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `9/10`
- `confidence`: `high`
- `scope`: `TravelPlanner domain adapter implementation + legacy V0.1 cleanup + paper-facing metrics wiring`

### Outcome
Implemented the first application-domain adapter on V3 (`travelplanner`) with CSV/HF workspace integration, deterministic domain search tools, schema-validated itinerary planning, programmatic commonsense/hard validation, CLI adapter dispatch, and end-to-end tests; removed obsolete V0.1 runtime surfaces and legacy tests.

### Reusable Patterns (1-3)
1. Keep domain adapters thin by placing data IO in `workspace`, action semantics in `tools`, and benchmark scoring in `evaluator`, while preserving core runtime contracts unchanged.
2. For benchmark-grade reproducibility, use LLM only for plan generation and keep constraint validation fully programmatic with explicit micro/macro/final metrics.
3. Introduce a domain setup script that verifies both data assets (CSV integrity) and query source availability before runtime execution.

### Evidence
- `uv run pytest tests/unit tests/integration -q` (`204 passed`)
- `uv run pytest tests/ -q` (`209 passed`)
- `uv run python scripts/setup_travelplanner.py --output-dir /tmp/travelplanner_db_check --force` (setup + integrity checks passed)

## 2026-03-06 — OC1-OC5 Alignment Audit (Review vs Plan vs Runtime)

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `8/10`
- `confidence`: `high`
- `scope`: `Thesis-alignment audit of V3 plan against literature review and current runtime evidence`

### Outcome
Produced a repo-backed audit that separates theoretical intent, V3 plan promises, and currently proven V3 capabilities, concluding that the framework is strong on runtime architecture (OC1-OC2) but still only partially validated at thesis scale (OC3-OC5, DSR/FEDS, governance).

### Reusable Patterns (1-3)
1. Audit thesis artifacts against three explicit layers: literature target, implementation plan, and current repo evidence.
2. Treat configured-but-unwired metrics or controls as intentions, not capabilities, until runtime outputs or tests prove them.
3. Separate `runtime complete` from `research validated`; benchmarks, case studies, and expert evaluation must be tracked as independent proof layers.

### Evidence
- `pytest -q` (`209 passed`)
- `documentation/v3_oc1_oc5_alignment_audit.md`
- V3 evidence sources reviewed: Sprint 4-6 ADRs, Sprint 6 artifact note, `core/*`, `adapters/*`, `tests/*`

## 2026-03-06 — Colab Qwen3-14B-AWQ Benchmark Notebook Rebuild

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `7/10`
- `confidence`: `medium`
- `scope`: `Google Colab notebook rebuild for local Qwen3-14B-AWQ benchmarking on Tesla T4`

### Outcome
Created a new Colab-oriented benchmark notebook that replaces brittle vLLM startup assumptions with a cleaner install-restart flow, conservative T4 memory settings, file-backed server logs, and the same latency/throughput plus structured-JSON checks needed for local model viability testing.

### Reusable Patterns (1-3)
1. For Colab notebooks that upgrade `torch` or `vllm`, separate the dependency install into its own restart-triggering section and resume runtime logic only after reconnect.
2. On constrained T4 setups, prefer auto-detected AWQ handling with conservative vLLM settings (`max_model_len`, `max_num_seqs`, `gpu_memory_utilization`) before adding backend or quantization overrides.
3. Persist vLLM startup logs to a file and surface the full tail on health-check timeout so notebook failures expose the real engine cause instead of a generic wrapper exception.

### Evidence
- `notebooks/benchmark_colab_qwen3_14b_t4_clean.ipynb`
- Static validation: notebook JSON parsed successfully and every code cell passed `ast.parse`
- Manual comparison against the failing notebook identified removed risk points: forced `FLASHINFER`, forced `awq_marlin`, truncated startup logs

## 2026-03-06 — TravelPlanner Colab Benchmark Notebook Rebuild

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `8/10`
- `confidence`: `medium`
- `scope`: `Rewrite the Sprint 6 TravelPlanner benchmark notebook for Colab T4 with local vLLM serving and resumable official evaluation`

### Outcome
Rebuilt the TravelPlanner benchmark notebook around the stable Colab T4 procedure: restart-aware environment install, pinned local vLLM stack, temporary local LLM override config, per-query checkpointing, and official TravelPlanner evaluation using the repository runtime instead of a hosted LLM backend.

### Reusable Patterns (1-3)
1. For repo-level Colab benchmarks, separate the notebook into `environment install`, `local model serving`, and `benchmark execution` phases so a runtime restart does not invalidate the run protocol.
2. When a benchmark loop depends on expensive local inference, save a checkpoint after every item instead of every N items to survive Colab disconnects and preemption.
3. For local OpenAI-compatible servers in a repo that expects hosted providers, inject a temporary config override plus a dummy provider API key rather than patching runtime code just for notebook execution.

### Evidence
- `travelplanner-sprint6-benchmark.ipynb`
- Static validation: notebook JSON parsed successfully and every code cell passed `ast.parse`
- Notebook now uses `main.py --query-idx ... --config <local override>` with official TravelPlanner scorer and per-query checkpoint persistence

## 2026-03-06 — Root-Level Colab Qwen3-14B-AWQ Feasibility Notebook

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `7/10`
- `confidence`: `medium`
- `scope`: `Root-level Colab notebook for thesis-facing local feasibility and benchmark credibility assessment`

### Outcome
Created a root-level notebook artifact that answers the thesis-facing question directly by separating minimal viability from repeated stability, exporting environment provenance and failure events, and producing a `GO` / `CONDITIONAL GO` / `NO-GO` verdict for using `Qwen/Qwen3-14B-AWQ` locally on Google Colab Free T4 without OpenRouter.

### Reusable Patterns (1-3)
1. Separate `runs once` from `benchmark credible` by combining a minimal viability suite with a repeated stability campaign on representative prompts.
2. Export benchmark provenance (`packages`, GPU, env overrides, launch command) and failure events together so Colab-session conclusions stay auditable and reproducible.
3. Translate benchmark outcomes into three thesis-use levels (`smoke`, `exploratory`, `primary`) instead of a binary feasibility flag.

### Evidence
- `benchmark_colab_qwen3_14b_t4_clean.ipynb`
- Static validation: notebook JSON parsed successfully and every code cell passed `ast.parse`
- The notebook writes a machine-readable summary to `qwen3_14b_awq_benchmark_results.json` with verdict, rationale, provenance, and repeated-run records

## 2026-03-12 — RunPod Ops Skill for Repo-Level Benchmarking

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `8/10`
- `confidence`: `high`
- `scope`: `Create a repo-local RunPod skill for Pod operations, storage handling, and benchmark execution`

### Outcome
Created a local `runpod-ops` skill that combines official RunPod product constraints with the currently installed `runpodctl` command shape, plus a repo-specific workflow for running `vLLM` and TravelPlanner evaluation on RunPod Pods.

### Reusable Patterns (1-3)
1. For external CLI skills, anchor command syntax to the installed CLI `--help` output when official docs still contain deprecated verbs or outdated flows.
2. Keep infrastructure skills concise in `SKILL.md` and move command maps plus repo runbooks into `references/` files.
3. Separate durable Pod storage and SSH workflows from ad-hoc transfer utilities so benchmark instructions stay reproducible.

### Evidence
- `runpodctl version` -> `2.1.6-400ac40`
- `runpodctl user` exited successfully with local config-based auth
- `.codex/skills/runpod-ops/SKILL.md`
- `.codex/skills/runpod-ops/references/runpodctl.md`
- `.codex/skills/runpod-ops/references/stigmergiagentic-runpod.md`

## 2026-03-12 — Autoresearch Integration Strategy for Research Workflows

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `8/10`
- `confidence`: `medium`
- `scope`: `Integration design for adapting karpathy/autoresearch patterns into the V3 stigmergic runtime`

### Outcome
Mapped `karpathy/autoresearch` to the current V3 runtime as an integration pattern instead of a direct code import. The reusable core is a fixed evaluator plus one mutable artifact plus a keep/discard loop, while thesis-style literature research additionally requires scholarly retrieval, citation grounding, and synthesis scoring.

### Reusable Patterns (1-3)
1. Reuse `autoresearch` as a control-loop pattern, not as a domain implementation: preserve immutable evaluation, mutable artifact iteration, and experiment logging, but swap the metric to a grounded research score.
2. Add research support as a dedicated adapter vertical slice rather than overloading the generic assistant adapter, so tool surface, state machine, and evaluator remain explicit and testable.
3. Feed evaluator-produced `quality_score` back into V3 reinforcement so high-value source chains and synthesis strategies are amplified across ticks.

### Evidence
- External sources reviewed: `https://github.com/karpathy/autoresearch`, `https://raw.githubusercontent.com/karpathy/autoresearch/master/README.md`, `https://raw.githubusercontent.com/karpathy/autoresearch/master/program.md`
- Local integration anchors reviewed: `main.py`, `adapters/base.py`, `adapters/assistant/adapter.py`, `core/environment.py`, `tools/decompose.py`, `tools/web_search.py`, `adapters/travelplanner/evaluator.py`

## 2026-03-13 — Repo-Local Objective Autoresearch Skill

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `8/10`
- `confidence`: `high`
- `scope`: `Create a hybrid repo-local skill for bounded autoresearch-style framework improvement and sourced research loops`

### Outcome
Implemented a repo-local `objective-autoresearch` skill that encodes a goal-locked iterative loop with explicit mode selection (`framework-improvement` vs `objective-research`), fixed evaluator discipline, keep/discard decisions, and bounded failure-stop guardrails.

### Reusable Patterns (1-3)
1. For hybrid strategy skills, keep the top-level `SKILL.md` short and decision-oriented, then push mode-specific procedures into separate `references/` files.
2. When the user wants autonomy without drift, encode autonomy as a fixed loop contract plus immutable evaluator rules and explicit failure-stop thresholds.
3. For repo-local autoresearch workflows, select mode from the final deliverable rather than from intermediate actions such as browsing, brainstorming, or patching.

### Evidence
- `.codex/skills/objective-autoresearch/SKILL.md`
- `.codex/skills/objective-autoresearch/references/framework-mode.md`
- `.codex/skills/objective-autoresearch/references/research-mode.md`
- `.codex/skills/objective-autoresearch/references/evaluator-contracts.md`
- `python /Users/lotfi/.codex/skills/.system/skill-creator/scripts/quick_validate.py .codex/skills/objective-autoresearch` -> `Skill is valid!`

## 2026-03-13 — Simplified Home AGENTS Governance

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `7/10`
- `confidence`: `high`
- `scope`: `Remove the heavy knowledge-governance block from the home-level AGENTS file and keep only lightweight skill-locality guidance`

### Outcome
Simplified `/Users/lotfi/.codex/AGENTS.md` by removing the dedicated `Knowledge Governance` section and replacing it with a short repo-local skill preference under `Skill Hygiene`, preserving the practical rules without the heavier policy framing.

### Reusable Patterns (1-3)
1. When an instruction file becomes noisy, prefer deleting rigid policy sections and preserving only the minimum operational rule that still guides behavior.
2. Keep home-level AGENTS files broad and lightweight; push repository-specific process rules down into repo-local files.
3. For skill systems, a simple "prefer repo-local for repo-specific workflows" rule is often clearer than a full governance section.

### Evidence
- `/Users/lotfi/.codex/AGENTS.md`
- Removed section: `## Knowledge Governance`
- Added guidance under `## Skill Hygiene` for repo-local skills

## 2026-03-13 — RunPod TravelPlanner Repo-Local Workflow

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `8/10`
- `confidence`: `high`
- `scope`: `Repo-local RunPod workflow for provisioning a Pod, bootstrapping the repo, running the TravelPlanner smoke flow, and retrieving artifacts`

### Outcome
Implemented a repo-local RunPod workflow composed of one operational guide plus four shell scripts that cover local pod creation, on-pod repository bootstrap, TravelPlanner smoke execution, and artifact packaging around the current `runpodctl 2.1.6` command shape.

### Reusable Patterns (1-3)
1. For remote pod runs, treat a pushed Git ref as the only source of truth and bootstrap empty machines from a raw GitHub script before cloning the full repository.
2. Split remote execution into four phases with separate scripts: local pod creation, on-pod bootstrap, in-repo smoke run, and artifact packaging/transfer.
3. Prefer environment-variable secrets and `runpodctl send/receive` artifact handoff over syncing an entire local workspace to the pod.

### Evidence
- `documentation/runpod_travelplanner_workflow.md`
- `scripts/runpod/create_travelplanner_pod.sh`
- `scripts/runpod/bootstrap_travelplanner_repo.sh`
- `scripts/runpod/run_travelplanner_smoke.sh`
- `scripts/runpod/package_artifacts.sh`
- `bash -n scripts/runpod/create_travelplanner_pod.sh scripts/runpod/bootstrap_travelplanner_repo.sh scripts/runpod/run_travelplanner_smoke.sh scripts/runpod/package_artifacts.sh`
- `uv run pytest tests/integration/test_travelplanner.py -q` (`5 passed`)
- `uv run python scripts/setup_travelplanner.py --output-dir /tmp/travelplanner_runpod_impl_check --force`
- `REPO_DIR=/Users/lotfi/Documents/EMLV/Memoire/StigmergiAgentic ARCHIVE_PATH=/tmp/travelplanner_runpod_artifacts_test.tgz bash scripts/runpod/package_artifacts.sh`

## 2026-03-13 — OpenRouter 9B Baseline Reset and Repo Cleanup

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `8/10`
- `confidence`: `high`
- `scope`: `Reset the checked-in runtime baseline to OpenRouter qwen/qwen3.5-9b, add verifiable CLI metadata, replace the pod-specific smoke entrypoint with a local TravelPlanner smoke script, and remove workflow detours from the main repo path`

### Outcome
Reset the default runtime path to `OpenRouter -> qwen/qwen3.5-9b`, aligned test fixtures and LLM fallback defaults, exposed `llm_provider` and `llm_model` in the CLI JSON summary, added a local `scripts/run_travelplanner_smoke.sh` verifier, and removed benchmark notebooks, repo-local infra skills, RunPod workflow artifacts, and leftover session scratch files from the standard repository surface. Final hardening for the live TravelPlanner path included compacting the itinerary prompt, injecting restaurant candidates from workspace data instead of raw `reference_information`, restoring bounded `max_response_tokens`, disabling OpenRouter reasoning for strict JSON calls, and coercing nullable LLM string fields so the end-to-end smoke completed successfully.

### Reusable Patterns (1-3)
1. Keep exactly one checked-in hosted LLM baseline across config, runtime fallbacks, and test fixtures; move alternate backends and experiments into transient scripts or notebooks.
2. For strict JSON tasks on OpenRouter reasoning models, pass `reasoning` through `extra_body`, set `effort: "none"` for the runtime path, cap `max_response_tokens`, and tolerate nullable string fields at the schema edge.
3. Keep benchmark prompts compact and domain-scoped: prefer workspace-backed slices such as restaurant/flight/hotel records over raw dataset blobs like `reference_information`.

### Evidence
- `config/default.yaml`
- `llm/client.py`
- `main.py`
- `scripts/run_travelplanner_smoke.sh`
- `tests/conftest.py`
- `tests/unit/test_llm_client.py`
- `tests/unit/test_main_summary.py`
- `tests/unit/test_schemas.py`
- `uv run pytest tests/unit/test_llm_client.py tests/unit/test_main_summary.py tests/unit/test_travelplanner_tools.py tests/unit/test_travelplanner_adapter.py tests/unit/test_travelplanner_evaluator.py tests/integration/test_travelplanner.py -q` -> `43 passed`
- `uv run pytest tests/ -q` -> `216 passed`
- `bash -n scripts/run_travelplanner_smoke.sh`
- `QUERY_IDX=0 OBJECTIVE='Query 0' bash scripts/run_travelplanner_smoke.sh` -> summary JSON emitted with `llm_provider=openrouter`, `llm_model=qwen/qwen3.5-9b`

## 2026-03-17 — TravelPlanner Live-Path Failure Audit for Query 0

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `7/10`
- `confidence`: `high`
- `scope`: `Audit the latest live OpenRouter smoke run on Query 0 to identify the next highest-leverage fixes for raising official TravelPlanner pass rate`

### Outcome
The latest smoke run completes end-to-end but fails official evaluation because the generated plan is not aligned with the exact string semantics expected by the upstream scorer. The two live commonsense failures for Query 0 are `is_valid_information_in_current_city` and `is_valid_information_in_sandbox`: the model emits a bare `transportation="Flight"` instead of a route-bearing transport string, and it chooses an accommodation that exists in the raw CSV but is excluded from the upstream evaluator inventory after `dropna()`. A second structural gap is that the planner only searches the outbound flight leg and never exposes return-leg or ground-transport options, even though the official task expects a closed-circle trip from origin to destination and back. The current replan loop is also too lossy because it feeds only failed constraint keys back to the planner, not the official error messages that explain what exact field formatting or grounding must be fixed.

### Reusable Patterns (1-3)
1. For scorer-backed benchmarks, align retrieval inventories with the scorer's own filtered dataset view; "present in source CSV" is not enough if the official evaluator applies additional filtering such as `dropna()`.
2. When an evaluator parses fields by literal substrings, feed the model canonical field templates and the exact candidate strings it should copy instead of relying on high-level natural-language guidance.
3. Replan loops should carry scorer messages, not only constraint IDs, whenever the evaluator exposes concrete failure reasons that can be repaired in the next generation pass.

### Evidence
- `output/travelplanner_smoke/travelplanner_query0_20260313_174033.json`
- `output/travelplanner_smoke/travelplanner_query0_20260313_174033.log`
- `adapters/travelplanner/tools.py`
- `adapters/travelplanner/adapter.py`
- `adapters/travelplanner/workspace.py`
- `third_party/travelplanner_official/evaluation/commonsense_constraint.py`
- `third_party/travelplanner_official/tools/accommodations/apis.py`
- `python - <<'PY' ... load_dataset('osunlp/TravelPlanner', 'validation', split='validation[:1]')[0] ... PY` -> Query 0 is `Washington -> Myrtle Beach`, 3 days, budget `1400`
- `python - <<'PY' ... OfficialTravelPlannerEvaluator(...).evaluate_plan(...) ... PY` -> `is_valid_information_in_current_city=false`, `is_valid_information_in_sandbox=false`
- `python - <<'PY' ... commonsense_constraint.is_valid_information_in_sandbox(...) ... PY` -> `(False, 'The accommodation in day 1 is invalid in the sandbox.')`
- `python - <<'PY' ... Accommodations().data ... PY` -> official accommodation inventory excludes `Private sunny room with private bathroom&entrance, Myrtle Beach`

## 2026-03-17 — Dockerized TravelPlanner Benchmark Validation Baseline

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `8/10`
- `confidence`: `high`
- `scope`: `Move the TravelPlanner smoke path from host-local execution to Docker Compose so benchmark evidence matches the repository's containerized validation contract`

### Outcome
The TravelPlanner smoke entrypoint now delegates to Docker Compose by default and runs the integration test plus live OpenRouter objective inside the repository container instead of on the host shell. This keeps benchmark validation aligned with the repo's Docker baseline and removes ambiguity about whether `.env`, Python dependencies, and runtime behavior came from the workstation or from the reproducible container image. The containerized smoke reproduced the same functional result as the prior host run: integration passes, the OpenRouter path completes end-to-end, and `final_pass_rate` remains `0.0`, which confirms that the remaining work is framework quality on scorer semantics rather than host-environment drift.

### Reusable Patterns (1-3)
1. For benchmark evidence, make the top-level smoke script enter Docker first and only execute the workflow directly once inside the container.
2. When a Docker runner image exposes the project virtualenv on `PATH`, container scripts should call `python` and `pytest` directly instead of assuming host tools like `uv` exist in the runtime image.
3. If benchmark artifacts must survive the run, bind-mount the repository into the smoke service so logs, outputs, and the current working tree stay synchronized without image rebuild confusion.

### Evidence
- `docker-compose.yml`
- `scripts/run_travelplanner_smoke.sh`
- `bash -n scripts/run_travelplanner_smoke.sh`
- `docker compose config`
- `docker version --format '{{.Server.Version}}'` -> `29.1.3`
- `docker compose run --rm travelplanner-smoke python --version` -> `Python 3.11.14`
- `docker compose run --rm travelplanner-smoke pytest --version` -> `pytest 9.0.2`
- `QUERY_IDX=0 OBJECTIVE='Query 0' bash scripts/run_travelplanner_smoke.sh` -> containerized smoke completed with `llm_provider=openrouter`, `llm_model=qwen/qwen3.5-9b`, `final_pass_rate=0.0`

## 2026-03-17 — TravelPlanner Scorer-Grounded Planning Loop Passes Query 0

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `9/10`
- `confidence`: `high`
- `scope`: `Upgrade the TravelPlanner adapter and planner loop so scorer-facing outputs are grounded in benchmark search data, replay official failure messages during replanning, and validate the result through the Docker benchmark path`

### Outcome
The TravelPlanner adapter now exposes both outbound and return route options, adds explicit ground-transport and restaurant search tasks, aligns search inventories with the official sandbox view, and normalizes planner outputs into scorer-facing canonical strings. The validation loop now persists official error messages and feeds them back into replanning instead of only constraint IDs. On top of that, hotel candidates shown to the planner are filtered by stay feasibility and occupancy constraints, and the prompt explicitly enforces exact day-count and closed-circle requirements. With those framework-level changes, the Dockerized OpenRouter smoke for `Query 0` moved from partial commonsense success to a full official pass: `commonsense_micro=1.0`, `hard_constraint_micro=1.0`, and `final_pass_rate=1.0`.

### Reusable Patterns (1-3)
1. When a benchmark scorer validates literal field syntax, normalize planner outputs against tool-grounded canonical options instead of trusting raw free-form text.
2. Surface route legs and alternative transport modes as explicit search tasks in the DAG when itinerary correctness depends on them; do not hide critical benchmark context inside one monolithic prompt blob.
3. Use scorer messages to drive replanning and prune infeasible accommodation candidates by declared trip constraints before generation when those constraints are already available in the task state.

### Evidence
- `adapters/travelplanner/adapter.py`
- `adapters/travelplanner/tools.py`
- `adapters/travelplanner/workspace.py`
- `adapters/travelplanner/evaluator.py`
- `third_party/travelplanner_official/runner.py`
- `tests/unit/test_travelplanner_workspace.py`
- `tests/unit/test_travelplanner_adapter.py`
- `tests/unit/test_travelplanner_tools.py`
- `tests/unit/test_travelplanner_evaluator.py`
- `uv run pytest tests/ -q` -> `222 passed`
- `QUERY_IDX=0 OBJECTIVE='Query 0' bash scripts/run_travelplanner_smoke.sh` -> Docker smoke completed with `final_pass_rate=1.0`
- `output/travelplanner_smoke/travelplanner_query0_20260317_102020.json`

## 2026-03-17 — Dockerized TravelPlanner Full-Eval Notebook Driver

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `7/10`
- `confidence`: `high`
- `scope`: `Add a Jupyter notebook that launches the full official TravelPlanner evaluation through Docker, checkpoints one artifact per query, and runs the official scorer on the aggregated run set`

### Outcome
The repository now includes a notebook driver at `output/jupyter-notebook/travelplanner-official-full-eval.ipynb` that orchestrates the full official TravelPlanner validation campaign without moving benchmark execution out of Docker. The notebook builds or reuses the `travelplanner-smoke` image, prepares the database, counts split size, runs queries one by one through `scripts/run_travelplanner_query_export.py`, checkpoints each query JSON into a resumable `runs.json`, and finally launches `scripts/eval_travelplanner_official.py` on the complete run set. The notebook was validated by compiling every code cell successfully and by executing its setup and dataset-count path, which resolved the official validation split size to `180`.

### Reusable Patterns (1-3)
1. For long-running benchmark notebooks, keep the notebook as a driver and inspection surface only; dispatch actual benchmark execution into the same Docker service used by the official scripted path.
2. Persist one structured JSON per query plus an aggregate `runs.json` checkpoint so interrupted benchmark campaigns can resume without rerunning completed queries.
3. Run the official scorer as a separate final container step against aggregated predictions so generation, checkpointing, and evaluation remain reproducible and inspectable.

### Evidence
- `output/jupyter-notebook/travelplanner-official-full-eval.ipynb`
- `scripts/run_travelplanner_query_export.py`
- `scripts/eval_travelplanner_official.py`
- `python - <<'PY' ... ast.parse(...) ... PY` -> all notebook code cells compiled successfully
- `python - <<'PY' ... exec cells 2,3 ... PY` -> notebook helper/config cells executed successfully
- `python - <<'PY' ... exec cell 4 with BUILD_IMAGE=False PREPARE_DATA=False MAX_QUERIES=1 ... PY` -> Docker dataset count succeeded with `total_queries_in_split=180`

## 2026-03-17 — Docker Script Entrypoints Need Explicit Repo Root Imports

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `6/10`
- `confidence`: `high`
- `scope`: `Fix the notebook-driven full evaluation path after every query failed with runtime import errors inside Docker`

### Outcome
The full-evaluation notebook had recorded `180` runtime failures because each containerized query invocation executed `python /app/scripts/run_travelplanner_query_export.py`, which put `/app/scripts` on `sys.path` instead of the repository root and broke imports like `from core.environment import Environment`. The export script now inserts `REPO_ROOT` into `sys.path` before importing project modules, matching the robustness already used by the official evaluation script. After the fix, the same Docker entrypoint succeeds for `--help` and for a minimal `Query 0` export run, which returns structured JSON with `status="ok"` instead of exiting with `ModuleNotFoundError`.

### Reusable Patterns (1-3)
1. Any repo script meant to run as `python /abs/path/to/script.py` inside Docker should prepend the repository root to `sys.path` before importing local packages.
2. When a resumable benchmark notebook marks failed queries as checkpointed, diagnose the first per-query log before rerunning the whole split; uniform failures often indicate an entrypoint bug, not model quality.
3. Validate Docker benchmark entrypoints with one cheap `--help` run plus one minimal real invocation before launching the full split campaign.

### Evidence
- `scripts/run_travelplanner_query_export.py`
- `output/travelplanner_official_full_eval/20260317_112022/queries/query_000.log` -> `ModuleNotFoundError: No module named 'core'`
- `python -m py_compile scripts/run_travelplanner_query_export.py`
- `docker compose run --rm travelplanner-smoke python /app/scripts/run_travelplanner_query_export.py --help`
- `docker compose run --rm travelplanner-smoke python /app/scripts/run_travelplanner_query_export.py --objective 'Query 0' --query-idx 0 --seed 42 --max-ticks 1` -> exits `0` and emits structured JSON

## 2026-03-22 — Controlled Qwen TravelPlanner Framework Comparison Notebook

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `8/10`
- `confidence`: `high`
- `scope`: `Add a reproducible notebook to compare solo Qwen, SwarmAgentic, and StigmergiAgentic on TravelPlanner with the same OpenRouter model and the same official scorer`

### Outcome
The repository now includes a controlled comparison notebook at `output/jupyter-notebook/travelplanner-framework-comparison-openrouter-qwen35-9b.ipynb` that runs three benchmark arms on the same routed model `qwen/qwen3.5-9b`: a solo baseline, SwarmAgentic, and StigmergiAgentic. The notebook reuses the local official scorer, writes one output subtree per method, and renders a final comparison table after evaluation. To support this protocol, the repo now also includes a solo TravelPlanner export runner plus small interoperability scripts that patch a cloned SwarmAgentic checkout for OpenRouter, normalize its saved state/results, and convert them into the local scorer format. The notebook and all helper scripts were validated by compiling every code cell and every Python entrypoint successfully.

### Reusable Patterns (1-3)
1. For framework comparisons, add a solo-model arm alongside agentic systems so gains can be attributed to orchestration rather than the hosted model alone.
2. When reusing an external benchmark repo, keep compatibility glue outside the main runtime: patch the cloned repo in-place, then convert its artifacts into one local scorer format.
3. Store each method's official evaluation JSON under a method-specific subtree and render the final table from those scorer outputs rather than from raw generation logs.

### Evidence
- `output/jupyter-notebook/travelplanner-framework-comparison-openrouter-qwen35-9b.ipynb`
- `scripts/run_travelplanner_solo_query_export.py`
- `scripts/prepare_swarmagentic_openrouter.py`
- `scripts/export_swarmagentic_save_jsonl.py`
- `scripts/convert_swarmagentic_travelplanner_results.py`
- `scripts/render_travelplanner_comparison_table.py`
- `python - <<'PY' ... compile(code_cell_source, ...) ... PY` -> all notebook code cells compiled successfully
- `python -m py_compile scripts/run_travelplanner_solo_query_export.py scripts/prepare_swarmagentic_openrouter.py scripts/export_swarmagentic_save_jsonl.py scripts/convert_swarmagentic_travelplanner_results.py scripts/render_travelplanner_comparison_table.py`

## 2026-04-02 — TravelPlanner Framework Comparison Review Hygiene

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `7/10`
- `confidence`: `high`
- `scope`: `Audit the scientific validity of the solo-versus-StigmergiAgentic TravelPlanner comparison notebook before using it in thesis reporting`

### Outcome
The persisted run `output/travelplanner_framework_compare/20260326_132646` is internally consistent for the two completed arms and confirms that StigmergiAgentic improves `final_pass_rate` from `6/180` to `18/180` on the same validation queries with the same official scorer. The review also found three reporting risks that matter scientifically: the notebook output mixes multiple `RUN_TAG` values from different executions, the current evidence is single-run and therefore lacks variance estimates for a stochastic LLM setting, and the Swarm interoperability script changes more than provider compatibility, so any future three-way claim must either disclose a patched variant explicitly or narrow the comparison claim.

### Reusable Patterns (1-3)
1. Treat benchmark notebooks as publishable artifacts only after rerendering them from one clean run tag; mixed historical cell outputs break reproducibility even when the underlying JSON files are correct.
2. For framework comparisons on stochastic LLM benchmarks, report paired per-query results plus cost/token deltas and at least one uncertainty estimate; aggregate pass rates alone are too weak for thesis-level claims.
3. When adapting an external baseline, any patch that changes retries, exception handling, checkpointing, or optimizer control flow must be described as a behavioral fork, not as a pure compatibility shim.

### Evidence
- `output/jupyter-notebook/travelplanner-framework-comparison-openrouter-qwen35-9b.ipynb`
- `output/travelplanner_framework_compare/20260326_132646/solo/official_eval.json`
- `output/travelplanner_framework_compare/20260326_132646/stigmergiagentic/official_eval.json`
- `output/travelplanner_framework_compare/20260326_132646/solo/runs.json`
- `output/travelplanner_framework_compare/20260326_132646/stigmergiagentic/runs.json`
- `python - <<'PY' ... paired comparison over runs.json ... PY` -> `final_pass` improved on 13 queries, degraded on 1, exact McNemar `p=0.0018310546875`
- `python - <<'PY' ... aggregate tokens/cost from runs.json ... PY` -> StigmergiAgentic used about `4.03x` tokens and `4.14x` cost versus the solo arm

## 2026-04-02 - Fair SwarmAgentic Qwen Benchmark Orchestration

- `repo_slug`: `stigmergiagentic-33b989`
- `type`: `implementation`
- `area`: `benchmarking`
- `summary`: `Refactored the Qwen TravelPlanner comparison notebook so SwarmAgentic runs through a dedicated orchestrator script with preflight/pilot/full modes, explicit infra-vs-framework failure statuses, mode-specific artifacts, and a separate non-comparable paper-context note.`
- `impact_score`: `8/10`
- `confidence`: `high`
- `scope`: `Stabilize the thesis benchmark workflow around qwen/qwen3.5-9b without mixing provider outages into framework scores`

### Outcome
The notebook now delegates SwarmAgentic execution to `scripts/run_swarmagentic_benchmark.py`, which writes `benchmark_status.json`, `reproducibility.md`, `context.md`, mode-specific `runs.json`, and `official_eval.json` when available. The same change also extends `scripts/eval_travelplanner_official.py` with a subset-aware scorer for pilot runs, and switches notebook-local repo scripts from `uv run` to `python` so the benchmark no longer depends on a broken project `.venv` for solo/StigmergiAgentic/offline scoring steps.

### Reusable Patterns (1-3)
1. Keep benchmark notebooks as orchestration surfaces only; move fragile multi-phase baseline execution into versioned Python scripts that emit explicit status and artifact files.
2. Separate `infra_failure` from `framework_failure` in LLM benchmark runs so provider outages do not get silently converted into model or framework score regressions.
3. When a project `.venv` becomes unreliable, route notebook-local scripts through the known-good interpreter and reserve isolated virtualenvs only for external cloned baselines that genuinely need them.

### Evidence
- `scripts/run_swarmagentic_benchmark.py`
- `scripts/eval_travelplanner_official.py`
- `scripts/update_qwen35_benchmark_notebook.py`
- `output/jupyter-notebook/travelplanner-framework-comparison-openrouter-qwen35-9b.ipynb`
- `python -m py_compile scripts/run_swarmagentic_benchmark.py scripts/eval_travelplanner_official.py scripts/update_qwen35_benchmark_notebook.py scripts/prepare_swarmagentic_openrouter.py`
- `python -m json.tool output/jupyter-notebook/travelplanner-framework-comparison-openrouter-qwen35-9b.ipynb >/dev/null`
- `python - <<'PY' ... compile notebook cells 3,5,9,11,13,15 ... PY`
- `python scripts/eval_travelplanner_official.py --runs-json <tmp> --database-root data/travelplanner/database --split validation --start-index 0 --end-index 1`

## 2026-04-03 - Dedicated SwarmAgentic Full Scientific Notebook

- `repo_slug`: `stigmergiagentic-33b989`
- `type`: `implementation`
- `area`: `benchmarking`
- `summary`: `Created a standalone notebook dedicated to a strict full SwarmAgentic benchmark against the already-completed Solo and StigmergiAgentic reference runs, with official-score comparison and paired final-pass analysis.`
- `impact_score`: `7/10`
- `confidence`: `high`
- `scope`: `Give thesis work a baseline-only notebook that runs Swarm full evaluation without reusing the heavier three-arm orchestration notebook`

### Outcome
The new notebook `travelplanner-swarmagentic-full-scientific-comparison-openrouter-qwen35-9b.ipynb` runs only the SwarmAgentic full benchmark, blocks the final scientific comparison when Swarm ends in infra/framework failure, loads the completed reference artifacts from run `20260326_132646` by default, and renders both the official aggregate table and paired final-pass comparisons against Solo and StigmergiAgentic.

### Reusable Patterns (1-3)
1. When one baseline is the unstable part of a comparison campaign, give it a dedicated notebook instead of forcing every rerun through a single all-arms orchestration notebook.
2. Default strict comparison notebooks to known-good reference artifact paths, but keep those paths overridable by environment variable so the notebook stays reusable across runs.
3. For thesis-grade reruns, combine official aggregate metrics with paired per-query final-pass comparisons in the same notebook so reproducibility and comparative significance are visible together.

### Evidence
- `scripts/create_swarmagentic_full_scientific_notebook.py`
- `output/jupyter-notebook/travelplanner-swarmagentic-full-scientific-comparison-openrouter-qwen35-9b.ipynb`
- `output/travelplanner_framework_compare/20260326_132646/solo/official_eval.json`
- `output/travelplanner_framework_compare/20260326_132646/stigmergiagentic/official_eval.json`
- `output/travelplanner_framework_compare/20260326_132646/solo/runs.json`
- `output/travelplanner_framework_compare/20260326_132646/stigmergiagentic/runs.json`
- `python -m py_compile scripts/create_swarmagentic_full_scientific_notebook.py`
- `python -m json.tool output/jupyter-notebook/travelplanner-swarmagentic-full-scientific-comparison-openrouter-qwen35-9b.ipynb >/dev/null`
- `python - <<'PY' ... compile notebook code cells 2-10 ... PY`

## 2026-04-07 - Notebook Interpreter Auto-Selection

- `repo_slug`: `stigmergiagentic-33b989`
- `type`: `bugfix`
- `area`: `benchmarking`
- `summary`: `Hardened the dedicated SwarmAgentic scientific notebook so it auto-selects a Python interpreter that can import repo-required modules like datasets, instead of assuming bare shell python is usable.`
- `impact_score`: `6/10`
- `confidence`: `high`
- `scope`: `Prevent setup failures when Jupyter/kernel python and shell python diverge`

### Outcome
The notebook generator now emits a helper that probes several Python candidates (`sys.executable`, repo `.venv`, Miniconda, `/usr/bin/python3`) and picks the first interpreter that can import `datasets`, `yaml`, and `pydantic`. The generated notebook then uses `REPO_PYTHON` for `setup_travelplanner.py`, dataset counting, Swarm benchmark orchestration, and comparison-table rendering.

### Reusable Patterns (1-3)
1. In notebooks that shell out to repository scripts, resolve the actual working interpreter explicitly instead of calling `python` by name.
2. When the notebook depends on third-party data tooling, test the interpreter against required imports up front and fail early with a precise error.
3. Use the selected interpreter consistently for every local script in the notebook to avoid mixed-environment drift across cells.

### Evidence
- `scripts/create_swarmagentic_full_scientific_notebook.py`
- `output/jupyter-notebook/travelplanner-swarmagentic-full-scientific-comparison-openrouter-qwen35-9b.ipynb`
- `python - <<'PY' ... import datasets,yaml,pydantic ... PY`
- `python - <<'PY' ... inspect notebook cells 2,6,7,8 for REPO_PYTHON ... PY`

## 2026-04-07 — SwarmAgentic Benchmark Watchdog and Live Monitoring

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `8/10`
- `confidence`: `high`
- `scope`: `SwarmAgentic TravelPlanner benchmark observability hardening for Qwen/OpenRouter full scientific runs`

### Outcome
Added explicit runtime observability to the SwarmAgentic comparison path: the benchmark runner now emits heartbeats, snapshots watched artifact paths, writes a live monitor JSON, kills stalled train/eval phases after configurable inactivity, refreshes stale clones when the local patch revision changes, and the patched upstream `pso.py` / `test.py` now print step-level progress so notebook runs no longer appear silently frozen.

### Reusable Patterns (1-3)
1. For long-running third-party LLM baselines, pair provider retries with an outer watchdog based on `child output or artifact movement`, not only subprocess liveness.
2. Version local patches to external benchmark clones with a small revision file and automatically refresh clones when the patch revision changes, so new reliability fixes are actually applied.
3. Surface benchmark observability in two layers: live stdout heartbeats for notebook usability and file-backed monitor artifacts (`live_monitor.json`, `heartbeat.log`) for post-mortem debugging.

### Evidence
- `scripts/run_swarmagentic_benchmark.py`
- `scripts/prepare_swarmagentic_openrouter.py`
- `scripts/create_swarmagentic_full_scientific_notebook.py`
- `output/jupyter-notebook/travelplanner-swarmagentic-full-scientific-comparison-openrouter-qwen35-9b.ipynb`
- `python -m py_compile scripts/run_swarmagentic_benchmark.py scripts/prepare_swarmagentic_openrouter.py scripts/create_swarmagentic_full_scientific_notebook.py`
- Fresh upstream smoke patch on `/private/tmp/swarmagentic_patch_test.TpvCDT/repo` with `python -m py_compile /tmp/swarmagentic_patch_test.TpvCDT/repo/travelplanner/swarm/pso.py /tmp/swarmagentic_patch_test.TpvCDT/repo/travelplanner/swarm/test.py`

## 2026-04-09 — TravelPlanner Organization-Philosophy Scientific Pack

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `9/10`
- `confidence`: `high`
- `scope`: `Replace named-framework comparison with a publication-oriented organization-philosophy benchmark on TravelPlanner`

### Outcome
Added a new scientific benchmarking path for TravelPlanner that evaluates six organization philosophies under the same provider/model/scorer contract, orchestrates preflight/pilot/full gates across three seeds, and produces a reusable paper pack with main tables, paired final-pass statistics, reproducibility reporting, threats to validity, and a DSR Episode 1 summary. The repo now includes controlled baselines for direct solo, CoT solo, self-refine solo, and centralized planner-executor, alongside the existing LangGraph supervisor and StigmergiAgentic arms.

### Reusable Patterns (1-3)
1. When the scientific claim targets coordination philosophy rather than vendor tooling, benchmark named implementations only as backends and keep the public protocol framed around organizational forms.
2. Split large benchmark studies into two repository scripts: one for run-matrix orchestration with gating/status taxonomy and one for analysis-pack generation from persisted artifacts.
3. Treat publishable notebooks as Markdown-first orchestration surfaces that trigger repo scripts and display generated artifacts, not as places where the core experimental logic lives inline.

### Evidence
- `adapters/travelplanner/scientific_baselines.py`
- `scripts/run_travelplanner_scientific_study.py`
- `scripts/build_travelplanner_scientific_pack.py`
- `scripts/create_travelplanner_organization_scientific_notebook.py`
- `output/jupyter-notebook/travelplanner-organization-philosophy-scientific-comparison-openrouter-qwen35-9b.ipynb`
- `documentation/travelplanner_organization_scientific_protocol.md`
- `pytest tests/unit/test_travelplanner_scientific_baselines.py -q`
- `pytest tests/unit/test_travelplanner_langgraph_supervisor.py -q`

## 2026-04-09 — TravelPlanner Official Evaluator Path Hardening

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `7/10`
- `confidence`: `high`
- `scope`: `Fix LangGraph benchmark crashes caused by stale official-eval database symlinks and runtime relative-path lookups`

### Outcome
Hardened the subprocess bridge to the upstream TravelPlanner evaluator so query-level validation no longer crashes when the repo-global `third_party/travelplanner_official/database` symlink points to a stale location or when upstream modules open `../database/...` files at runtime outside the expected working directory. The runner now recreates stale symlinks safely, re-enters the `evaluation/` directory for the sensitive runtime calls, and is covered by a regression test that poisons the symlink before evaluation.

### Reusable Patterns (1-3)
1. When vendoring evaluation code that relies on relative paths, wrap every runtime entrypoint that performs file IO in a temporary working-directory context instead of fixing imports only.
2. Treat repo-global symlinks used by subprocess bridges as mutable state: validate the target each invocation and recreate stale or broken links before executing third-party code.
3. Add regression tests that deliberately corrupt integration state first, then assert the bridge repairs it automatically, so long-running benchmarks do not rediscover the same failure hours later.

### Evidence
- `third_party/travelplanner_official/runner.py`
- `tests/unit/test_travelplanner_evaluator.py`
- `python -m py_compile third_party/travelplanner_official/runner.py`
- `pytest tests/unit/test_travelplanner_evaluator.py -q`
- `pytest tests/unit/test_travelplanner_langgraph_supervisor.py -q`

## 2026-04-10 — Non-Invasive Benchmark Progress Inspection

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `4/10`
- `confidence`: `high`
- `scope`: `Read long-running TravelPlanner study progress and partial results without perturbing the active Docker benchmark`

### Outcome
Confirmed that the active scientific study can be monitored safely by reading `scientific_pack/run_registry.csv`, per-arm `official_eval.json`, and the newest `queries/query_XXX.json` timestamps instead of attaching to the subprocess or touching notebook state. This surfaced complete `solo_direct` results, partial/failed `planner_executor` status, and the live `langgraph_supervisor` seed progression while the study kept running.

### Reusable Patterns (1-3)
1. For long notebook-driven benchmarks, treat persisted registry rows and query artifact mtimes as the source of truth for progress rather than cell output.
2. Only report aggregate metrics from arms that already have `official_eval.json`; classify everything else as in-progress or invalid rather than extrapolating.
3. Distinguish a completed arm seed from a completed arm family, especially when the study averages across multiple seeds.

### Evidence
- `output/travelplanner_framework_compare/20260409_233919/scientific_pack/run_registry.csv`
- `output/travelplanner_framework_compare/20260409_233919/runs/solo_direct/seed_42/full/official_eval.json`
- `output/travelplanner_framework_compare/20260409_233919/runs/langgraph_supervisor/seed_42/full/official_eval.json`
- `output/travelplanner_framework_compare/20260409_233919/runs/langgraph_supervisor/seed_44/full/queries/query_046.json`

## 2026-04-11 — Scientific Baseline Fallback Hardening

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `8/10`
- `confidence`: `high`
- `scope`: `Prevent TravelPlanner self-refine and planner-executor study arms from aborting on truncated JSON responses`

### Outcome
Hardened the scientific baseline runners so truncated structured outputs no longer abort entire benchmark seeds. `Self-Refine` now compacts evaluator feedback and falls back to a local critique object when the reviewer JSON is invalid, while `Planner-Executor` now requests a smaller planner blueprint and can recover by generating a fallback itinerary then converting it into a normalized blueprint when the planner JSON is truncated.

### Reusable Patterns (1-3)
1. When a benchmark baseline uses multiple structured-output substeps, treat non-essential intermediate JSON as recoverable and derive a deterministic local fallback instead of failing the whole query.
2. Reduce structured-output failure rate by asking planner schemas to emit only non-empty day entries and reconstructing omitted defaults downstream.
3. For planner-style baselines, a direct valid itinerary can serve as a reliable intermediate fallback artifact from which a smaller blueprint is reconstructed.

### Evidence
- `adapters/travelplanner/scientific_baselines.py`
- `tests/unit/test_travelplanner_scientific_baselines.py`
- `python -m py_compile adapters/travelplanner/scientific_baselines.py`
- `pytest tests/unit/test_travelplanner_scientific_baselines.py -q`
- `pytest tests/unit/test_travelplanner_langgraph_supervisor.py tests/unit/test_travelplanner_evaluator.py -q`

## 2026-04-12 — V5.1 Plan Executability Review for TravelPlanner

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `7/10`
- `confidence`: `high`
- `scope`: `Review the updated V5.1 scientific improvement plan against the current TravelPlanner codebase to confirm what is now sound and what is still underspecified`

### Outcome
Confirmed that V5.1 is materially stronger than V5 because it now targets the main structural bottleneck (single-destination TravelPlanner encoding), uses the correct statistical framing for binary `final_pass`, and separates ablation stages cleanly. The remaining gaps are operational rather than conceptual: the multi-city redesign cannot rely on parsing `dest` alone, the proposed ACO heuristic hook is not currently pluggable from the adapter layer, and campaign robustness work should extend the existing per-query checkpointing instead of reintroducing it.

### Reusable Patterns (1-3)
1. Treat a scientific improvement plan as executable only after every major task is checked against the current extension points in code, not just against the intended architecture.
2. When a benchmark adapter compresses a structured task into a scalar field like `dest`, fix the task representation before tuning prompts or hyperparameters.
3. If a benchmark runner already checkpoints per query, subsequent robustness tasks should focus on continue-on-error semantics, failure taxonomy, and clean resume behavior rather than duplicate checkpoint logic.

### Evidence
- `adapters/travelplanner/workspace.py`
- `adapters/travelplanner/adapter.py`
- `adapters/travelplanner/tools.py`
- `core/agent.py`
- `scripts/run_travelplanner_framework_benchmark.py`

## 2026-04-12 — V5.1-Final Plan Review: Partial Scoring Caveat

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `6/10`
- `confidence`: `high`
- `scope`: `Validate the final revised V5.1 benchmark-improvement plan against the scorer and runner behavior before approving it as executable`

### Outcome
Validated that the revised V5.1-final plan closes nearly all earlier methodological and implementation gaps. The remaining caveat is in T5 wording: the official TravelPlanner scorer does not produce a truly partial denominator when some queries fail. Missing predictions are evaluated as empty plans over the full query range, so the campaign can continue and still emit a full `official_eval.json`, but that file is not an `N-k` subset score unless the scorer is explicitly run on a reduced index range.

### Reusable Patterns (1-3)
1. When designing continue-on-error benchmark runners, distinguish `partial artifact availability` from `partial official scoring`; many scorers silently treat missing predictions as empty failures under the full denominator.
2. Acceptance tests for resilience features should reference the exact scorer semantics, not the intended runner semantics.
3. A scientific plan can be considered execution-ready even when one wording fix remains, provided the remaining issue is about measurement phrasing rather than architecture or validity.

### Evidence
- `scripts/run_travelplanner_framework_benchmark.py`
- `scripts/eval_travelplanner_official.py`
- `adapters/travelplanner/workspace.py`

## 2026-04-12 — Official Scoring Wording Patch for V5.1 T5

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `5/10`
- `confidence`: `high`
- `scope`: `Align the V5.1 benchmark-plan wording for continue-on-error with the actual denominator semantics of the official TravelPlanner scorer`

### Outcome
Updated the V5.1 plan so T5 no longer describes continue-on-error runs as producing a subset-scored `official_eval.json`. The plan now states the correct behavior: the campaign continues, failed queries are checkpointed and summarized, and the official scorer still evaluates the full requested range, treating missing predictions as empty failed plans.

### Reusable Patterns (1-3)
1. Distinguish `campaign continuity` from `subset official scoring` in benchmark plans; they are not the same behavior.
2. Acceptance criteria for resilience work should describe both the runner artifact semantics and the scorer denominator semantics.
3. Wording fixes in research plans matter when they change how future readers interpret benchmark validity.

### Evidence
- `documentation/redisgn_v2/plan_v5_framework_improvement.md`
- `scripts/eval_travelplanner_official.py`
- `scripts/run_travelplanner_framework_benchmark.py`

## 2026-04-12 — TravelPlanner Multi-City Adapter T0

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `8/10`
- `confidence`: `high`
- `scope`: `Implement V5.1 T0 by inferring a TravelPlanner city sequence from the local databases, expanding the adapter DAG to multi-city routing, and updating prompts/search payload handling without touching core/`

### Outcome
Implemented a TravelPlanner-side multi-city path that infers `city_sequence` from the local city/state inventory and route availability, injects that sequence into normalized queries and objectives, expands `initial_markers()` into alternating route and per-city search tasks, and teaches the planning toolchain to consume dynamic per-city/per-leg result keys while preserving the single-city keys for backward compatibility. Added a dedicated multi-city fixture and regression tests covering inferred city order, linear inter-city dependencies, and prompt/search payload expansion.

### Reusable Patterns (1-3)
1. When a benchmark query names a state or region but the runtime needs concrete cities, infer the city sequence from inventory coverage plus route feasibility instead of overloading one scalar destination field.
2. Preserve legacy single-entity keys while introducing prefix-based dynamic keys for multi-entity expansion; then make downstream prompt and normalization code match by prefix rather than by exact key.
3. Model multi-city workflows as alternating `route -> city search -> next route` dependencies so the final planning task can depend on one explicit, auditable DAG instead of hidden sequencing logic.

### Evidence
- `adapters/travelplanner/workspace.py`
- `adapters/travelplanner/adapter.py`
- `adapters/travelplanner/tools.py`
- `tests/fixtures/travelplanner_data.py`
- `tests/unit/test_travelplanner_multi_city.py`

## 2026-04-14 — TravelPlanner T5 Continue-on-Error Runner

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `8/10`
- `confidence`: `high`
- `scope`: `Implement T5 end-to-end in the TravelPlanner framework benchmark runner with per-query failure checkpoints, failure taxonomy, and explicit full-denominator scorer semantics`

### Outcome
Implemented T5 in the TravelPlanner batch benchmark runner so a single failing query no longer aborts the whole seed. The runner now persists failed query artifacts with empty-plan outputs and machine-readable failure reasons, continues to the next query, writes an enriched `benchmark_summary.json` with success/failure ratios and tolerance status, and keeps the official scorer contract explicit: campaign resilience improves resumability and traceability without changing the official evaluation denominator.

### Reusable Patterns (1-3)
1. In batch benchmark runners, convert per-item subprocess failures into checkpointable result payloads so resumed runs stay deterministic and auditable.
2. Keep failed query artifacts structurally compatible with downstream scorers by emitting explicit empty-plan outputs rather than omitting the query from the run ledger.
3. When resilience changes runner behavior but not scorer behavior, encode the denominator semantics directly in the machine-readable summary to prevent later misinterpretation.

### Evidence
- `scripts/run_travelplanner_framework_benchmark.py`
- `tests/unit/test_travelplanner_benchmark_runner.py`
- `scripts/eval_travelplanner_official.py`

## 2026-04-16 — TravelPlanner V5-Full Execution Hardening

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `9/10`
- `confidence`: `high`
- `scope`: `Implement TravelPlanner-side V5-full execution upgrades (preset, marker shaping, train-only few-shots, train-only tuning script, and benchmark-runner subset alignment) without modifying core/`

### Outcome
Implemented the V5-full execution layer entirely outside `core/`: a new `config/ablation/v5_full.yaml` preset, marker shaping in TravelPlanner tools, train-only few-shot prompt enrichment with warning-only fallback, and a train-only ACO tuning script that writes temporary train configs and can apply the winning values back to the V5 preset. The existing framework benchmark runner was extended to accept the planned `stigmergic` CLI alias plus inclusive `--start/--end`, and to propagate the evaluated subset bounds to the official scorer. Local validation finished with `275 passed` once the declared `langgraph` dependency was made available for the run.

### Reusable Patterns (1-3)
1. When a benchmark improvement plan forbids `core/` changes, concentrate steering logic in adapter-local tool state updates plus benchmark-script alignment rather than pushing experiment-specific behavior into the generic runtime.
2. For train-only tuning against a validation preset, generate temporary split-overridden configs for the tuning runs and only write the winning scalar hyperparameters back to the reusable base preset.
3. If a benchmark runner already emits per-query artifacts, make subset official scoring explicit by forwarding the requested index bounds to the scorer instead of inferring subset semantics from the partial run ledger.

### Evidence
- `config/ablation/v5_full.yaml`
- `adapters/travelplanner/tools.py`
- `scripts/run_travelplanner_framework_benchmark.py`
- `scripts/tune_aco_travelplanner.py`
- `tests/unit/test_travelplanner_marker_shaping.py`

## 2026-04-17 — V6 Framework Plan Review for Executability and Attribution

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `7/10`
- `confidence`: `high`
- `scope`: `Review the proposed V6 framework-improvement plan against the current runtime extension points, benchmark methodology, and existing TravelPlanner repair loop`

### Outcome
Reviewed `documentation/redisgn_v2/plan_v6_framework_general_improvement.md` against the live codebase and found the overall direction methodologically strong: benchmark freeze, framework-vs-adapter separation, and stratified metrics are all sound. The main caveats are executional: the idle-cycle evidence currently mixes seeds across configs, T1 and T5 overlap with the existing emergence feedback control plane, `marker_reads` are not a reliable proxy for lock contention, T2 is a representation-contract redesign rather than a light runtime tweak, and T3 partly duplicates an adapter-local repair loop that already exists in TravelPlanner.

### Reusable Patterns (1-3)
1. Before accepting a framework-improvement plan, verify that every proposed hook maps to an existing runtime extension point rather than assuming the current architecture already exposes the needed control surface.
2. If a runtime already has one adaptive control loop, route new anti-stagnation and temperature logic through that same control plane unless you explicitly want competing controllers.
3. When comparing benchmark configs, keep seed pairing consistent across variants before drawing causal conclusions from pass-rate deltas.

### Evidence
- `documentation/redisgn_v2/plan_v6_framework_general_improvement.md`
- `core/orchestrator.py`
- `core/emergence.py`
- `core/agent.py`
- `core/marker_store.py`
- `tools/decompose.py`
- `adapters/travelplanner/tools.py`

## 2026-04-18 — V6 Plan Rewritten Into a Three-Arm, Executable Framework Ablation

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `8/10`
- `confidence`: `high`
- `scope`: `Rewrite the V6 framework-improvement plan into a more executable roadmap with paired-seed baseline discipline, a unified control plane, and three attributable ablation arms`

### Outcome
Rewrote `documentation/redisgn_v2/plan_v6_framework_general_improvement.md` into a tighter V6 roadmap. The new version keeps the original scientific boundary conditions, explicitly downgrades mixed-seed `idle=16` evidence to directional status until rerun on paired seeds, merges anti-stagnation and dynamic adaptation into one runtime control plane, reduces the first ablation cycle to `V6-A`, `V6-B`, and `V6-C`, and defers persistent subgoal coverage to a separate `V6.2` track because it changes task representation rather than lightly tuning the runtime.

### Reusable Patterns (1-3)
1. When an improvement plan has too many additive steps, convert it into a short branching ablation around one shared core change so each gain remains attributable.
2. If benchmark evidence mixes seeds across configs, preserve the insight but mark it as directional until a paired-seed replay confirms the effect.
3. Separate runtime control-plane upgrades from task-representation redesigns; the former fit first-pass ablations, the latter deserve their own scoped plan.

### Evidence
- `documentation/redisgn_v2/plan_v6_framework_general_improvement.md`

## 2026-04-18 — V6 Phase-1 Runtime Controls, Lock Telemetry, and Generic Targeted Repair

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `9/10`
- `confidence`: `high`
- `scope`: `Implement the first executable V6 framework wave in core runtime + TravelPlanner bridge, with frozen V5 reference and dedicated V6 ablation presets`

### Outcome
Implemented the executable phase-1 V6 framework surface in the generic runtime. `core.marker_store` now records explicit lock-attempt telemetry through `marker_lock_events` and exposes aggregated `lock_stats`; `core.orchestrator` now owns a bounded recovery controller with dynamic idle and activation audit; `core.agent` now supports short-horizon stickiness plus recovery-aware target choice; and `core.tool_registry` / `core.environment` now expose a generic validation/repair contract that can materialize repair markers when enabled. TravelPlanner was bridged to that contract behind an opt-in flag, and new ablation presets (`v6_base`, `v6_A`, `v6_B`, `v6_C`) were added while leaving `v5_full.yaml` untouched.

### Reusable Patterns (1-3)
1. For benchmark-sensitive runtime upgrades, preserve the old reference preset and express new behavior through explicit config gates plus dedicated ablation presets.
2. If a coordination controller needs contention awareness, instrument real lock attempts and conflicts directly, then expose the aggregated signal both to the controller and to agent snapshots.
3. A generic repair contract stays clean when the adapter owns `what to repair` and `why`, while the runtime owns `how to materialize and track the repair execution surface`.

### Evidence
- `core/marker_store.py`
- `core/orchestrator.py`
- `core/agent.py`
- `core/environment.py`
- `core/tool_registry.py`
- `adapters/travelplanner/tools.py`
- `config/ablation/v6_base.yaml`
- `config/ablation/v6_A.yaml`
- `config/ablation/v6_B.yaml`
- `config/ablation/v6_C.yaml`
- `documentation/decisions/20260418-sprint8-v6-general-runtime-controls.md`

## 2026-04-21 — Sprint 9 Groundwork Contracts for Persistent Skills and Protocol Compilation

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `8/10`
- `confidence`: `high`
- `scope`: `Prepare the runtime and project docs for Sprint 9 with opt-in config surfaces, protocol-compilation seams, cross-run protocol helpers, and targeted unit coverage`

### Outcome
Prepared a non-breaking Sprint 9 groundwork layer on top of the Sprint 8 runtime. The repo now exposes explicit config sections for `skill_library`, `protocol`, `emergence.cross_run`, `reinforcement.promotion_min_uses`, and `agents.protocol_compiler`; the assistant domain has an opt-in `compile_protocol()` path backed by `ProtocolSpec` and a dedicated compiler prompt; `main.py` can now prefer compiled marker DAGs while gracefully falling back to `initial_markers()`; and the new cross-run helpers `compute_protocol_score()` plus `clamp_cross_run_adaptations()` define the first stable contract for future persistent coordination artifacts. I also switched `llm/__init__.py` and `adapters/__init__.py` to lazy imports so prompt/schema-only code paths and unit tests no longer pull the full heavy dependency graph by default.

### Reusable Patterns (1-3)
1. Before wiring persistent runtime features, land the smallest stable contract surface first: config keys, schemas, prompts, adapter seam, and runtime fallback.
2. When a package-level `__init__` drags heavy optional dependencies into lightweight paths, convert exports to lazy imports so unit tests and prompt-only workflows stay fast and isolated.
3. For thesis-facing adaptation features, keep train/adapt and frozen-eval presets separate from day one, even before the persistence loop is fully implemented.

### Evidence
- `config/default.yaml`
- `config/travelplanner_adapt.yaml`
- `config/travelplanner_eval.yaml`
- `core/schemas.py`
- `core/emergence.py`
- `adapters/base.py`
- `adapters/assistant/adapter.py`
- `main.py`
- `tests/unit/test_protocol_compiler.py`
- `documentation/decisions/20260421-sprint9-groundwork-persistent-skills-protocols-and-compiler.md`

## 2026-04-23 — Final Campaign Live Monitoring Sanity Check

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `6/10`
- `confidence`: `high`
- `scope`: `Verify whether the final Docker campaign is progressing normally without disturbing running services, with emphasis on cross-run skills/protocols and sequential Gemma baselines`

### Outcome
Confirmed that the three final scientific campaign containers are still alive and actively computing, and that the apparently empty Gemma baseline folders do not indicate a failure yet. `gemma-baselines` runs frameworks sequentially, so only `solo_direct` is expected to populate first; the `zsh: no matches found` messages come from unmatched `*.json` globs during live counting, not from the benchmark itself. Read-only inspection of `campaign_results/*/pheromones/{skills,protocols}.db` also confirmed that both stigmergic services have persistent promoted skills and coordination-protocol markers with nontrivial `usage_count` and `latest` protocol entries, while `docker stats` and `docker top` showed active Python processes still working on long-running queries (`Gemma C3 Q18`, `DeepSeek C3 Q42`, `Gemma baseline solo_direct Q130`) rather than a stalled pipeline.

### Reusable Patterns (1-3)
1. During live campaign monitoring, treat unmatched shell globs in `zsh` as a counting artifact first and confirm directory creation order before suspecting a benchmark failure.
2. For in-progress Docker campaigns, combine `docker stats`, `docker top`, recent file mtimes, and read-only SQLite inspection to distinguish genuine stalls from simply long-running queries.
3. When validating cross-run learning during execution, inspect `skills.db` and `protocols.db` in read-only mode and look for promoted `skill` markers plus `coordination_protocol::*::latest` entries instead of relying only on output JSON counts.

### Evidence
- `docker-compose.campaign.yml`
- `scripts/run_gemma_baselines_docker.sh`
- `campaign_results/gemma-baselines/solo_direct/`
- `campaign_results/gemma-stigmergie/pheromones/skills.db`
- `campaign_results/gemma-stigmergie/pheromones/protocols.db`
- `campaign_results/deepseek-stigmergie/pheromones/skills.db`
- `campaign_results/deepseek-stigmergie/pheromones/protocols.db`

## 2026-04-23 — Read-Only Audit of Cross-Run Skill and Protocol Artifacts

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `7/10`
- `confidence`: `high`
- `scope`: `Audit the quality and effective usage of persistent skills/protocols during the live final campaign without perturbing running containers`

### Outcome
The live campaign is persisting cross-run artifacts correctly, but the audit surfaced one major functional gap and two quality issues in the current skill/protocol loop. First, persistent `skill_markers` are recalled into `Decision` and copied into runtime marker payloads, yet the `think` tool only reads `lesson_markers` and the lesson-credit path also ignores `skill_markers`, so the promoted skills currently behave more like archived metadata than reusable runtime guidance. Second, promoted `skill_text` is usually copied from raw objective fragments and then merged by "keep the longest text", which makes the stored skills query-specific and verbose instead of distilled, reusable heuristics. Third, protocol persistence stores raw `latest` adaptations while clamping only happens on re-application, so the persisted `latest` payload can drift far beyond the actual bounded configuration that a future run will consume.

### Reusable Patterns (1-3)
1. For a cross-run memory feature, verify the full loop end to end: recall, prompt injection, success credit, and persistence update; storage-only validation is not enough.
2. When promoting lessons into reusable skills, distill to short generalized advice before persistence; copying full objective text creates prompt noise and weak transfer.
3. If runtime adaptations are clamped on read, store the clamped payload as well or persist both raw and applied values explicitly to keep offline analysis honest.

### Evidence
- `core/agent.py`
- `core/environment.py`
- `tools/think.py`
- `main.py`
- `campaign_results/gemma-stigmergie/pheromones/skills.db`
- `campaign_results/gemma-stigmergie/pheromones/protocols.db`

## 2026-04-24 — Final Campaign Result Audit Finds Empty-Plan C3 False Positives

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `10/10`
- `confidence`: `high`
- `scope`: `Analyze current final campaign outputs, distinguish complete baselines from in-progress baselines, and validate whether C3 final-pass rates correspond to delivered TravelPlanner plans`

### Outcome
The completed Gemma/DeepSeek C3 validation folders contain 180 files each, but their raw `evaluation.final_pass_rate` values are not scientifically usable as success rates. All 360 stigmergic C3 summaries lack a top-level structured `final_plan`; `assistant_response` is `No travel plan generated.` for 178/180 Gemma C3 files and 105/180 DeepSeek C3 files. The raw evaluator still marks 18 Gemma C3 and 105 DeepSeek C3 cases as `final_pass=True`, which are empty-plan false positives caused by per-query evaluation of empty plans. A stricter artifact-aware reading gives C3 strict successful delivered plans of 0/180 for both Gemma and DeepSeek. The Gemma baselines remain interpretable: `solo_self_refine` is currently strongest among complete baselines at 109/180, followed by `solo_direct` 101/180, `solo_cot` 100/180, and `planner_executor` 72/180; `metagpt_sequential` and `langgraph_supervisor` are still in progress or not started.

### Reusable Patterns (1-3)
1. For TravelPlanner, never report `final_pass=True` without confirming that a structured final plan or rendered non-empty plan was actually delivered.
2. Separate raw evaluator pass, artifact delivery, and strict delivered-pass metrics in final campaign tables; empty-plan behavior can otherwise inflate C3 results.
3. When a final campaign discovers a scoring-path bug, preserve the completed artifacts but mark the affected arm as invalid for primary success claims until rerun or rescored with artifact-aware semantics.

### Evidence
- `campaign_results/gemma-stigmergie/c3/`
- `campaign_results/deepseek-stigmergie/c3/`
- `campaign_results/gemma-baselines/`
- `adapters/travelplanner/evaluator.py`
- `adapters/travelplanner/adapter.py`
- `scripts/aggregate_campaign_comparison.py`
- `output/final_campaign_live_analysis/aggregates.json`

## 2026-04-24 — C3 Root-Cause Audit Finds Disconnected Cross-Run Learning

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `10/10`
- `confidence`: `high`
- `scope`: `Critically audit why the final C3/skills version underperforms the older Qwen V6 campaign and whether the design choices invalidate the campaign`

### Outcome
The current C3 campaign is best treated as an invalid implementation/campaign assembly rather than evidence against stigmergic orchestration itself. Cross-run protocol learning was not applied during validation because the protocol namespace includes fields that differ between adapt and eval (`llm.model` and `emergence.feedback_loop.enabled`), so Gemma eval looked for `coordination_protocol::travelplanner::b0f70bab` while adapt persisted `coordination_protocol::travelplanner::f36ac546`, and DeepSeek eval looked for `coordination_protocol::travelplanner::499889af` while adapt persisted `coordination_protocol::travelplanner::d6cf4d18`. Gemma adapt also used the default `qwen/qwen3.5-9b` model because `config/travelplanner_adapt_scientific.yaml` lacks an `llm.model` override. The promoted skills are operationally weak: only five skills were stored, their texts are copied raw objective fragments with `quality_score=1.0`, and the active prompt path recalls skills into `Decision` but does not convert them into actionable planning context. Finally, `agents.protocol_compiler.enabled` is false in the relevant C3 configs, so the objective-conditioned compiler was not actually part of the final C3 test.

### Reusable Patterns (1-3)
1. Treat cross-run learning as untested unless adapt and eval share an explicit persisted namespace or the run summary proves `coordination_protocol_applied=True`.
2. Validate model identity separately for train/adapt and eval configs; inherited defaults can silently train the wrong model while filenames imply otherwise.
3. Require promoted skills to be distilled, consumed by the action prompt, and credited on reuse before claiming skill accumulation as an experimental mechanism.

### Evidence
- `main.py`
- `core/agent.py`
- `tools/think.py`
- `core/environment.py`
- `config/travelplanner_adapt_scientific.yaml`
- `config/travelplanner_eval_c3_gemma.yaml`
- `config/travelplanner_adapt_scientific_deepseek.yaml`
- `config/travelplanner_eval_c3_deepseek.yaml`
- `campaign_results/gemma-stigmergie/pheromones/skills.db`
- `campaign_results/gemma-stigmergie/pheromones/protocols.db`
- `campaign_results/deepseek-stigmergie/pheromones/skills.db`
- `campaign_results/deepseek-stigmergie/pheromones/protocols.db`

## 2026-04-24 — C3 Refactor Implements Artifact-Aware Measurement and Isolated Rerun Controls

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `10/10`
- `confidence`: `high`
- `scope`: `Implement the C3 refactor plan so V6 clean and C3 ablations can be rerun with strict delivered-plan metrics, explicit protocol namespaces, prompt-visible skills, and campaign preflight manifests`

### Outcome
The TravelPlanner measurement path now treats `strict_final_pass = raw_final_pass and artifact_delivered` as the primary pass signal across the official wrapper, adapter summaries, query exports, run summaries, and campaign aggregation. Empty plans cannot pass, raw and strict metrics are exported separately, and summaries expose `final_plan`, `artifact_delivered`, `failure_reason`, protocol namespace/load/apply status, and skill load/injection counters. Protocol reuse now prefers explicit `protocol.namespace`, Gemma adapt/eval configs pin the intended provider/model, skills are injected into `PlanDayTool` as short reusable planning cards, and skill promotion is gated by `strict_final_pass=True` with raw objective/pattern fragments rejected. A new Python C3 campaign runner replaces fragile shell loops with config/API/namespace/compiler preflight, isolated SQLite stores, per-query logs, JSON extraction, manifests, and strict benchmark summaries.

### Reusable Patterns (1-3)
1. Make artifact delivery a first-class field in benchmark summaries, not an inference applied only after aggregation.
2. For cross-run memory experiments, require explicit namespace, preflighted effective config, and prompt-level evidence that retrieved memory was actually injected.
3. Gate persistent skill promotion on strict task success and normalize stored skills into short transferable guidance before reuse.

### Evidence
- `adapters/travelplanner/official_eval.py`
- `adapters/travelplanner/adapter.py`
- `adapters/travelplanner/tools.py`
- `core/environment.py`
- `main.py`
- `scripts/run_travelplanner_c3_refactor_campaign.py`
- `scripts/aggregate_campaign_comparison.py`
- `config/travelplanner_v6_clean_gemma.yaml`
- `config/travelplanner_c3_full_eval_gemma.yaml`

## 2026-04-24 — Gemma Baseline Completion Audit Finds Silent Empty Query Artifacts

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `8/10`
- `confidence`: `high`
- `scope`: `Audit completed Gemma baseline folders before using them as comparison evidence, with special attention to the LangGraph supervisor environment and empty-output behavior`

### Outcome
The old Gemma baseline campaign did not produce 180 valid JSON artifacts for every framework despite file counts showing 180/180. `langgraph_supervisor` has 171 valid JSON files and 9 empty files at query indices 0-7 and 10; valid LangGraph outputs show real `openrouter` / `google/gemma-4-31b-it` execution with LangGraph step traces, so the framework environment was available for successful runs. Other silent empty artifacts exist as well: `solo_direct` query 62, `solo_cot` query 0, and `metagpt_sequential` queries 162-179. The root operational issue is the legacy baseline shell loop redirecting stderr to `/dev/null` and ignoring non-zero exits, which turns crashes into zero-byte `query_*.json` files.

### Reusable Patterns (1-3)
1. Treat benchmark completion as `valid JSON count`, not `file count`, whenever shell redirection or `|| true` is present.
2. Do not suppress stderr for publication-grade per-query baselines; persist one log per query so API/env/import failures remain diagnosable.
3. If empty artifacts remain in an old campaign, either count them as full-denominator failures or rerun only those query indices with a log-preserving runner before citing the arm.

### Evidence
- `campaign_results/gemma-baselines/langgraph_supervisor/`
- `campaign_results/gemma-baselines/metagpt_sequential/`
- `scripts/run_gemma_baselines_docker.sh`
- `scripts/run_travelplanner_langgraph_query_export.py`

## 2026-04-24 — C3 Smoke Test Separates API Recovery From Compiler Failure

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `9/10`
- `confidence`: `high`
- `scope`: `Inspect the rerun C3 smoke after OpenRouter quota recovery and decide whether V6 clean can proceed`

### Outcome
After the OpenRouter key limit was lifted, the C3 smoke consumed real tokens, confirming that the API path is active. The remaining failure is not quota-related: `full_c3` still delivered 0/5 plans, mostly with `protocol_compiler.used=true`, only 4-6 runtime markers, `query_idx` missing in runtime summaries, and `empty_plan_from_llm`. This indicates the current objective-conditioned compiler can produce a formally accepted but operationally weak protocol that starves the TravelPlanner execution graph. The clean V6 preset is not affected because it disables `skill_library`, `protocol`, `cross_run`, and `protocol_compiler`, but compiler-only/full-C3 should not be launched publication-grade until the compiler contract is strengthened. The C3 runner was patched to force the requested `query_idx` into every per-query artifact even when the runtime summary omits it.

### Reusable Patterns (1-3)
1. Distinguish API-path recovery from mechanism validity: nonzero token spend proves provider access, not that a compiled coordination graph is executable.
2. A protocol compiler guard must validate operational TravelPlanner markers, not only action names and coarse stage coverage.
3. Campaign runners should force requested query identity into artifacts so failed or malformed runtime summaries remain official-scorer addressable.

### Evidence
- `campaign_results/smoke_gemma_c3_refactor/benchmark_summary.json`
- `campaign_results/smoke_gemma_c3_refactor/c3/`
- `scripts/run_travelplanner_c3_refactor_campaign.py`
- `config/travelplanner_v6_clean_gemma.yaml`

## 2026-04-25 — V6 Clean Smoke Reveals Empty Finalize Export Bug

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `9/10`
- `confidence`: `high`
- `scope`: `Diagnose why V6 clean Gemma smoke reported 10/10 empty plans despite internal evaluation showing delivered valid plans`

### Outcome
The V6 clean smoke was not a model/runtime failure. Per-query artifacts had top-level `final_plan=[]`, but their internal `evaluation.query_results` showed delivered strict passes. Root cause was the export summary path stopping at an empty `::finalize` marker and never falling back to valid `plan` payloads on plan/validation markers. The extractor now scans beyond empty finalize markers, recovers valid plan-marker artifacts, and the query exporter reuses the corrected summary contract. A real Gemma Q0 control rerun changed from `empty_plan_from_llm` to `artifact_delivered=true`, `strict_final_pass=true`, and a 3-day final plan.

### Reusable Patterns (1-3)
1. When internal eval and top-level artifact fields disagree, inspect export extraction before blaming the LLM or orchestration runtime.
2. Empty terminal/finalize markers must not mask valid intermediate artifacts in benchmark exporters.
3. Add a one-query real-provider control after export-path fixes before relaunching a smoke or full campaign.

### Evidence
- `main.py`
- `scripts/run_travelplanner_query_export.py`
- `tests/unit/test_main_summary.py`
- `campaign_results/v6_clean_gemma_seed42_exportfix2_q0/queries/query_000.json`

## 2026-04-25 — V6 Clean Gemma Docker Campaign Completes Near Solo Baseline

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `9/10`
- `confidence`: `high`
- `scope`: `Read the completed Docker V6 clean Gemma campaign and compare it against existing Gemma baselines under strict delivered-pass semantics`

### Outcome
The V6 clean Gemma Docker campaign completed all 180 validation queries with valid JSON artifacts. It delivered 178/180 non-empty plans and achieved 99/180 strict final passes (`final_pass_rate=0.55`) with 5.45M tokens and $0.8495 cost. Against existing Gemma baselines counted over the same 180-query denominator, V6 clean is slightly behind `solo_direct` (101/180), `solo_cot` (100/180), and `solo_self_refine` (109/180), but ahead of heavier orchestration baselines such as `planner_executor` (72/180), `metagpt_sequential` (79/180 with 18 empty artifacts), and `langgraph_supervisor` (53/180 with 9 empty artifacts). V6 wins over solo_direct on 10 paired queries but loses on 12, so it does not justify its extra token/runtime cost as a global TravelPlanner improvement.

### Reusable Patterns (1-3)
1. Report V6 clean as a valid controlled baseline, not a positive performance claim, when it matches but does not beat solo baselines at higher cost.
2. Use paired win/loss counts alongside aggregate pass rates to avoid overstating small score differences.
3. For TravelPlanner, separate artifact delivery success from strict constraint success; V6 can deliver plans reliably while still failing validation repair.

### Evidence
- `campaign_results/v6_clean_gemma_seed42_docker/benchmark_summary.json`
- `campaign_results/v6_clean_gemma_seed42_docker/queries/`
- `campaign_results/gemma-baselines/solo_direct/`
- `campaign_results/gemma-baselines/solo_self_refine/`

## 2026-04-26 — MigrationBench Becomes the Primary Post-TravelPlanner Scientific Plan

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `9/10`
- `confidence`: `high`
- `scope`: `Create a publication-grade roadmap for moving the framework evaluation from TravelPlanner to repository-level code migration`

### Outcome
The new plan treats TravelPlanner as a controlled negative or secondary result and makes MigrationBench the primary benchmark for evaluating the framework's real potential. The plan prioritizes official execution-based scoring, strong baselines (`no_change`, deterministic dependency-only, solo, planner-executor, agentless self-debug), Docker-first campaign execution, paired statistical analysis, and explicit C3 ablations only after the V6 migration adapter is stable. It also reframes C3 as a mechanism to be tested through isolated protocol, skills, and compiler arms rather than assumed as a full-system win.

### Reusable Patterns (1-3)
1. Move to external execution-based benchmarks when the current benchmark does not expose enough coordination surface for the claimed framework mechanism.
2. Treat agentless/self-debug baselines as mandatory for software-engineering agent claims, because simple pipelines can outperform complex orchestration.
3. Pre-register subsets, metrics, budgets, and failure semantics before launching expensive code-migration campaigns.

### Evidence
- `documentation/redisgn_v2/plan_migrationbench_scientific_campaign.md`

## 2026-04-26 — V7 Elastic Colony Supersedes Integrated C3 as the Next Architecture Track

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `9/10`
- `confidence`: `high`
- `scope`: `Audit current runtime rigidity and update the MigrationBench plan with dynamic ticks, elastic agents, progressive decomposition, and visible specialization`

### Outcome
The current runtime already has useful seeds for adaptation, including dynamic idle extension, emergence metrics, feedback-loop adjustments, and per-agent affinity profiles. However, ticks still depend on a fixed `max_ticks` hard loop, agents are created once from fixed `agents.num_agents`, and decomposition remains bounded by a static `max_depth`. The plan now freezes integrated C3 as the primary architecture path and introduces `V7 Elastic Colony` as the next mechanism track, with isolated ablations for dynamic ticks, elastic agent pools, progressive atomic decomposition, and visible specialization before any full combination or reintroduction of skills/protocol/compiler mechanisms.

### Reusable Patterns (1-3)
1. Keep hard runtime caps as safety guards, but evaluate agent systems through adaptive budget policies that can explain why they continued or stopped.
2. Treat population size as an experimental mechanism, not a constant, when the task graph exposes variable parallelism.
3. Avoid full-stack mechanism bundles after a failed integration; rebuild through isolated ablations that each change one control surface.

### Evidence
- `core/orchestrator.py`
- `core/agent.py`
- `tools/decompose.py`
- `documentation/redisgn_v2/plan_migrationbench_scientific_campaign.md`

## 2026-04-27 — Publish Deep Research Brief for GitHub-Connected ChatGPT

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `8/10`
- `confidence`: `high`
- `scope`: `Prepare and publish a documentation-only research packet so an external GitHub-connected ChatGPT Deep Research run can inspect the right repository context`

### Outcome
A dedicated Deep Research brief was added and pushed with the MigrationBench scientific plan on branch `codex/t0-travelplanner-multi-city`. The commit intentionally stages only the two documentation files needed for external review, leaving the dirty local implementation worktree untouched. The brief tells the external agent which files to inspect, what architectural failures to critique, and what deliverables to produce for improving the V7 Elastic Colony and MigrationBench evaluation plan.

### Reusable Patterns (1-3)
1. For external AI research with repository access, publish a small documentation-only context packet instead of asking the agent to infer priorities from a large dirty worktree.
2. Include branch name and ordered file-reading instructions so GitHub-connected tools do not accidentally inspect stale default-branch context.
3. Stage only the minimal research files when pushing context from a dirty experimental branch.

### Evidence
- `documentation/redisgn_v2/deep_research_brief_for_chatgpt.md`
- `documentation/redisgn_v2/plan_migrationbench_scientific_campaign.md`
- Git commit `1bb2447`

## 2026-04-27 — Integrate External Deep Research Into MigrationBench Plan

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `9/10`
- `confidence`: `high`
- `scope`: `Read the downloaded Deep Research report and turn its critical recommendations into concrete MigrationBench/V7 roadmap constraints`

### Outcome
The external report confirmed the MigrationBench and V7 direction but tightened the proof standard. The plan now states that MigrationBench supports a code-migration claim, not universal agentic superiority; V6 static migration must come before V7; `agentless_self_debug` is mandatory; cross-run adaptation is forbidden on the main evaluation split; `compute_protocol_score` is demoted to telemetry; and elastic agents require hysteresis/cooldown before any full V7 combination. A separate integration note captures the adopted decisions and action items.

### Reusable Patterns (1-3)
1. Treat external AI research as a decision-hardening pass: integrate only recommendations that change gates, claims, metrics, or implementation order.
2. Distinguish benchmark-specific claims from general framework claims to avoid overextending external validity.
3. Demote opaque scalar self-optimization scores to telemetry unless they are validated against external outcomes and disjoint splits.

### Evidence
- `/Users/lotfi/Downloads/deep-research-report.md`
- `documentation/redisgn_v2/deep_research_report_integration.md`
- `documentation/redisgn_v2/plan_migrationbench_scientific_campaign.md`

## 2026-04-27 — Interpret From-Scratch Architecture Critique

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `8/10`
- `confidence`: `high`
- `scope`: `Read the second Deep Research report asking what should be redesigned from scratch and extract the architectural implication`

### Outcome
The second report reframes the project from an agent-first architecture to a benchmark-first, evaluator-first, patch-first system. It does not reject stigmergy or V7, but argues that the scientific core should be a strict campaign/evaluator harness with strong baselines before adaptive colony mechanisms. The key architectural takeaway is to separate domain adapter, colony controller, official evaluator, artifact store, and offline knowledge plane so skills/protocol/compiler cannot silently contaminate the evaluation path.

### Reusable Patterns (1-3)
1. For scientific agent frameworks, build the evaluator and artifact contract before adding adaptive intelligence.
2. Treat cross-run learning as an offline knowledge plane with explicit train/eval split boundaries, not as implicit runtime mutation.
3. Make new runtime mechanisms ablation-native from the start, so every adaptive control surface can be tested alone.

### Evidence
- `/Users/lotfi/Downloads/deep-research-report (2).md`
- `documentation/redisgn_v2/plan_migrationbench_scientific_campaign.md`

## 2026-04-27 — Create MigrationBench Implementation Handoff

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `9/10`
- `confidence`: `high`
- `scope`: `Update the master plan with evaluator-first architecture guidance and create a short implementation handoff for another agent`

### Outcome
The master plan now includes a "from scratch" evaluator-first, patch-first section that separates campaign runner, instance registry, domain adapter, sandbox, colony controller, scheduler, official evaluator, artifact store, offline analysis, and knowledge plane responsibilities. A concise implementation handoff was added so another agent can begin with MigrationBench preflight, adapter scaffolding, mandatory baselines, strict output contracts, and static V6 guardrails before attempting V7 or C3 mechanisms.

### Reusable Patterns (1-3)
1. Pair long scientific plans with a shorter implementation handoff so execution agents can act without losing the research constraints.
2. Encode "do not do yet" items alongside "files to create" to prevent premature full-architecture implementation.
3. Make the first implementation definition of done about valid artifacts and evaluator integration, not performance wins.

### Evidence
- `documentation/redisgn_v2/plan_migrationbench_scientific_campaign.md`
- `documentation/redisgn_v2/migrationbench_implementation_handoff.md`

## 2026-04-27 — Harden MigrationBench Main30 Plan Before Implementation

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `10/10`
- `confidence`: `high`
- `scope`: `Incorporate critical agent feedback before attempting a two-day MigrationBench main_30 campaign`

### Outcome
The MigrationBench plan and implementation handoff now switch the primary model to DeepSeek direct API `deepseek-v4-flash`, add a power-analysis warning that `main_30` is directional rather than proof of small effects, require official MigrationBench/JavaMigration preflight before adapter work, prioritize official SD-Feedback over a naive local agentless reimplementation, standardize `repo_url`, require clean workspace isolation and patch reapplication checks, forbid raw LLM-generated unified diffs, make the aggregator manifest-driven, and clarify that `stigmergic_v6_static` still means marker-store + dependency frontier + local sensing + pressure/ACO scheduling without C3/V7 mechanisms.

### Reusable Patterns (1-3)
1. Treat small benchmark campaigns as directional evidence unless power/discordance supports stronger claims.
2. Prefer running the official reference baseline before implementing a lookalike baseline that could become a strawman.
3. For patch benchmarks, let the harness compute diffs from concrete edits and verify them on a clean checkout before official evaluation.

### Evidence
- `documentation/redisgn_v2/plan_migrationbench_scientific_campaign.md`
- `documentation/redisgn_v2/migrationbench_implementation_handoff.md`
- DeepSeek pricing/model docs
- `amazon-science/JavaMigration`

## 2026-04-28 — Review AI Learning CFP Draft

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `5/10`
- `confidence`: `high`
- `scope`: `Assess documentation/cfp_ailearning2026 submission draft, EasyChair checklist, and bibliography without editing the submission text`

### Outcome
The CFP package is submission-ready in structure and well aligned with the AI&Learning2026 axis on organizational learning, exploration, exploitation, and hybridization. The main remaining risk is rhetorical overclaiming: phrases such as "inédit", "ne peut être résolue que", and broad AI Act alignment should be softened so the conceptual contribution stays credible and defensible.

### Reusable Patterns (1-3)
1. In short CFP submissions, prefer one sharp conceptual contribution over many adjacent theoretical mappings.
2. Keep legal/governance references conditional when the artifact is not explicitly framed as a high-risk AI system.
3. Replace novelty-heavy wording with contribution-specific wording when the paper is conceptual and pre-empirical.

### Evidence
- `documentation/cfp_ailearning2026/abstract_etendu.md`
- `documentation/cfp_ailearning2026/submission_easychair.md`
- `documentation/cfp_ailearning2026/references.bib`

## 2026-04-27 — Frame CFP Submission Around Stigmergic Organizational Learning

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `6/10`
- `confidence`: `high`
- `scope`: `Develop a submission angle for AI&Learning2026 around persistent markers as a hybrid organizational learning medium`

### Outcome
The strongest framing is to present persistent stigmergic markers as an externalized collective memory for AI-agent organizations. The angle maps directly to the CFP theme on organizational learning with AI, exploration, exploitation, and hybridization, while also connecting to epistemic legitimacy, human-AI responsibility, and governance.

### Reusable Patterns (1-3)
1. For management-oriented CFPs, translate system mechanisms into organizational learning constructs before presenting technical details.
2. Use Yan et al. (2026) as the bridge from exploration/exploitation tensions to hybrid human-AI learning governance.
3. Frame markers as traceable learning artifacts with lifecycle controls: deposition, reinforcement, decay, inhibition, audit, and human oversight.

### Evidence
- `/Users/lotfi/Downloads/CFP_IA & Learning.pdf`
- `https://easychair.org/cfp/AI-Learning-2026`
- `https://doi.org/10.1016/j.ijinfomgt.2025.102997`

## 2026-04-27 — Verify And Patch MigrationBench Guardrail Feedback

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `9/10`
- `confidence`: `high`
- `scope`: `Verify external agent feedback about runaway instance limits, edit schema ambiguity, SD-Feedback fallback criteria, stale plan fragments, and DeepSeek client readiness`

### Outcome
The feedback was mostly correct. The plan still contained stale `github_url`, Gemma/OpenRouter, and `v6_clean` fragments; the handoff lacked deterministic per-instance kill switches, a concrete typed edit schema, and a timebox for official SD-Feedback. The local DeepSeek client also lacked `deepseek-v4-flash` pricing and did not translate `reasoning.mode: non-thinking` into DeepSeek's official thinking toggle. The docs and client were updated, and targeted LLM client tests passed.

### Reusable Patterns (1-3)
1. Pair "max model tokens" with deterministic per-instance campaign limits so high-capability models cannot create runaway repair loops.
2. Standardize edit primitives across all LLM arms before benchmarking; otherwise patch validity becomes a hidden treatment variable.
3. Verify provider-specific reasoning controls in the actual client code, not just in YAML plans.

### Evidence
- `documentation/redisgn_v2/plan_migrationbench_scientific_campaign.md`
- `documentation/redisgn_v2/migrationbench_implementation_handoff.md`
- `llm/client.py`
- `tests/unit/test_llm_client_deepseek.py`
- DeepSeek official pricing and thinking-mode docs

## 2026-04-27 — Relax Main30 Hard Caps To Monitor-Only

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `7/10`
- `confidence`: `high`
- `scope`: `Adjust MigrationBench main_30 controls after deciding not to cap high-budget DeepSeek runs per instance`

### Outcome
The MigrationBench handoff and master plan no longer require hard per-instance caps for tokens, runtime, LLM calls, or repair cycles during `main_30`. They now specify `monitor_only` execution with manual abort support and mandatory telemetry for tokens, cost, runtime, calls, repair cycles, last progress time, and abort reason. This preserves room for stigmergic repair behavior while keeping the results auditable.

### Reusable Patterns (1-3)
1. When deliberately removing campaign hard caps, replace them with explicit monitor-only semantics rather than silence.
2. Manual aborts must remain full-denominator failures unless rerun cleanly from checkpoint.
3. High-token stigmergic runs should be judged with cost/runtime Pareto metrics instead of being preemptively capped.

### Evidence
- `documentation/redisgn_v2/plan_migrationbench_scientific_campaign.md`
- `documentation/redisgn_v2/migrationbench_implementation_handoff.md`

## 2026-04-27 — Implement MigrationBench Patch-First Harness

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `10/10`
- `confidence`: `high`
- `scope`: `Create the first executable MigrationBench evaluation track from the implementation handoff`

### Outcome
The repository now has a MigrationBench adapter package with typed benchmark instances, typed edit primitives, clean workspace checkout, harness-computed patches, patch reapplication verification on a second checkout, an official MigrationBench evaluator wrapper, deterministic and LLM baselines, a V6 static stigmergic adapter path, official preflight tooling, manifest-driven runners, manifest-driven aggregation, DeepSeek V4 Flash config, registered official selected subsets, Docker services with Java 17/Maven support, and targeted tests for patch validity, empty-patch failure, denominator preservation, and query export behavior.

### Reusable Patterns (1-3)
1. For execution-based patch benchmarks, implement workspace isolation and patch applicability before optimizing prompts or runtime behavior.
2. Keep official preflight separate from adapter scoring so setup mortality is measured before framework claims.
3. Make every framework arm emit one shared output contract so aggregators can synthesize missing rows without framework-specific exceptions.

### Evidence
- `adapters/migrationbench/`
- `scripts/run_migrationbench_official_preflight.py`
- `scripts/run_migrationbench_query_export.py`
- `scripts/run_migrationbench_framework_benchmark.py`
- `scripts/aggregate_migrationbench_comparison.py`
- `fixtures/migrationbench/subsets/main_30.jsonl`
- `Dockerfile`
- `docker-compose.campaign.yml`
- `tests/unit/test_migrationbench_workspace.py`
- `tests/integration/test_migrationbench_toy_repo.py`

## 2026-04-28 — Fix MigrationBench Compose Preflight Invocation

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `7/10`
- `confidence`: `high`
- `scope`: `Repair Docker Compose command wiring for MigrationBench preflight and campaign services`

### Outcome
The MigrationBench preflight service no longer drops script arguments at startup. The Compose services now use exec-form `bash` commands with literal command blocks, escaped container-side environment variables, and explicit `/opt/venv/bin/python` calls so login-shell PATH resets cannot bypass installed dependencies.

### Reusable Patterns (1-3)
1. For Docker Compose campaign services, avoid folded shell commands when passing multi-line Python arguments.
2. Escape container-side environment variables with `$$` in Compose command blocks.
3. Validate command wiring with a zero-limit smoke before launching a benchmark preflight or campaign.

### Evidence
- `docker-compose.campaign.yml`
- `PREFLIGHT_LIMIT=0 docker compose -f docker-compose.campaign.yml up --force-recreate migrationbench-preflight`

## 2026-04-28 — Fix MigrationBench Official Evaluator Preflight Environment

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `8/10`
- `confidence`: `high`
- `scope`: `Make MigrationBench official evaluator execution scientifically interpretable in Docker preflight`

### Outcome
The official MigrationBench evaluator now receives its package path through `PYTHONPATH`, the Docker image includes the evaluator's missing Python dependencies, and the preflight summary separates evaluator process health from expected unmigrated-base success. A one-instance Docker smoke now reports `official_eval_process_ok=1`, `failure_reasons.ok=1`, and `setup_failure_rate=0.0`.

### Reusable Patterns (1-3)
1. Distinguish evaluator execution health from benchmark task success in preflight summaries.
2. Install official benchmark dependencies explicitly instead of assuming the project requirements cover them.
3. Treat unmigrated baseline failure as diagnostic when the final benchmark contract expects a migrated artifact.

### Evidence
- `scripts/run_migrationbench_official_preflight.py`
- `adapters/migrationbench/evaluator.py`
- `adapters/migrationbench/workspace.py`
- `requirements.txt`
- `PREFLIGHT_LIMIT=1 docker compose -f docker-compose.campaign.yml up --force-recreate migrationbench-preflight`

## 2026-04-28 — Validate MigrationBench Docker Smoke Path

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `8/10`
- `confidence`: `high`
- `scope`: `Run deterministic and LLM smoke checks for MigrationBench campaign services after Docker bind-mount failure`

### Outcome
The MigrationBench campaign service no longer bind-mounts repository source/config folders from macOS, avoiding `Errno 35 Resource deadlock avoided` when reading YAML inside Docker. Smoke runs passed for `no_change` and `dependency_only_script` on `smoke_5`, and for `solo_direct` plus `stigmergic_v6_static` on `smoke_1`. The LLM arms delivered patches, verified patch applicability, recorded token/cost telemetry, and invoked official evaluation.

### Reusable Patterns (1-3)
1. For Docker Desktop campaign runs, prefer immutable code copied into the image over source/config bind mounts when filesystem locking errors appear.
2. Use a `smoke_1` subset for LLM and stigmergic path validation before running expensive multi-framework subsets.
3. Validate pipeline health with delivery, patch applicability, official evaluator invocation, and telemetry capture before interpreting success rates.

### Evidence
- `docker-compose.campaign.yml`
- `fixtures/migrationbench/subsets/smoke_1.jsonl`
- `campaign_results/migrationbench/main/no_change/benchmark_summary.json`
- `campaign_results/migrationbench/main/dependency_only_script/benchmark_summary.json`
- `campaign_results/migrationbench/main/solo_direct/benchmark_summary.json`
- `campaign_results/migrationbench/main/stigmergic_v6_static/benchmark_summary.json`

## 2026-04-29 — Force Clean MigrationBench Workspaces For Docker Campaigns

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `9/10`
- `confidence`: `high`
- `scope`: `Prevent stale workspace contamination in MigrationBench Docker campaigns`

### Outcome
The first `main_30_clean` launch showed a contaminated `no_change` summary: all rows failed as `empty_patch`, but one row still reported an artifact, indicating a dirty pre-existing workspace. The campaign was stopped, `MIGRATION_FORCE=true` was added as the Docker default, and a clean `no_change` smoke now reports `artifact_delivery_rate=0.0` and `empty_patch=1/1` as expected.

### Reusable Patterns (1-3)
1. Treat any `no_change` artifact delivery as a hard contamination signal in patch benchmarks.
2. Force-clean workspaces for publication-grade campaign launches unless explicitly resuming a known-clean checkpoint.
3. Keep aborted contaminated result folders separate from clean reruns rather than aggregating them.

### Evidence
- `docker-compose.campaign.yml`
- `campaign_results/migrationbench/main_30_clean/no_change/benchmark_summary.json`
- `campaign_results/migrationbench/smoke_force_check/no_change/benchmark_summary.json`

## 2026-04-29 — Make MigrationBench No-Change Baseline Explicitly Empty

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `9/10`
- `confidence`: `high`
- `scope`: `Fix no-change baseline artifact delivery semantics for MigrationBench main_30`

### Outcome
The `no_change` baseline no longer exports `git diff` from a checkout, because one repository produced a parasite diff despite no intended migration. It now writes an explicit empty `patch.diff` and constructs `PatchStats(patch_delivered=False)`. Smoke validation on the offending PacktPublishing instance and on all `main_30` instances now reports `artifact_delivery_rate=0.0` with `empty_patch` for every row.

### Reusable Patterns (1-3)
1. A no-op baseline should emit an explicit no-op artifact rather than inferring no-op status from workspace diff state.
2. Validate no-op baselines on the full denominator before using them as scientific controls.
3. If failure reason and artifact metrics disagree, stop the campaign and fix the output contract before interpreting any downstream arm.

### Evidence
- `adapters/migrationbench/scientific_baselines.py`
- `fixtures/migrationbench/subsets/smoke_packt.jsonl`
- `campaign_results/migrationbench/smoke_nochange_packt_fix/no_change/benchmark_summary.json`
- `campaign_results/migrationbench/smoke_nochange_main30_fix/no_change/benchmark_summary.json`

## 2026-04-29 — Add MigrationBench Per-Instance Timeout Guard

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `9/10`
- `confidence`: `high`
- `scope`: `Stop a stalled MigrationBench solo_direct run and add robust per-instance timeout controls`

### Outcome
The `main_30_clean_v3` campaign was stopped after `solo_direct` stalled for more than 50 minutes on one instance with no CPU/network activity and no per-instance timeout active. The campaign runner now accepts and forwards `--query-timeout-seconds`, Docker exposes `MIGRATION_QUERY_TIMEOUT_SECONDS`, the framework runner kills the exporter process group on timeout, and manifests record the effective timeout. A forced `1s` Docker smoke produced `timeout_after_1s`, and a normal `1800s` smoke completed with patch delivery/applicability intact.

### Reusable Patterns (1-3)
1. Per-instance timeouts must be wired from Compose to campaign runner to framework runner, not just declared in YAML.
2. Timeout handling should kill the whole process group so Maven/official-eval children cannot leak.
3. Choose timeout values from observed benchmark runtimes; a 300s hard cap is too low when legitimate official evals already exceed 600s.

### Evidence
- `scripts/run_migrationbench_campaign.py`
- `scripts/run_migrationbench_framework_benchmark.py`
- `config/migrationbench_v6_static_deepseek.yaml`
- `docker-compose.campaign.yml`
- `campaign_results/migrationbench/main_30_clean_v3/`
- `campaign_results/migrationbench/smoke_timeout_1s/solo_direct/benchmark_summary.json`
- `campaign_results/migrationbench/smoke_timeout_normal/solo_direct/benchmark_summary.json`

## 2026-04-29 — Fix MigrationBench Stigmergic Final Contract Selection

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `9/10`
- `confidence`: `high`
- `scope`: `Audit completed main_30_clean_v4 results and repair stigmergic result extraction`

### Outcome
The completed `main_30_clean_v4` campaign produced valid baseline summaries, but the `stigmergic_v6_static` aggregate was invalid because one instance exported a lesson marker instead of the benchmark final contract. The adapter now requires the final marker to be a `task` marker with `strict_success` in its payload, preventing lesson markers whose IDs also end in `::finalize_patch` from being selected as final results.

### Reusable Patterns (1-3)
1. In marker-based runtimes, final-result extraction must filter by marker type and required contract keys, not only by ID suffix.
2. Treat `recorded_rows > requested_instances` as an immediate export-contract failure.
3. When a result file contains framework memory fields such as `lesson`, rerun that arm after fixing extraction rather than interpreting the aggregate.

### Evidence
- `adapters/migrationbench/adapter.py`
- `tests/unit/test_migrationbench_adapter.py`
- `campaign_results/migrationbench/main_30_clean_v4/stigmergic_v6_static/runs.json`
- `campaign_results/migrationbench/main_30_clean_v4/stigmergic_v6_static/instances/comic__con__museum__fan__forge__backend_artifacts/markers.db`

## 2026-04-29 — Rebuild MigrationBench Image Without Cache

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `7/10`
- `confidence`: `high`
- `scope`: `Clear MigrationBench scratch/cache state and relaunch stigmergic rerun from a no-cache Docker image`

### Outcome
The MigrationBench workspace scratch directory had grown to about 11GB and Docker build cache contained more than 14GB of reclaimable data. The scratch workspace was cleared, Docker build cache was pruned, Python `__pycache__` files in source/runtime folders were removed, `.dockerignore` now excludes `external/` and `workspaces/`, and the `migrationbench-campaign` image was rebuilt with `--no-cache` from a 1.4MB minimal temporary context after Docker Desktop stalled on the full repository context. The corrected `stigmergic_v6_static` rerun was launched in `campaign_results/main_30_stigmergic_fixed_nocache`.

### Reusable Patterns (1-3)
1. Benchmark scratch workspaces should be treated as disposable cache and cleared before reruns that investigate contamination or extraction bugs.
2. Docker image build contexts should exclude mounted benchmark directories such as `workspaces/` and `external/`.
3. If Docker Desktop stalls while loading a repository context, build from a minimal temporary context containing only runtime code, configs, scripts, and fixtures.

### Evidence
- `.dockerignore`
- `workspaces/migrationbench`
- `docker image inspect stigmergiagentic-migrationbench-campaign:latest`
- `campaign_results/migrationbench/main_30_stigmergic_fixed_nocache/stigmergic_v6_static/campaign_manifest.json`

## 2026-04-29 — Triage No-Cache MigrationBench Stigmergic Rerun

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `8/10`
- `confidence`: `high`
- `scope`: `Check completion and scientific validity of the no-cache stigmergic_v6_static rerun`

### Outcome
The no-cache `stigmergic_v6_static` rerun completed with Docker exit code 0 and a valid denominator: 30 requested instances and 30 recorded rows. The run delivered patches for 29/30 instances and 27/30 patches applied on clean checkout, but strict success was 0/30 because all official evaluations failed or pre-evaluation patch checks failed. This is a valid negative result for the arm, not a cache or export-contract failure.

### Reusable Patterns (1-3)
1. Separate execution validity from benchmark success: exit code 0 and full denominator only prove the campaign ran cleanly.
2. For patch benchmarks, inspect delivered, patch-applies, official-success, and strict-success as distinct funnel stages.
3. Treat `official_eval_failed` with `official_eval_returncode=0` as a benchmark failure signal, not a harness crash.

### Evidence
- `campaign_results/migrationbench/main_30_stigmergic_fixed_nocache/stigmergic_v6_static/benchmark_summary.json`
- `campaign_results/migrationbench/main_30_stigmergic_fixed_nocache/stigmergic_v6_static/runs.json`
- `campaign_results/migrationbench/main_30_stigmergic_fixed_nocache/stigmergic_v6_static/official_eval.json`

## 2026-04-30 — Diagnose MigrationBench V6 Static Zero Success

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `9/10`
- `confidence`: `high`
- `scope`: `Explain why the no-cache stigmergic_v6_static run delivered patches but achieved 0/30 strict success`

### Outcome
The run failure is not a cache or denominator issue. The V6 static MigrationBench adapter mostly emits tiny POM-oriented patches, often 1-3 changed lines, then runs build and final evaluation without feeding build failures back into a repair loop. The final marker depends on `propose_patch`, not `run_build`, so build feedback is telemetry rather than a decision input. Several patches are semantically broken, such as property renames without updating all references, while others apply but fail official build/test/class-version criteria.

### Reusable Patterns (1-3)
1. Repository migration agents need a closed repair loop: propose patch, run official-like build/test, classify failure, revise patch, then finalize.
2. Build markers that no downstream marker depends on are telemetry, not control flow.
3. High patch delivery/applicability with zero official success indicates shallow edit quality, not necessarily execution infrastructure failure.

### Evidence
- `adapters/migrationbench/adapter.py`
- `adapters/migrationbench/tools.py`
- `campaign_results/migrationbench/main_30_stigmergic_fixed_nocache/stigmergic_v6_static/instances/realjeeshop__jeeshop_artifacts/artifacts/patch.diff`
- `campaign_results/migrationbench/main_30_stigmergic_fixed_nocache/stigmergic_v6_static/instances/realjeeshop__jeeshop_artifacts/artifacts/official/official_eval.log`

## 2026-04-30 — Implement MigrationBench V7 Repair Colony

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `9/10`
- `confidence`: `high`
- `scope`: `Add a MigrationBench-first V7 adaptive repair-colony arm`

### Outcome
Implemented `stigmergic_v7_repair_colony` as an opt-in MigrationBench arm with branch-isolated patch hypotheses, build-failure classification, repair-marker deposition, official-eval repair feedback, elastic agent-pool resizing, high-cap telemetry, and V7 summary metrics. The new flow no longer finalizes directly from patch proposal; finalization requires a selected evaluated branch and can feed repair markers when the patch or official evaluator fails.

### Reusable Patterns (1-3)
1. Closed-loop benchmark agents should encode external failures as typed repair markers rather than terminal telemetry.
2. Patch-candidate branches let a stigmergic runtime explore and repair alternatives while preserving a clean base checkout.
3. Skip-official-eval smoke mode must not be treated as a repairable official failure.

### Evidence
- `config/migrationbench_v7_repair_colony_deepseek.yaml`
- `adapters/migrationbench/tools.py`
- `core/orchestrator.py`
- `tests/unit/test_migrationbench_v7_repair_colony.py`

## 2026-05-04 — Harden V10 BranchingRepair A3 With Dedup, Repeat-Failure Suppression, And An Explainable Selector

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `8/10`
- `confidence`: `high`
- `scope`: `Phase 5 V10 deliverables on top of Phase 4 MigrationBench harness`

### Outcome
`core_v10/strategy_runner.py` now owns a `_SignatureTracker` (sha256 of canonicalized `kind+payload`), emits `candidate.deduped` / `candidate.repeat_failure_suppressed` / `selection.completed` events, and returns a `SelectionRationale` (selected id, reason, score, ranked competitors). `scripts/bench/telemetry.py` exposes `dedup_skipped_total`, `repeat_failure_suppressed_total`, and per-instance `selection_rationale`, all reconstructible from the EventLog so the live==replay invariant survives. New `scripts/bench/compare_strategies.py` runs A1/A2/A3 ablations on the same JSONL subset and writes `comparison.json`. Suite V10: 136 passed (+10 new tests).

### Reusable Patterns (1-3)
1. Put auditability primitives (signature dedup, repeated-failure suppression, selection rationale) in the strategy runner — every adapter inherits them for free and the EventLog stays the single source of truth.
2. When a summary gains new fields, reconstruct them from raw events as a fallback so legacy campaign trees written before the change keep replaying with `live==replay` parity.
3. An ablation harness should be parametric over `(strategy_name, max_candidates, max_repair_rounds, max_repairs_per_candidate)` rather than hard-coded — this lets future arms (e.g. typed_blackboard, verifier_guided_search) plug in without changing the comparison script.

### Evidence
- `core_v10/strategy_runner.py`
- `scripts/bench/telemetry.py`
- `scripts/bench/compare_strategies.py`
- `tests/unit/v10/test_strategy_runner_phase5.py`
- `tests/unit/v10/bench/test_compare_strategies.py`
- `documentation/decisions/20260504-phase5-a3-branching-repair.md`
- `documentation/redisgn_v2/phase_05_artifact.md`

## 2026-05-04 — Diagnose V10 A1/A2/A3 main_30 Ablation Non-Interpretability

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `9/10`
- `confidence`: `high`
- `scope`: `Interpret the completed Docker A1/A2/A3 MigrationBench main_30 campaign and identify why it cannot yet evaluate the framework contribution.`

### Outcome
The A1/A2/A3 `main_30` campaign validated Docker execution, EventLog replay parity, and Phase 5 telemetry plumbing, but it did not validate the framework contribution. A2 and A3 used the same deterministic single-candidate POM provider as A1 and the repair provider returned no candidates, so A3 never branched and A2 never repaired. The identical results (`0/30` strict success, `5` no-candidate, `23` invalid/repair-exhausted, `2` local-pass but official-fail) are therefore an activation failure of the treatment, not evidence that branching repair is ineffective. The local verifier also over-aborts on `dependency:resolve` compared with MigrationBench's official evaluator behavior, and the official evaluator can reject locally green patches when its stdout-based test-count check returns `-2`.

### Reusable Patterns (1-3)
1. **Ablation arms must emit mechanism-activation evidence before their scores are interpreted**: for branching repair, require multiple candidates or repair candidates, not just `max_candidates > 1` in config.
2. **Separate harness validity from treatment validity**: `exit 0`, full denominator, and live==replay prove execution integrity, not scientific comparability.
3. **Mirror official evaluator semantics before optimizing agents**: local verifier gates must not create false negatives that the official benchmark would evaluate differently.

### Evidence
- `campaign_results/v10/ablation_main30/comparison.json`
- `scripts/bench/providers.py`
- `scripts/bench/compare_strategies.py`
- `adapters_v10/migrationbench/verifier.py`
- `external/MigrationBench/src/migration_bench/eval/final_eval.py`

## 2026-05-05 — Harden V10 MigrationBench Budgeted Ablation Against Workspace Exhaustion

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `8/10`
- `confidence`: `high`
- `scope`: `Stabilize Phase 6 A3/A4 budget=5 campaign relaunch`

### Outcome
The partial budget=5 A3 run crashed at instance 26/30 because branch and `_verify` workspaces accumulated copied Maven build outputs. V10 now skips generated outputs when copying branches, cleans `_verify/<candidate>` immediately after patch-apply checks, removes branch build outputs after validation/finalization, records branch-copy failures as `ApplyResult` failures instead of campaign crashes, and raises Docker `nofile`/`nproc` limits for V10 MigrationBench services. Telemetry now exposes apply and validation status counters so `partial` validations no longer look like missing validation events.

### Reusable Patterns (1-3)
1. Budgeted branch-search campaigns must treat verification checkouts and build outputs as disposable resources, not durable evidence.
2. Final score signals and validation-progress counters should be separate telemetry channels; strict success stays score-derived, while partial progress remains auditable.
3. Infrastructure failures in branch materialization should become typed per-candidate failures whenever possible, preserving campaign denominator and EventLog continuity.

### Evidence
- `adapters_v10/migrationbench/workspace.py`
- `adapters_v10/migrationbench/adapter.py`
- `scripts/bench/telemetry.py`
- `docker-compose.campaign.yml`
- `documentation/redisgn_v2/phase_06_budget5_audit.md`
- `tests/unit/v10`
- `tests/integration/v10`
