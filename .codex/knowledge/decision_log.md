# Decision Log

## 2026-05-04 (Phase 4 V10 — Port MigrationBench To V10 Stack With Verifier-First Contract And EventLog-Derived Telemetry)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Livrer Phase 4 du plan canonique en 7 itérations `/loop` autonomes : `adapters_v10/migrationbench/` complet (workspace isolé, MavenRunner+Verifier émettant 8 signaux canoniques, adapter implémentant `DomainAdapterV10`), `scripts/bench/` unifié (harness CLI, telemetry pure-EventLog, providers déterministes, helpers Docker), service `migrationbench-v10-smoke` dans `docker-compose.campaign.yml`, suite test 121 unit + 5 integration golden. Cloison étanche stricte (`adapters_v10/` n'importe rien de `core/` ni `adapters/`). Invariant : `strict_success` requiert la chaîne complète `apply → mvn dependency+compile+test → class versions == {61} → official run_eval.py Success=True`.
- `rationale`: Le pivot V10 (ADR-018) impose de prouver que la nouvelle pile peut traiter le banc le plus dur (MigrationBench main_30) sans réintroduire les bugs V3/V7 — notamment la divergence télémétrique de 73 points entre `patch_applies` et `artifact_delivery` causée par `_synthesize_best_partial_payload`. Un harness Docker-first avec summary reconstruit depuis l'EventLog (testé `live==replay`) rend cette divergence structurellement impossible : aucune métrique n'existe en dehors du payload `score.completed`, et `strict_success=True` exige que les 8 signaux soient tous True. La validation locale renvoie `PASSED` dès que la chaîne locale (5 signaux) est verte ; `official_success` reste gate par `score()` après `finalize()`. Cette séparation permet à `_finalize_best_validated` d'avancer sans court-circuiter le verifier-first contract.
- `alternatives_rejected`: (a) Recopier le legacy `MigrationBenchAdapter` V3 puis adapter — rejeté car aurait conservé le couplage avec `core/marker_store.py` et la sémantique V7 colony qu'on cherche à abandonner ; (b) faire la `validate()` exécuter aussi l'official evaluator pour pouvoir renvoyer `PASSED` selon la chaîne complète — rejeté car double exécution coûteuse de Maven, et l'official Maven n'est pas reproductible (dépend de Maven Central + dépendances tierces) ; (c) déclencher dès L6 un smoke run réel via Docker + DeepSeek API — rejeté car gate-keeped par les règles d'arrêt du plan (`Coût LLM L6 > 10 USD ⇒ stop`, `Maven indisponible ⇒ stop`), et la pipeline complète peut être validée sans coût via Maven mocké + upstream git local + invariant `live==replay` testé golden.
- `linked_adr`: `documentation/decisions/20260503-pivot-v10-from-scratch.md` (ADR-018)

## 2026-05-03 (Complete V10 Toy Runtime Before Real Benchmark Adapters)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Extend the V10 bootstrap with blackboard projections, typed coordination signals, branching repair, verifier-scored selection, fallback finalization, event-only blackboard reconstruction, and a deterministic toy adapter before connecting MigrationBench or any other real benchmark.
- `rationale`: The previous V7 failures came from mixing benchmark logic with unproven runtime mechanics. A toy adapter lets the framework prove branch lineage, workspace continuity, artifact contracts, replay, feedback, repair, and strict-success gating in a controlled setting where failures are attributable to runtime invariants rather than Maven, model quality, or external scorer behavior.
- `alternatives_rejected`: Connect MigrationBench immediately after the first V10 contracts, keep repairs as sibling branches from the root workspace, allow duplicate candidate IDs, rely only on in-memory graph state for blackboard reconstruction, or finalize only the first locally validated candidate.
- `linked_adr`: `documentation/redisgn_v2/plan_v10_framework_rebuild.md`

## 2026-05-03 (Bootstrap V10 As Isolated Verified Runtime Core)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Start V10 implementation with an isolated `core_v10`/`adapters_v10` runtime containing contracts, EventLog/replay, HypothesisGraph, VerifierLoop, and a minimal agentless StrategyRunner, while leaving the legacy V3/V7 runtime untouched.
- `rationale`: The V10 plan requires a real architectural rupture, and the first executable increment must prove plug-and-play contracts, verifier-gated strict success, replayability, per-run hypothesis state, and branch-workspace continuity before adding MigrationBench logic, blackboards, stigmergic signals, roles, or memory.
- `alternatives_rejected`: Refactor `core/` in place, patch V7.3 again, start with MigrationBench-specific code, reuse the marker store as the first V10 source of truth, or add role-colony machinery before a simple verified workflow passes contract tests.
- `linked_adr`: `documentation/redisgn_v2/plan_v10_framework_rebuild.md`

## 2026-05-03 (Document V10 Pivot in Repo Artifacts — Memoir-Grade Narrative + ADR-018)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Produce a memoir-grade narrative (`documentation/redisgn_v2/pivot_v10_documentation_memoire.md`) and ADR-018 (`documentation/decisions/20260503-pivot-v10-from-scratch.md`) that explicitly trace the path from the invalidated stigmergic-pure hypothesis to the V10 pivot, with H1/H2/H3/H4 hypotheses, ablation ladder A0..A6, and threats-to-validity already declared.
- `rationale`: A scientific master's thesis cannot publish a pivot of this magnitude without a memoir-section narrative explaining the original hypothesis, the empirical invalidation, and the reformulated research question. Without ADR-018, the repository's decision history would skip from Sprint 9 (C1/C2/C3) directly to V10 implementation, leaving the architectural rationale undocumented for future maintainers and thesis defense.
- `alternatives_rejected`: Document the pivot only in the technical canonical plan, document only via `.codex/knowledge/captures.md`, postpone documentation until V10 implementation is complete, or leave Sprint 9 ADR active without explicit deprecation.
- `linked_adr`: `documentation/decisions/20260503-pivot-v10-from-scratch.md`

## 2026-05-03 (Adopt V10 From-Scratch Core Over V3 Cleanup)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Treat `documentation/redisgn_v2/plan_v10_from_scratch_rebuild.md` as the canonical rebuild plan and pursue a new `core_v10` architecture rather than cleaning V3 in place.
- `rationale`: The Claude plan correctly identified the hybrid blackboard plus verifier-loop pivot, but still preserved too much of the V3 marker/orchestrator substrate as the center. A true rupture needs EventLog, HypothesisGraph, typed Blackboard projection, verifier-gated artifacts, and an ablation order that tests stigmergic signals before MCTS-style search.
- `alternatives_rejected`: Continue V7.3, build a V3-cleaned runtime, make Blackboard the source of truth, introduce MCTS before testing stigmergic signals, or patch Sprint 9 textual skills instead of replacing them with verifier-gated memory.
- `linked_adr`: `documentation/redisgn_v2/plan_v10_from_scratch_rebuild.md`

## 2026-05-03 (Plan StigmergiAgentic V10 As Contract-First Verified Runtime)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Treat the next major framework line as V10 / StigmergiAgentic 2.0, centered on plug-and-play adapter contracts, EventLog, Blackboard, HypothesisGraph, strategy runners, structured feedback, replay, and ablation-first evaluation.
- `rationale`: V6/V7 MigrationBench results showed that improving patch delivery and repair mechanics does not automatically produce strict success or causal multi-agent value. A deeper architecture reset is needed so framework logic, domain adapters, validation contracts, stigmergic signals, and memory modes are separately testable.
- `alternatives_rejected`: Continue with V7.3 prompt/repair tweaks, add more agents to the current marker loop, hard-code Maven solvers into core, or claim colony behavior from concurrent agents without hypothesis-level evidence.
- `linked_adr`: `documentation/redisgn_v2/plan_v10_framework_rebuild.md`

## 2026-05-03 (Repair V7.2 Strict-Success Contract Before Further Campaign Claims)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Make V7.2 best-partial finalization export and officially evaluate the selected branch through the common strict contract, and collapse repair retries back to root patch hypotheses instead of recursively repairing repair markers.
- `rationale`: The main_30 readout showed `patch_applies=27/30` but `strict_success=0/30` for V7.2 because most best-partials were marker payloads only, not official-evaluated artifacts. Marker DB inspection also showed runaway `repair::repair::...` chains after empty repair edits, which consumed LLM calls without producing new candidate branches.
- `alternatives_rejected`: Accept V7.2 results as purely model-limited, rerun main_30 with the same code, or keep best-partial as a telemetry-only fallback while comparing it to V6 delivered patches.
- `linked_adr`: `documentation/redisgn_v2/v7_1_diagnostic_loop.md`

## 2026-05-02 (Harden MigrationBench V7.1 Before Any New main_30 Run)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Implement V7.1 as a technical hardening layer for `stigmergic_v7_repair_colony` and require a smoke gate before any new `main_30`, while keeping V6 static and the DeepSeek `deepseek-v4-flash` model unchanged.
- `rationale`: The prior V7 result was not interpretable enough for scientific comparison because schema failures, missing finalization, noisy Maven feedback, lessons pollution, weak telemetry, and stale artifacts could masquerade as benchmark failure. Fixing these mechanics first makes future negative or positive results attributable to the repair-colony behavior rather than harness defects.
- `alternatives_rejected`: Rerun `main_30` immediately, switch to legacy DeepSeek aliases, let compile-only partial patches be selected normally, or treat `reinforcement.enabled=false` as sufficient to disable lessons.
- `linked_adr`: `documentation/redisgn_v2/v7_1_implementation_handoff.md`

## 2026-04-27 (Accept Improved MigrationBench Handoff With Consistency Cleanup)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Accept the improved MigrationBench implementation handoff as substantially ready for execution, but require a short consistency cleanup pass in the long scientific plan before coding starts.
- `rationale`: The handoff now locks the important scientific safeguards: official preflight first, patch/workspace isolation, manifest-driven denominators, query-level exporter, SD-Feedback priority, and V6 static before V7/C3. The remaining risk is stale terminology in the master plan (`github_url`, Gemma-first commands/config names, `v6_clean`) conflicting with the handoff's current DeepSeek/V6-static direction.
- `alternatives_rejected`: Reject the handoff because the long plan still has stale sections, or proceed to implementation without resolving naming/model conflicts that could leak into scripts and configs.
- `linked_adr`: `documentation/redisgn_v2/migrationbench_implementation_handoff.md`

## 2026-04-27 (Keep MigrationBench Handoff V6-Static-First with Preflight Tightening)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Treat the MigrationBench handoff as the correct implementation guide, with a tightened execution emphasis on official evaluator preflight, single instance schema, clean patch workspace isolation, and requested-instance denominator handling before prompt or V7 optimization.
- `rationale`: The handoff correctly avoids repeating the C3 mistake of combining many adaptive mechanisms before the benchmark contract is trustworthy. Its main remaining risk is not direction but operational ambiguity around evaluator setup, schema naming, workspace cleanliness, and missing-output aggregation.
- `alternatives_rejected`: Start with V7 Elastic Colony implementation, repair integrated C3 first, or port TravelPlanner runner/aggregator semantics without strengthening patch and denominator invariants for MigrationBench.
- `linked_adr`: `N/A (implementation handoff review before MigrationBench work)`

## 2026-04-23 (Create a Thesis-Facing Expert Guide for the Framework)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Create `documentation/framework_guide_expert.md` as the canonical pedagogical guide for understanding the StigmergiAgentic framework end to end, and link it from `documentation/README.md`.
- `rationale`: The project has accumulated multiple sprint artifacts, ADRs, configs, adapters, and campaign notes; the memoire needs one coherent document that teaches the framework as a runtime mechanism rather than forcing the reader to reconstruct it from scattered implementation files.
- `alternatives_rejected`: Only update sprint artifacts, only document TravelPlanner, or produce a short architecture summary without runtime diagnostics and extension guidance.
- `linked_adr`: `N/A (documentation consolidation for thesis support)`

## 2026-04-23 (Implement V9 Final Campaign as Train-Adapt and Full-Validation Eval)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Implement the V9 final campaign protocol as TravelPlanner `train[0:45]` adaptation followed by read-only full `validation[0:180]` evaluation, and redefine aggregate `delivery_rate` around official delivery semantics while retaining artifact delivery for diagnostics.
- `rationale`: This turns the previously documented methodology fix into executable defaults, aligns with SwarmAgentic/TravelPlanner validation reporting, prevents stale 90-query outputs from polluting 180-query runs, and avoids claiming C3 evidence when `skills.db` / `protocols.db` remain unwritten.
- `alternatives_rejected`: Keep 90/90 validation slicing, keep C3 adapt cross-run writes disabled, count nested `query_results.delivered` as delivery for no-plan rows, or defer terminal-marker lesson compatibility until after another expensive campaign.
- `linked_adr`: `documentation/decisions/20260421-sprint9-full-implementation-persistent-skills-protocols-and-cross-run-coordination.md`

## 2026-04-23 (Move Sprint 9 Adaptation to TravelPlanner Train and Evaluate on Full Validation)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: For the next final Sprint 9/V9 TravelPlanner campaign, use the published TravelPlanner `train` split for adaptation and evaluate C2/C3/baselines on the full 180-query validation split.
- `rationale`: SwarmAgentic trains on `train_45.jsonl` (sampled to 9 effective examples by default) and evaluates on `validation.jsonl` with 180 queries. The current 90/90 validation split is arbitrary and can leak distribution-level information into persistent artifacts consumed by evaluation.
- `alternatives_rejected`: Keep using `validation[0:90]` for adaptation and `validation[90:180]` for evaluation, or disable `cross_run` while still letting evaluation consume artifacts learned from validation queries.
- `linked_adr`: `documentation/decisions/20260421-sprint9-full-implementation-persistent-skills-protocols-and-cross-run-coordination.md`

## 2026-04-23 (Treat the Current V9 Campaign as Diagnostic Until Persistence Activation Is Verified)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Treat the current V9/Sprint 9 campaign as a diagnostic C3-style runtime comparison, not as final evidence for persistent skill accumulation or cross-run protocol adaptation, until non-empty `skills.db` / `protocols.db` artifacts and protocol application are observed.
- `rationale`: The result files are mostly available, but both persistent stores are empty, `skills_promoted` remains zero, and no C3 row applies a coordination protocol. Additionally, nested `delivered=true` fields overstate delivery for rows with `No travel plan generated` and `evaluated_queries=0`.
- `alternatives_rejected`: Cite the current 90/90 C3 files as final Sprint 9 C2/C3 evidence based only on file completeness, or rerun missing baselines before fixing metric semantics and activation checks.
- `linked_adr`: `documentation/decisions/20260421-sprint9-full-implementation-persistent-skills-protocols-and-cross-run-coordination.md`

## 2026-04-21 (Complete Sprint 9 by Wiring Persistence and Promotion into the Runtime)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Wire the Sprint 9 persistence layer (`skills_store`, `protocol_store`), skill promotion (`_maybe_promote_to_skill`), protocol save/load (`save_protocol_marker`, `load_protocol_marker`), and cross-run adaptation (`_maybe_apply_cross_run_protocol`, `_persist_protocol`) into the existing runtime while preserving Sprint 8 defaults.
- `rationale`: The groundwork (config, schema, prompt, adapter seams) was already landed in ADR 016; the remaining work was the functional core of Sprint 9. Completing it now gives end-to-end test coverage for C1/C2/C3 before the benchmark campaign.
- `alternatives_rejected`: Stop at groundwork and defer persistence wiring to a later sprint, which would leave the thesis claims without executable validation.
- `linked_adr`: `documentation/decisions/20260421-sprint9-full-implementation-persistent-skills-protocols-and-cross-run-coordination.md`

## 2026-04-21 (Prepare Sprint 9 Through Contracts Before Persistence Wiring)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Prepare Sprint 9 by landing opt-in config/schema/prompt/runtime seams for persistent skills, protocol artifacts, and objective-conditioned protocol compilation before wiring the dedicated stores and cross-run write paths.
- `rationale`: The current runtime already provides the necessary substrate primitives, but introducing persistence, protocol learning, and benchmark methodology in one step would make regressions harder to isolate; a contract-first layer keeps Sprint 8 stable while giving Sprint 9 a concrete, testable implementation boundary.
- `alternatives_rejected`: Delay all Sprint 9 work until the full persistence loop is ready, or wire stores/promotions/protocol application immediately without first stabilizing the config and compiler contracts.
- `linked_adr`: `documentation/decisions/20260421-sprint9-groundwork-persistent-skills-protocols-and-compiler.md`

## 2026-04-20 (Approve Revised Sprint 9 Direction with a Narrower C1 Claim)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Treat the revised Sprint 9 direction as architecturally sound and philosophically aligned, provided C1 is defended as objective-conditioned protocol generation over a fixed substrate, while T1 and T2 become the primary mechanisms for validating C2 and C3.
- `rationale`: The revised plan moves self-optimization into persistent stigmergic artifacts, introduces a necessary adapt-vs-eval separation, and avoids the earlier drift toward manual specialist roles; the main residual risk is overclaiming C1 beyond what a fixed tool/evaluator substrate can support.
- `alternatives_rejected`: Keep the previous manual specialist-seeding approach, or postpone cross-run adaptation entirely until a later sprint.
- `linked_adr`: `documentation/decisions/20260418-sprint8-v6-general-runtime-controls.md`

## 2026-04-20 (Constrain Sprint 9 to Protocol Adaptation, Not Manual Specialist Roles)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Treat Sprint 9 as a bounded auto-organization cycle centered on persistent agent state and cross-run coordination feedback, but reject manual domain-specialist seed templates as the main mechanism for validating "from-scratch agent generation".
- `rationale`: Persistent memory and feedback can extend the current stigmergic philosophy without breaking role-freeness if they remain environment-mediated and auditable, while hard-coded transport/accommodation/planning templates in the adapter would weaken both the philosophical claim and the scientific interpretation of C1.
- `alternatives_rejected`: Implement Sprint 9 exactly as proposed with manual specialist templates in the domain adapter, or enable cross-run adaptation directly in the primary evaluation preset without a separate adaptation/frozen-eval protocol.
- `linked_adr`: `documentation/decisions/20260418-sprint8-v6-general-runtime-controls.md`

## 2026-04-19 (Prioritize Targeted Repair After the V6-A Readout)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Prioritize `v6_C` targeted-repair benchmarking before a full `v6_B` stickiness campaign, because the paired-seed V6 readout shows that the dominant residual failure regime has shifted from premature `idle_cycles` collapse toward `all_terminal` but scorer-invalid plans.
- `rationale`: `v6_base` already proved that extending continuation control reduces early stagnation and improves delivery, while `v6_A` improved the quality-efficiency balance of that regime; the clearest remaining gap is not more raw continuity, but the ability to repair terminal-invalid outputs into official-pass plans.
- `alternatives_rejected`: Run stickiness first as the primary next ablation, or keep extending continuation/search behavior without introducing an explicit repair-oriented mechanism.
- `linked_adr`: `documentation/decisions/20260418-sprint8-v6-general-runtime-controls.md`

## 2026-04-17 (V6 Planning Boundary: Improve the Framework, Freeze the Benchmark)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Frame the next improvement cycle as a framework-general V6 plan with a frozen benchmark/scorer boundary, and keep TravelPlanner-specific optimizations explicitly downstream from the framework ablation.
- `rationale`: The latest V5-full validation analysis around the ~21% regime exposed real framework bottlenecks, but article credibility would be weakened immediately if the next cycle mixed core improvements with benchmark or scorer modifications.
- `alternatives_rejected`: Tune the benchmark harness together with the framework, or bundle framework-general and TravelPlanner-specific changes into one opaque improvement preset.
- `linked_adr`: `N/A (review-planning rule for benchmark credibility)`

## 2026-04-17 (Type-Specific Improvement Priority for V5-Full)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Prioritize the next TravelPlanner framework improvements by query regime: strengthen validator-guided repair and constraint-aware candidate filtering for `3-day / 1-city` hard queries, and prioritize anti-stagnation decomposition and multi-city execution continuity for `5-day / 2-city` and `7-day / 3-city` queries.
- `rationale`: The latest ~21% validation runs show that single-city hard queries usually fail with non-empty plans, while multi-city queries mostly fail as empty-plan `idle_cycles` collapses; a single generic optimization pass would blur these distinct bottlenecks.
- `alternatives_rejected`: Optimize only global emergence metrics without query-type stratification, or focus exclusively on multi-city structure while ignoring hard single-city constraint failures.
- `linked_adr`: `N/A (benchmark improvement prioritization rule)`

## 2026-04-17 (Interpretation of V5-Full Emergence Metrics)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Treat `pressure_entropy` and `parallel_utilization` as the main success-side emergence indicators for the current TravelPlanner `v5_full` validation preset, and interpret late `convergence_tick` primarily as stagnation risk unless accompanied by strong parallel utilization.
- `rationale`: Across the latest full validation seeds (`42`, `43`), successful queries consistently showed higher pressure entropy and higher parallel utilization, while failed queries were more often associated with delayed convergence and `idle_cycles`; `collaboration_density` and `colony_specialization` were comparatively weak discriminators.
- `alternatives_rejected`: Use collaboration density as the primary emergence readout, or treat later convergence as automatically beneficial exploration without checking runtime utilization.
- `linked_adr`: `N/A (post-hoc benchmark interpretation rule)`

## 2026-04-13 (Self-Refine Seed Stability)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Fix the `solo_self_refine` seed-stability issue in `scientific_baselines.py` by adding node-local retry and Self-Refine-specific fallbacks for provider failures, instead of modifying the shared `LLMClient` or changing the baseline’s draft-critique-revise structure.
- `rationale`: Historical evidence showed the failing seed died on a query-local `APIConnectionError` during `self_refine_draft`; the shared client already performs transport retries, so the missing piece was query-local containment inside the baseline orchestration layer.
- `alternatives_rejected`: Add another generic retry policy in `llm/client.py`, or let provider exceptions continue to abort the entire seed.
- `linked_adr`: `N/A (baseline resilience refinement)`

## 2026-04-13 (TravelPlanner T1/T2 Observability and Ablation Surface)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Implement T1 as a dedicated `travelplanner_v4_only.yaml` preset and implement T2 through marker-persisted failure reasons plus adapter/export promotion, while leaving `core/orchestrator.py` unchanged.
- `rationale`: The V5 plan explicitly required a pure V4 ablation surface and query-level failure taxonomy, and the existing core already exposed `stop_reason`; the missing piece was durable query-local observability that survives tool execution and can be logged in benchmark artifacts.
- `alternatives_rejected`: Fold the V4-only switches into the main `travelplanner.yaml`, or try to derive all query failures only from `stop_reason` and `final_plan=[]` without persisting tool-level causes.
- `linked_adr`: `N/A (benchmark observability + ablation hygiene)`

## 2026-04-12 (V5 Plan Execution Policy)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Treat the proposed V5 plan as a strong draft, but require a pre-execution rewrite that separates pure V4 ablation from tuned-performance work and inserts an explicit TravelPlanner adapter redesign track for multi-city support.
- `rationale`: The current draft mixes causal questions (`what do V4 corrections contribute?`) with optimization changes (`heuristics`, `few-shots`, `max_ticks`, `num_agents`), while the dominant failure mode remains an adapter-level single-destination bottleneck that heuristics alone will not resolve.
- `alternatives_rejected`: Execute the plan unchanged, or reduce V5 to only local tuning without addressing the adapter’s representational limitation.
- `linked_adr`: `N/A (campaign planning rule)`

## 2026-04-11 (TravelPlanner Failure Interpretation)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Interpret the current TravelPlanner scientific comparison as a single-destination-capable benchmark slice, and treat the `5-day / 2-city` and `7-day / 3-city` collapse of `StigmergiAgentic` as a structural adapter limitation until multi-city routing and explicit empty-plan failure export are implemented.
- `rationale`: The analysis of run `20260409_233919` showed that the adapter binds search and routing to one `dest`, while many failed queries terminate with `final_plan=[]` and `No travel plan generated.` under `status=ok`; reading these outcomes as random planner weakness would overstate the current generality of the framework.
- `alternatives_rejected`: Continue discussing the failures as generic LLM instability, or interpret the current TravelPlanner table as evidence of multi-city capability without adapter-level routing support.
- `linked_adr`: `N/A (post-run scientific interpretation rule)`

## 2026-04-09 (LangGraph Robustness)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Handle LangGraph TravelPlanner intermediate-node structured-output failures with parse retries and deterministic fallbacks instead of aborting the batch on the first malformed JSON response.
- `rationale`: Hosted-model runs can return transport-successful but schema-invalid payloads; batch reproducibility is better served by bounded local degradation than by full campaign interruption.
- `alternatives_rejected`: Keep single-shot schema parsing with hard failure, or silently ignore malformed fields without explicit retry/fallback behavior.
- `linked_adr`: `N/A (benchmark runtime hardening)`

## 2026-04-09

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Make the principal TravelPlanner comparison notebook stream Docker command output live and skip redundant `travelplanner-smoke` rebuilds unless tracked build inputs change or a force flag is set.
- `rationale`: The previous setup cell buffered `docker compose build` output entirely, which made legitimate work look frozen and forced unnecessary rebuild time on every notebook rerun.
- `alternatives_rejected`: Keep buffered subprocess capture in the notebook, or remove the explicit build step entirely without any cache or diagnostic layer.
- `linked_adr`: `N/A (notebook execution-path hardening)`

## 2026-04-08

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Retire SwarmAgentic from the principal TravelPlanner benchmark and adopt `LangGraph Supervisor` as the main centralized hierarchical baseline, executed through a Docker-first shared benchmark pipeline.
- `rationale`: SwarmAgentic proved operationally non-reproducible in the controlled Qwen/OpenRouter protocol, while LangGraph enables an explicit, durable, in-repo state-graph baseline that can share the same scorer, split, and artifact contract as `Solo` and `StigmergiAgentic`.
- `alternatives_rejected`: Keep SwarmAgentic in the main comparison table, compare only `Solo` vs `StigmergiAgentic`, or use a generic LangChain agent path without an explicit graph/state-machine baseline.
- `linked_adr`: `N/A (benchmark methodology pivot)`

## 2026-02-10

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Adopt JSON pheromone store with POSIX file locking and append-only audit trail for Sprint 1.
- `rationale`: Aligns with architecture plan artifacts while ensuring concurrency safety and RQ3 traceability.
- `alternatives_rejected`: Plain unlocked JSON store, full SQLite migration in Sprint 1.
- `linked_adr`: `documentation/decisions/20260210-sprint1-environment-medium.md`

## 2026-02-11

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Implement Sprint 2 validation as mock-first tests with optional non-blocking `live_api` smoke coverage.
- `rationale`: Keeps agent behavior tests deterministic while preserving a direct OpenRouter wiring check path.
- `alternatives_rejected`: Fully live API blocking tests, fully mocked suite without any smoke check.
- `linked_adr`: `documentation/decisions/20260210-sprint2-agents-unitaires.md`

## 2026-02-12

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Adopt Sprint 3 adaptive fallback classification and mountpoint-safe Docker execution to satisfy the blocking gate on `docopt/docopt@0.6.2`.
- `rationale`: Preserves adaptive all-file coverage without static scope filtering while eliminating false negatives from script entrypoints, optional dependencies, and host mount deadlocks.
- `alternatives_rejected`: Threshold-only tuning without fallback reclassification, static exclusion of tests/examples/setup files, bind-mounted `target_repo` with direct delete/reclone.
- `linked_adr`: `documentation/decisions/20260212-sprint3-loop-gating-docopt.md`

## 2026-02-12 (Patch)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Remove hard LLM completion cap and add optional USD cost budgeting using OpenRouter pricing + usage-based accounting.
- `rationale`: Hard output caps reduced migration quality on thinking models; USD-level control is required for reliable cost governance and comparability.
- `alternatives_rejected`: Keep `max_response_tokens=4096`, rely only on token-count budgeting, or disable budgeting entirely.
- `linked_adr`: `documentation/decisions/20260212-sprint3-llm-cost-budget-and-uncapped-output.md`

## 2026-02-12 (Patch 2)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Hard-disable `max_tokens` in runtime requests (ignore `llm.max_response_tokens` even when set).
- `rationale`: Prevents accidental reintroduction of output truncation during migrations, especially in stale Docker-image scenarios.
- `alternatives_rejected`: Keep optional `max_response_tokens` passthrough, rely on manual config discipline.
- `linked_adr`: `documentation/decisions/20260212-sprint3-llm-cost-budget-and-uncapped-output.md`

## 2026-02-17

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Treat Sprint 4 as tooling-complete but benchmark-incomplete until fairness runs and Pareto reporting requirements are satisfied.
- `rationale`: Code paths and tests pass, but current evidence is smoke-level and does not yet meet protocol constraints (`>=5 runs/config`, confidence-interval reporting, complete baseline input coverage).
- `alternatives_rejected`: Mark Sprint 4 fully complete based only on single-run snapshot and mean/std-only Pareto output.
- `linked_adr`: `documentation/decisions/TBD-sprint4-benchmark-readiness.md`

## 2026-02-17 (Closure Implementation)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Upgrade Pareto tooling to enforce baseline coverage and export raw+aggregate evidence, then close Sprint 4 with a bounded 5x3 benchmark protocol on `docopt/docopt@0.6.2`.
- `rationale`: Prevents partial-data misinterpretation and provides reproducible closure artifacts when full unconstrained campaigns are too costly for the current iteration.
- `alternatives_rejected`: Keep aggregate-only Pareto output, accept silent missing-baseline inputs, or defer all benchmark execution until a later sprint.
- `linked_adr`: `documentation/decisions/TBD-sprint4-closure-bounded-benchmark-and-pareto-v2.md`

## 2026-02-17 (Benchmark Stability Hardening)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Add explicit LLM request timeout (`llm.request_timeout_seconds`) and sequential stage action cap (`loop.sequential_stage_action_cap`) to reduce benchmark run hangs.
- `rationale`: Repeated baseline runs showed long-running/non-terminating behavior under provider latency and nested stage loops; bounded runtime controls are needed for campaign completion.
- `alternatives_rejected`: Keep SDK default timeout behavior and unbounded stage `while run()` loops.
- `linked_adr`: `documentation/decisions/TBD-benchmark-runtime-stability-timeout-stage-cap.md`

## 2026-02-17 (Unbounded 5x3 Final Batch Execution)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Execute missing Sprint 4 benchmark runs in parallel using isolated temporary workspace copies, then treat `metrics/output/sprint4_20260217_full` as the canonical unbounded 5x3 batch.
- `rationale`: Parallelism reduces wall time, while per-worker workspace isolation avoids race conditions/cross-run contamination on shared runtime artifacts.
- `alternatives_rejected`: Run all remaining jobs serially, or run them in parallel from one workspace with shared `target_repo`/`pheromones`.
- `linked_adr`: `documentation/decisions/TBD-sprint4-unbounded-5x3-final-batch.md`

## 2026-02-19 (Sprint 5 Provider Switch: OpenRouter + Z.ai)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Make `LLMClient` provider-aware and adopt `zai` + `glm-5` as default Sprint 5 frontier configuration while preserving OpenRouter compatibility.
- `rationale`: Sprint 5 requires a frontier model (`glm-5`) and reliable provider switching without touching agent orchestration logic.
- `alternatives_rejected`: Fork a dedicated Z.ai client, or hard-replace OpenRouter paths with Z.ai-only logic.
- `linked_adr`: `documentation/decisions/TBD-sprint5-provider-switch-zai-glm5.md`

## 2026-02-19 (Anti-429 Controls for Z.ai)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Introduce built-in anti-rate-limit controls in `LLMClient` (inter-call pacing + 429-specific backoff floor + jitter), and enable them in default config.
- `rationale`: Repeated Sprint 5 runs encountered frequent Z.ai `429` responses; centralized pacing/backoff is required for stable batch execution.
- `alternatives_rejected`: Handle delays only in shell loops, or raise retries without pacing control.
- `linked_adr`: `documentation/decisions/TBD-sprint5-anti429-llm-pacing.md`

## 2026-02-19 (Provider Default Rollback to OpenRouter)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Restore OpenRouter as default runtime provider/model for Sprint execution (`qwen/qwen3-235b-a22b-2507`) and disable default inter-call pacing.
- `rationale`: User prioritizes faster campaign throughput; current Z.ai rate-limiting profile introduced repeated delays and unstable batch progress.
- `alternatives_rejected`: Keep Z.ai default with long enforced pacing intervals.
- `linked_adr`: `documentation/decisions/TBD-sprint5-openrouter-default-rollback.md`

## 2026-02-19 (GPT-5-nano Pre-Sprint Trial Protocol)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Run the pre-Sprint model trial with `openai/gpt-5-nano` (OpenRouter) as 5 complete stigmergic runs without `--max-tokens`, and report from a curated exact-5 output set.
- `rationale`: The trial needed uncapped completions and strict sample size control (`n=5`) despite an interrupted batch during execution.
- `alternatives_rejected`: Keep the interrupted mixed run set as-is, or rerun everything from scratch serially.
- `linked_adr`: `documentation/decisions/TBD-pre-sprint-gpt5nano-trial-protocol.md`

## 2026-02-26

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Execute V2 Sprint 1 as a hard reset branch and replace JSON pheromone storage with a generic SQLite/WAL marker store plus mandatory append-only audit.
- `rationale`: A clean cut removes legacy role-coupled constraints and provides a stable, domain-agnostic coordination substrate with stronger concurrency and governance guarantees.
- `alternatives_rejected`: Coexistence with V0.1 runtime, or delaying SQLite migration while keeping JSON+file-lock storage.
- `linked_adr`: `documentation/decisions/20260226-sprint1-v2-core-reset-and-sqlite-marker-store.md`

## 2026-02-26 (Documentation Protocol)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Require a per-sprint artifact functioning note in `documentation/redisgn_v2/sprint_XX_artifact.md` for all future sprint closures.
- `rationale`: This creates a stable, sprint-granular trace of runtime behavior and reduces onboarding ambiguity for future agents.
- `alternatives_rejected`: Keeping artifact-state notes only in `construction_log.md`, or relying on ad-hoc sprint summaries.
- `linked_adr`: `N/A (process rule)`

## 2026-02-26 (Sprint 2 V2 Runtime)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Implement Sprint 2 with an async core runtime (`Environment`, `StigmergicAgent`, `Orchestrator`) plus sync test wrapper, pressure-driven selection, and environment-mediated deposits.
- `rationale`: This preserves stigmergic decentralization, keeps mutation/guardrail control centralized, and enables deterministic unit validation without external dependencies.
- `alternatives_rejected`: Fully synchronous orchestrator, direct tool-to-store writes, and deferred LLM client port.
- `linked_adr`: `documentation/decisions/20260226-sprint2-v2-agent-orchestrator-runtime.md`

## 2026-02-26 (Sprint 3 V2 Assistant Runtime)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Implement Sprint 3 as a shared infrastructure-tool layer plus an `assistant` adapter and CLI entrypoint, while keeping adapter scope `assistant`-only for this sprint.
- `rationale`: This enables end-to-end framework usage without coupling to benchmark adapters and preserves a clean path to register the same tools in future domain adapters.
- `alternatives_rejected`: Adding partial TravelPlanner/CodeMigration stubs in Sprint 3, or introducing assistant-specific tool contracts outside `ToolRegistry`.
- `linked_adr`: `documentation/decisions/20260226-sprint3-v2-infrastructure-tools-and-assistant-mode.md`

## 2026-03-04 (Assistant Eligibility Defaults + Execution-Oriented Output)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Remove hardcoded assistant marker allowlists (`decompose`/`think`) and move to context-derived tool eligibility defaults, while preserving explicit `eligible_actions` as an override and enriching final CLI responses with concrete tool outputs.
- `rationale`: Hardcoded allowlists prevented execution-capable tools from participating in normal assistant runs and produced plan-only outputs; context-derived eligibility restores practical execution without losing adapter-level control.
- `alternatives_rejected`: Keep strict allowlists everywhere, or make all tools universally eligible regardless of required payload inputs.
- `linked_adr`: `N/A (runtime behavior refinement in Sprint 3 scope)`

## 2026-03-04 (Think-Then-Act Gate for Active Subtasks)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Enforce a think-then-act lifecycle where active subtasks are progressed by concrete execution tools, while `think` is blocked on generic active markers and only allowed on a decomposed root-marker exception path.
- `rationale`: This prevents plan-only marker completion and aligns terminal progress with artifact-generating actions (read/write/bash/search) rather than repeated reasoning-only loops.
- `alternatives_rejected`: Keep `think` fully eligible on active markers, or force all markers through static hardcoded tool allowlists.
- `linked_adr`: `N/A (runtime execution policy update)`

## 2026-03-04 (Emergent Structure over Fixed Decomposition Defaults)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Remove fixed decomposition defaults and heuristic tool-hint inference by making `subtask_count` optional, using LLM-only structured hints in `think`, and driving intensity decrements from config.
- `rationale`: Fixed `subtask_count=3` and local hint inference introduced non-emergent behavior and planner bias; optional shaping + strict structured outputs better preserve execution-first stigmergic dynamics.
- `alternatives_rejected`: Keep forced default subtask counts, keep `_infer_tool_hints` fallback, or keep hardcoded intensity decrements in tool code.
- `linked_adr`: `N/A (Sprint 3 V2 runtime behavior refinement)`

## 2026-03-04 (Sprint 4 V3 Runtime Overhaul)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Standardize V3 runtime on structured async LLM interactions, dependency-gated marker scheduling, and session-isolated persistence while preserving sync backward compatibility.
- `rationale`: This combination addresses major instability sources (untyped outputs, race-prone concurrency, dependency violations, and cross-run state leakage) without breaking existing sync consumers.
- `alternatives_rejected`: Async-only breaking migration, prompt-only dependency conventions without runtime enforcement, shared single DB path across runs.
- `linked_adr`: `documentation/decisions/20260304-sprint4-v3-runtime-overhaul.md`

## 2026-03-04 (Sprint 5 V3 Memory + Emergence + Lessons)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Extend Sprint 4 V3 with bounded episodic agent memory, schema-neutral emergence telemetry, and automatic high-quality `lesson` marker deposition while keeping marker persistence schema unchanged.
- `rationale`: The thesis runtime needed cognition and observability signals beyond intensity reinforcement, but introducing DB/schema migrations would increase risk and coupling; decision-level memory payloads + audit-log parsing preserve compatibility and traceability.
- `alternatives_rejected`: Persist agent memory directly in marker schema, add dedicated emergence tables, or keep emergence/lesson logic as external post-processing only.
- `linked_adr`: `documentation/decisions/20260304-sprint5-v3-memory-emergence-lessons.md`

## 2026-03-05 (Sprint 6 V3 TravelPlanner Domainization)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Standardize TravelPlanner integration as a dedicated adapter vertical slice (`workspace`, `tools`, `adapter`, `evaluator`) and remove V0.1 legacy runtime/tests in the same sprint.
- `rationale`: This provides a clean domain-validation signal for V3 architecture without core coupling to legacy code paths, while ensuring benchmark scoring remains deterministic and auditable.
- `alternatives_rejected`: Keep mixed V0.1/V3 runtime coexistence; perform LLM-based constraint evaluation; postpone cleanup to a later sprint.
- `linked_adr`: `documentation/decisions/20260305-sprint6-travelplanner-adapter-and-fidelity-eval.md`

## 2026-03-06 (OC1-OC5 Thesis Alignment Audit Method)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Evaluate thesis alignment with a three-layer matrix (`literature intent -> V3 plan promise -> current V3 repo evidence`) and treat only current-runtime-backed evidence as valid proof.
- `rationale`: This prevents mixing roadmap claims, legacy artifacts, and actual V3 capabilities, and makes DSR readiness gaps visible without overstating implementation maturity.
- `alternatives_rejected`: Audit only the plan against the review, or count historical/non-V3 artifacts as current proof.
- `linked_adr`: `documentation/v3_oc1_oc5_alignment_audit.md`

## 2026-03-06 (Colab Qwen3-14B-AWQ Notebook Hardening)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Rebuild the Colab Qwen benchmark notebook around auto-detected AWQ loading, conservative Tesla T4 vLLM settings, and file-backed startup diagnostics instead of forced backend/quantization overrides.
- `rationale`: The previous notebook hid the root cause behind truncated logs and brittle T4-specific assumptions; a restart-aware install flow plus explicit log capture is more stable and debuggable across Colab images.
- `alternatives_rejected`: Keep forcing `FLASHINFER` with `awq_marlin`, or keep the existing timeout path that only surfaces `Engine core initialization failed`.
- `linked_adr`: `N/A (notebook/runbook hardening)`

## 2026-03-06 (TravelPlanner Colab Benchmark Execution Path)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Rebuild the TravelPlanner Sprint 6 notebook to run through a local Colab vLLM server plus a temporary runtime override config, with per-query checkpoints and official scorer evaluation kept inside the notebook flow.
- `rationale`: This keeps the benchmark path reproducible on Colab without changing checked-in runtime defaults, while making long-running local inference resilient to restarts and preemption.
- `alternatives_rejected`: Keep the previous notebook's hosted-LLM assumptions and coarse checkpoint cadence, or hardcode local Colab settings into repo YAML files.
- `linked_adr`: `N/A (notebook/runbook hardening)`

## 2026-03-06 (Colab Feasibility Verdict Protocol)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Frame the root-level Colab Qwen notebook as a thesis-facing feasibility protocol with repeated stability checks and a three-level verdict (`GO`, `CONDITIONAL GO`, `NO-GO`) instead of a single-pass `works/does not work` check.
- `rationale`: The thesis question is about benchmark credibility, not only local execution; repeated load, structured-output reliability, and provenance-aware interpretation are required before replacing or complementing the current backend.
- `alternatives_rejected`: Keep a latency-only smoke notebook, or use a binary startup verdict without repeated benchmark-style requests.
- `linked_adr`: `N/A (benchmark notebook protocol)`

## 2026-03-22 (Sprint 6 V4 Stigmergic Corrections)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Implement local sensing, temporal decay, frequentation reinforcement, emergent contention resolution, and emergence feedback as opt-in runtime features instead of replacing the default Sprint 6 behavior.
- `rationale`: The thesis needed a stronger stigmergic interpretation, but replacing the existing runtime in-place would have broken compatibility, muddied benchmark comparisons, and increased rollout risk.
- `alternatives_rejected`: Hard-switch the runtime to the new behavior by default, or implement only local sensing and leave the other audit findings unresolved.
- `linked_adr`: `documentation/decisions/20260322-sprint6-v4-stigmergic-corrections.md`

## 2026-03-12 (Repo-Local RunPod Operations Skill)

## 2026-03-17 (TravelPlanner Failure-Triage Lens)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Diagnose TravelPlanner benchmark quality primarily through scenario-shape buckets (`3 days/1 city`, `5 days/2 cities`, `7 days/3 cities`) before changing prompts or models.
- `rationale`: The official run shows a regime break by itinerary shape, which is more informative than top-line pass rates and points directly to adapter/search-coverage limitations rather than generic model weakness.
- `alternatives_rejected`: Tune prompts from aggregate scores only, or attribute the low final pass rate primarily to model quality without scenario-level decomposition.
- `linked_adr`: `N/A (analysis decision for benchmark triage)`

## 2026-03-17 (Controlled OpenRouter GPT-4o Framework Comparison Protocol)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Standardize the next TravelPlanner framework comparison on OpenRouter-routed `openai/gpt-4o`, the validation split, and the shared official scorer, with SwarmAgentic adapted only at the provider/model-compatibility layer and result normalization layer.

## 2026-04-01 (SwarmAgentic OpenRouter Fault Tolerance)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Harden the SwarmAgentic OpenRouter adaptation with per-iteration PSO checkpoints, task-level degradation on transient provider failures, and conservative notebook rerun defaults for the Qwen3.5-9B comparison flow.
- `rationale`: OpenRouter `504` responses and null structured outputs were causing full-run loss after long PSO executions; resumable checkpoints and non-fatal task failure handling preserve benchmark progress and reduce wasted wall-clock time.
- `alternatives_rejected`: Keep end-of-run-only checkpointing, rely only on provider retries, or keep the notebook defaults at high concurrency with forced re-clone/reinstall on every rerun.
- `linked_adr`: `N/A (benchmark workflow hardening)`
- `rationale`: This gives a materially stronger framework comparison than mixing published paper numbers and local Qwen runs, while keeping the remaining uncontrolled factor (SwarmAgentic PSO optimization before evaluation) explicit.
- `alternatives_rejected`: Compare local Qwen scores directly to the published GPT-3.5/GPT-4o table, or reimplement SwarmAgentic behavior from scratch inside this repo.
- `linked_adr`: `N/A (experiment protocol decision)`

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Add a repo-local `runpod-ops` skill that prioritizes the installed `runpodctl` command shape over stale documentation examples, while bundling official RunPod product constraints and a StigmergiAgentic-specific Pod workflow.
- `rationale`: RunPod became the likely replacement for Colab in long-running benchmark work, and successful operation depends on precise CLI syntax plus durable Pod/storage guidance; a local skill reduces repeated rediscovery and avoids using deprecated RunPod commands.
- `alternatives_rejected`: Rely on ad-hoc web searches each turn, or write a doc-only note without a reusable skill structure.
- `linked_adr`: `N/A (local skill and workflow enablement)`

## 2026-03-12 (Autoresearch Integration Pattern)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Integrate `karpathy/autoresearch` into V3 as a native research adapter with fixed evaluation and artifact iteration, not by embedding its single-repo training assumptions directly.
- `rationale`: V3 already exposes the right extensibility points (`DomainAdapter`, `ToolRegistry`, evaluator-style scoring, reinforcement), while direct embedding would couple the runtime to `autoresearch`-specific artifacts such as `train.py`, `prepare.py`, and `results.tsv` and would not cover literature-grounding needs.
- `alternatives_rejected`: Run `autoresearch` unchanged as an outer shell around this repo, or overload the generic assistant adapter with ad hoc research behavior.
- `linked_adr`: `N/A (integration strategy note)`

## 2026-03-13 (Repo-Local Objective Autoresearch Skill)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Implement one hybrid repo-local skill, `objective-autoresearch`, instead of splitting framework self-improvement and sourced research into separate skills.
- `rationale`: The user wants one shared mentality centered on objective retention, fixed evaluation, and keep/discard iteration; a single skill with explicit mode selection keeps invocation simple while still preventing drift through narrow trigger rules and mode-specific references.
- `alternatives_rejected`: Create two separate skills, or keep the autoresearch mentality as an informal prompt pattern without reusable skill packaging.
- `linked_adr`: `N/A (repo-local skill implementation)`

## 2026-03-13 (Home AGENTS Simplification)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Remove the `Knowledge Governance` section from `/Users/lotfi/.codex/AGENTS.md` and replace it with one lightweight repo-local skill preference under `Skill Hygiene`.
- `rationale`: The heavier section added policy weight without improving day-to-day execution; a concise locality rule preserves the useful behavior while making the principal AGENTS file easier to read and maintain.
- `alternatives_rejected`: Keep the section as-is, or delete it without preserving any guidance about repo-local vs home-level skills.
- `linked_adr`: `N/A (home instruction cleanup)`

## 2026-03-13 (RunPod TravelPlanner Pod Workflow)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Standardize TravelPlanner remote execution around a branch-pinned RunPod workflow with one local creation script, one raw-fetched bootstrap script, and repo-resident smoke/package scripts.
- `rationale`: The repository is too heavy and too dirty to mirror blindly, while the pod starts empty; a pushed-ref workflow keeps the execution source auditable and lets the pod bootstrap itself from GitHub before running `uv`-based TravelPlanner checks.
- `alternatives_rejected`: Sync the whole local workspace to the pod with `runpodctl send`, clone an unspecified branch ad hoc on the pod, or rely on Docker Compose inside the pod for benchmark execution.
- `linked_adr`: `N/A (ops workflow standardization)`

## 2026-03-13 (OpenRouter Baseline Reset and Local Smoke Standard)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Standardize the checked-in runtime baseline on OpenRouter `qwen/qwen3.5-9b`, expose LLM metadata in CLI JSON summaries, and use one local TravelPlanner smoke script as the default verification path while pruning notebook and pod-workflow detours from the main repo surface. For the stable TravelPlanner path, cap completions, disable OpenRouter reasoning on strict-JSON calls, and compact the itinerary prompt to workspace-backed records.
- `rationale`: A single baseline reduces setup drift and decision fatigue, keeps fixtures aligned with real runtime defaults, and preserves scorer-backed validation without carrying Colab/Kaggle/RunPod workflow complexity in the everyday repository path. The live provider behavior showed that uncapped reasoning-heavy responses were the real blocker, so the runtime now treats strict JSON planning as a bounded, non-reasoning task.
- `alternatives_rejected`: Keep `qwen/qwen3.5-flash-02-23` or older 235B defaults as the baseline, retain the pod-specific smoke flow as the standard path, leave benchmark notebooks and session artifacts in the primary repo surface, or keep reasoning enabled and rely on prompt wording alone to suppress long thought traces.
- `linked_adr`: `N/A (baseline cleanup and workflow narrowing)`

## 2026-03-17 (Docker as the Benchmark Validation Source of Truth)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Run the TravelPlanner smoke workflow through Docker Compose by default and treat the containerized result as the only benchmark-valid evidence path.
- `rationale`: The repository already defines Docker as its reproducible execution contract; validating benchmark runs from the host shell creates ambiguity about environment, dependency source, and artifact provenance. The containerized smoke reproduced the same `final_pass_rate=0.0`, so quality gaps now clearly belong to framework behavior rather than host drift.
- `alternatives_rejected`: Keep using the host-local smoke script as the default benchmark path, or introduce query-specific scorer patches before first aligning execution provenance.
- `linked_adr`: `documentation/decisions/20260212-sprint2.5-docker-infrastructure.md`

## 2026-03-17 (TravelPlanner Scorer-Grounded Planning Standard)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Improve TravelPlanner benchmark performance only through framework-level grounding changes: explicit route-search markers, scorer-aligned serialization, sandbox-aligned inventories, feasibility-aware hotel candidate selection, and replanning from official failure messages.
- `rationale`: These changes preserve the philosophy of the framework by strengthening the adapter's contracts and planner loop instead of inserting query-specific shortcuts or evaluator-side hacks. The resulting Docker smoke reached `final_pass_rate=1.0` on `Query 0` while staying within the benchmark's official search space and scoring semantics.
- `alternatives_rejected`: Hardcode `Query 0` templates, patch the official evaluator, inject post-hoc manual itinerary rows, or keep free-form planner outputs and hope the scorer infers intent from approximate strings.
- `linked_adr`: `N/A (adapter and planning-loop standardization)`

## 2026-03-17 (Notebook as the Dockerized Full-Eval Driver)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Add a notebook driver for the full official TravelPlanner campaign, but keep all benchmark execution and official scoring inside Docker with resumable per-query checkpoints.
- `rationale`: The user needs a convenient cockpit for launching and inspecting the full official benchmark, but moving execution into the host notebook kernel would weaken environment provenance and make results harder to compare with scripted Docker runs. A Docker-driven notebook preserves the benchmark contract while making long campaigns easier to start, resume, and analyze.
- `alternatives_rejected`: Run the full benchmark directly in the notebook kernel, keep only shell scripts with no interactive inspection surface, or embed official evaluation logic directly into the notebook instead of reusing the repository scripts.
- `linked_adr`: `N/A (benchmark notebook orchestration)`

## 2026-03-17 (Explicit Repo Root for Docker Script Entry Points)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Require Docker-invoked repository scripts to inject the repository root into `sys.path` before importing project modules, and apply that rule to `scripts/run_travelplanner_query_export.py`.
- `rationale`: Container entrypoints executed by absolute script path do not reliably inherit the repository root on Python's import path, which can collapse an entire benchmark campaign into uniform runtime failures. Making the entrypoint self-sufficient keeps notebook, shell, and Docker execution paths aligned.
- `alternatives_rejected`: Assume the container working directory will always rescue imports, switch every invocation to `python -m ...`, or debug runtime failures only after a full split has already been attempted.
- `linked_adr`: `N/A (entrypoint robustness rule)`

## 2026-03-22 (Controlled Same-Model Qwen Framework Comparison Protocol)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Standardize TravelPlanner framework comparisons on a three-arm protocol that fixes OpenRouter as provider, `qwen/qwen3.5-9b` as routed model, the official validation split as dataset, and the local official scorer as the only scoring path, with evaluation arms for solo Qwen, SwarmAgentic, and StigmergiAgentic.
- `rationale`: The earlier comparison mixed frameworks and model families, which made any scientific claim about orchestration strength too weak. Holding provider, model, split, and scorer constant while adding a solo-model arm isolates what the orchestration contributes relative to the same base model and makes cross-framework differences interpretable.
- `alternatives_rejected`: Compare against published GPT-3.5 or GPT-4o table values directly, compare only SwarmAgentic versus StigmergiAgentic without a solo baseline, or score each framework through its own native evaluation path.
- `linked_adr`: `N/A (controlled benchmark protocol)`

## 2026-04-02 (TravelPlanner Comparison Reporting Gate)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Treat the current notebook as valid internal evidence for the two completed arms (`solo` and `StigmergiAgentic`) but not yet as a publishable three-way benchmark artifact; require a clean single-run rerender, explicit budget reporting, and a clarified Swarm patch scope before thesis-grade reporting.
- `rationale`: The persisted JSON artifacts support the reported two-arm scores, but the notebook surface currently mixes outputs from multiple run tags and the Swarm preparation layer changes execution behavior beyond simple provider wiring. Without cleaning those issues, a reader could overinterpret the notebook as a fully reproducible and methodologically matched framework comparison.
- `alternatives_rejected`: Cite the notebook as-is in thesis text, hide the budget asymmetry behind aggregate pass rates only, or describe the patched Swarm baseline as an untouched upstream comparison.
- `linked_adr`: `N/A (benchmark review gate)`

## 2026-04-02 (Qwen Swarm Benchmark Modes and Failure Separation)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Run the Qwen SwarmAgentic TravelPlanner baseline through explicit `preflight`, `pilot`, and `full` modes with mode-specific artifacts, classify provider `504` outages as `infra_failure` rather than score `0`, and keep the notebook on the healthy local interpreter for repo scripts while reserving isolated virtualenv use for the cloned Swarm baseline.
- `rationale`: The thesis benchmark needs a fair same-backbone comparison, but the original notebook mixed orchestration, scoring, and baseline setup inside large cells and let provider failures surface as hard crashes. Separating modes and status artifacts makes the Swarm path resumable and auditable, while decoupling local notebook scripts from a broken project `.venv` keeps the experiment runnable without relaxing the isolation of the external baseline.
- `alternatives_rejected`: Keep the monolithic notebook cell, treat `504` as benchmark score failures, or force every local script through the project `.venv` even when that environment is corrupted.
- `linked_adr`: `N/A (benchmark orchestration rule)`

## 2026-04-03 (Standalone Swarm Full Comparison Notebook)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Add a dedicated notebook for the strict full SwarmAgentic Qwen comparison that reruns only SwarmAgentic and compares it against the previously completed Solo and StigmergiAgentic artifacts from a fixed reference run tag by default.
- `rationale`: The unstable part of the thesis comparison is the Swarm baseline, not the already-scored Solo and StigmergiAgentic arms. A baseline-specific notebook shortens rerun cycles, reduces accidental churn on the stable arms, and makes it easier to enforce a scientific gate where the final table appears only if Swarm finishes successfully.
- `alternatives_rejected`: Reuse the large three-arm notebook for every Swarm retry, manually copy paths into ad hoc cells, or compare only aggregate official scores without paired per-query final-pass analysis.
- `linked_adr`: `N/A (dedicated baseline notebook rule)`

## 2026-04-07 (Notebook-Level Python Auto-Resolution)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Make the dedicated Swarm scientific notebook resolve a working interpreter dynamically and run all local repo scripts through that interpreter instead of calling bare `python`.
- `rationale`: The benchmark notebook can execute under a kernel environment that differs from the shell's default `python`, which leads to immediate failures on imports such as `datasets`. Probing interpreters up front and standardizing on one verified interpreter is cheaper and safer than expecting users to manually reconcile environments before each rerun.
- `alternatives_rejected`: Keep hardcoded `python` calls, instruct the user to repair environments manually before notebook use, or pin the notebook to a single absolute interpreter path.
- `linked_adr`: `N/A (notebook runtime robustness rule)`

## 2026-04-07 (SwarmAgentic Watchdog Observability)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Wrap the SwarmAgentic benchmark subprocesses with heartbeat-based monitoring, watched-artifact inactivity timeouts, patch-revision clone refresh, and notebook-visible debug artifacts instead of trusting raw subprocess liveness.
- `rationale`: The Qwen/OpenRouter Swarm baseline can enter long silent stalls where the Python process stays alive, no checkpoint is written, and the notebook appears to "run" for tens of minutes without progress. A watchdog keyed to real progress signals plus file-backed monitor artifacts reduces wasted wall-clock time and makes infra stalls auditable without conflating them with benchmark scores.
- `alternatives_rejected`: Wait indefinitely on living subprocesses, rely only on provider SDK timeouts, or inspect hangs manually from external terminal tools after each failed run.
- `linked_adr`: `N/A (baseline observability and recovery rule)`

## 2026-04-09 (Organization-Philosophy TravelPlanner Benchmark)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Promote the principal TravelPlanner benchmark from a small named-framework comparison to a publication-oriented organization-philosophy study with six controlled arms, three seeds, gated execution (`preflight/pilot/full`), and a generated paper pack of statistical and methodological artifacts.
- `rationale`: The thesis claim is about stigmergic organization quality, not about outperforming one unstable external repo or one orchestration SDK. Reframing the benchmark around organizational forms preserves scientific fairness, aligns better with DSR/FEDS, and makes the comparison auditable and publishable through reproducibility artifacts rather than notebook screenshots.
- `alternatives_rejected`: Keep the three-arm framework-branded comparison only, rely on SwarmAgentic as the main external baseline despite reproducibility failures, or compute publication tables manually outside the repository.
- `linked_adr`: `N/A (scientific benchmark framing rule)`

## 2026-04-09 (TravelPlanner Official Evaluator Runtime Path Repair)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Harden the vendored TravelPlanner official runner by revalidating the repo-global database symlink on every invocation and executing evaluation-time file-IO calls inside the upstream `evaluation/` directory context.
- `rationale`: The LangGraph benchmark failure after roughly 148 completed queries was not a model-quality issue but an integration fault: upstream OSU evaluation code opens `../database/...` paths relative to `evaluation/`, while the bridge subprocess was only importing from that directory and was also vulnerable to a stale symlink left behind by prior temp runs. Repairing both the symlink lifecycle and the runtime cwd removes a class of late-run crashes that can waste hours and invalidate otherwise successful query outputs.
- `alternatives_rejected`: Keep the stale-link check best-effort only, patch each upstream module individually, or accept the late failure as an unavoidable external-benchmark limitation.
- `linked_adr`: `N/A (vendored evaluator integration rule)`

## 2026-04-10 (Artifact-Only Benchmark Status Reads)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Use artifact-only inspection (`run_registry.csv`, `official_eval.json`, query file counts/mtimes) as the default way to answer progress questions on active TravelPlanner studies instead of interacting with the notebook kernel or benchmark subprocess.
- `rationale`: The user often needs reassurance or provisional numbers while a multi-hour Docker benchmark is still running. Reading persisted study artifacts provides accurate status and partial results without risking notebook interruption, TTY side effects, or accidental reruns.
- `alternatives_rejected`: Attach to the running container interactively, inspect notebook cell state only, or infer progress solely from provider dashboards.
- `linked_adr`: `N/A (safe benchmark observability rule)`

## 2026-04-11 (Scientific Baseline Intermediate Fallbacks)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Make the TravelPlanner `Self-Refine` and `Planner-Executor` scientific baselines recover from truncated intermediate JSON by using compact prompts plus deterministic fallback objects instead of aborting the seed.
- `rationale`: The failed study arms were not collapsing on the final scored itinerary schema but on intermediate reviewer/planner schemas that occasionally returned truncated JSON under the shared Qwen/OpenRouter setup. Treating those intermediate artifacts as recoverable preserves the intent of the baseline while turning a benchmark-stopping parse error into a lower-risk local repair path.
- `alternatives_rejected`: Increase token budgets globally, accept those baselines as permanently invalid, or hand-edit partial outputs after the fact.
- `linked_adr`: `N/A (scientific baseline robustness rule)`

## 2026-04-12 (Executable Scientific Plan Gate)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Treat benchmark-improvement plans as approved only after checking that every major task maps to current code extension points, existing runner behavior, and the actual domain representation used by the adapter.
- `rationale`: The revised V5.1 plan is much closer to scientifically sound execution, but review against the live code still surfaced hidden implementation constraints: TravelPlanner currently stores a scalar `dest`, the agent layer does not yet expose an adapter-provided heuristic hook, and the benchmark runner already checkpoints per query. Requiring an executability gate avoids launching long campaigns from plans that are directionally right but still underspecified at the implementation boundary.
- `alternatives_rejected`: Approve plans based on methodology text alone, defer all feasibility checks until implementation starts, or keep tuning and redesign work mixed inside one loosely specified execution plan.
- `linked_adr`: `N/A (scientific plan review rule)`

## 2026-04-12 (Official Scorer Denominator Rule)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Treat missing query outputs in TravelPlanner benchmark runs as full-denominator failures unless the official scorer is explicitly restricted to a subset index range.
- `rationale`: The continue-on-error runner can preserve a seed and write per-query failure artifacts, but the current official scorer iterates across the requested query range and evaluates missing predictions as empty plans. Labeling such outputs as a "partial official score" would blur the denominator and weaken the scientific interpretation of delivery and final-pass rates.
- `alternatives_rejected`: Describe full-range scores with missing predictions as subset scores, hide failed-query counts behind aggregate metrics, or stop the entire seed on first failed query to preserve terminology.
- `linked_adr`: `N/A (scorer semantics rule)`

## 2026-04-12 (Plan Acceptance Criteria Must Match Scorer Semantics)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: When updating benchmark plans, rewrite acceptance criteria to match the actual official scorer behavior even if the underlying implementation idea is already correct.
- `rationale`: The V5.1 T5 design was directionally right, but one sentence still implied subset official evaluation. Tightening that wording preserves methodological clarity without changing the technical plan and prevents later thesis text from overstating what a continue-on-error run means.
- `alternatives_rejected`: Leave the ambiguous wording in place, rely on oral clarification later, or postpone the correction until ADR drafting.
- `linked_adr`: `N/A (plan wording precision rule)`

## 2026-04-12 (TravelPlanner T0 Multi-City Adapter Shape)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Implement V5.1 T0 entirely inside `adapters/travelplanner/` by inferring `city_sequence` in the workspace, expanding the adapter DAG into per-city and per-leg markers, and teaching the planning toolchain to consume dynamic search keys by prefix while keeping single-city keys backward compatible.
- `rationale`: The root bottleneck was not the core stigmergic runtime but the TravelPlanner adapter's single-scalar destination encoding. Keeping the redesign local to the adapter layer fixes the domain representation gap, preserves `core/` invariants, and avoids breaking existing single-city flows or tests that still expect legacy search keys.
- `alternatives_rejected`: Parse `dest` as a list directly, move domain-specific sequencing into `core/`, or replace all legacy search keys with multi-city-only names in one breaking sweep.
- `linked_adr`: `N/A (adapter-local multi-city routing rule)`

## 2026-04-14 (TravelPlanner T5 Continue-on-Error Benchmark Runner)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Implement benchmark-runner resilience as per-query failed checkpoints plus unchanged full-denominator official scoring, instead of aborting the seed or introducing a separate partial-scoring mode.
- `rationale`: T5 is about campaign continuity, not changing how TravelPlanner official evaluation is computed. Writing explicit failed query payloads preserves resume semantics, keeps `runs.json` structurally complete, and lets the official scorer continue to treat failed or missing predictions as empty unsuccessful plans under the original denominator.
- `alternatives_rejected`: Stop the seed on the first exporter failure, drop failed queries from `runs.json`, or define an ad hoc partial official score for resilience runs.
- `linked_adr`: `N/A (campaign continue-on-error rule)`

## 2026-04-16 (TravelPlanner V5-Full Adapter-Local Execution Hardening)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Implement V5-full execution improvements entirely in the TravelPlanner adapter/config/script layer, using train-only prompt/tuning data and extending the existing benchmark runner with subset-aware aliases instead of modifying `core/`.
- `rationale`: The execution plan explicitly forbids changes to the generic runtime and to the vendored official evaluator. Adapter-local marker shaping, train-only prompt enrichment, a temporary-config tuning workflow, and lightweight runner aliases satisfy the plan while preserving runtime invariants and benchmark validity.
- `alternatives_rejected`: Move shaping into `core.pressure` or `core.orchestrator`, tune directly against the validation preset, or fork a separate V5-only benchmark runner.
- `linked_adr`: `documentation/decisions/20260416-sprint7-v5-full-execution-hardening.md`

## 2026-04-17 (V6 Should Start With a Paired-Seed, Single-Control-Plane Framework Pass)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Treat the proposed V6 roadmap as strategically valid, but execute it in a stricter order: first establish a paired-seed `v6_base` baseline and isolate anti-stagnation inside the existing emergence/orchestrator control plane before attempting persistent subgoal or validator-contract redesigns.
- `rationale`: The current runtime already mutates inhibition and temperature through the emergence feedback loop, so adding separate T1/T5 controllers would blur attribution unless they are unified. The evidence for `idle=16` is promising but currently compared across mixed seeds, and T2/T3 are materially larger design changes than the plan wording suggests because they alter task-representation and repair contracts rather than just tuning scheduling behavior.
- `alternatives_rejected`: Execute T1-T5 as one broad ladder without paired-seed cleanup, introduce a second adaptive controller next to the existing feedback loop, or treat T2 persistent decomposition as a lightweight early ablation.
- `linked_adr`: `N/A (framework plan review rule)`

## 2026-04-18 (V6 Phase 1 Uses Three Branching Arms, Not a Long Additive Ladder)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Rewrite V6 phase 1 around a paired-seed `v6_base` plus three branching framework arms (`V6-A`, `V6-B`, `V6-C`), while deferring persistent subgoal coverage to a separate `V6.2` plan.
- `rationale`: A short branching ablation preserves attribution far better than a five-step additive ladder, especially when one shared controller change already dominates the design. Keeping the first wave limited to unified recovery, short-horizon stability, and targeted repair lets the project test genuinely runtime-general levers before opening a heavier redesign of task representation.
- `alternatives_rejected`: Keep the original long `V6-A` to `V6-E` additive chain, fold persistent decomposition into the first wave anyway, or combine every promising lever before measuring them independently.
- `linked_adr`: `N/A (three-arm V6 planning rule)`

## 2026-04-18 (V6 Phase 1 Ships as Opt-In Runtime Controls With a Frozen V5 Reference)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Implement V6 phase 1 as three opt-in generic runtime surfaces (`recovery_controller`, `stickiness`, `targeted_repair`) plus dedicated V6 presets, while keeping `config/ablation/v5_full.yaml` unchanged.
- `rationale`: The V6 plan needs experimentally attributable framework changes without polluting the frozen V5 benchmark reference. Explicit config gates and new presets allow the runtime to gain real control-plane leverage while preserving a stable comparison anchor and keeping adapter-specific repair semantics outside `core/`.
- `alternatives_rejected`: Mutate `v5_full.yaml` directly into the V6 baseline, infer contention only from `marker_reads`, or keep targeted repair fully adapter-local without a framework-level contract.
- `linked_adr`: `documentation/decisions/20260418-sprint8-v6-general-runtime-controls.md`

## 2026-04-23 (Monitor Final Campaign Progress With Read-Only Runtime Signals)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: For the final Docker campaign, interpret live progress primarily through read-only runtime signals (`docker ps/stats/top`, file mtimes, and read-only SQLite inspection) rather than raw shell glob counts.
- `rationale`: The Gemma baseline service executes frameworks sequentially, so empty downstream folders are expected until earlier frameworks finish. In `zsh`, unmatched globs add misleading `no matches found` errors, while long TravelPlanner queries can leave counts unchanged for minutes even though the Python runner is still active. Read-only container and SQLite inspection gives a much safer signal during in-flight campaigns without risking interference.
- `alternatives_rejected`: Diagnose progress from `ls *.json | wc -l` alone, assume empty framework folders imply a crash, or attach intrusive debugging/restart actions to running containers.
- `linked_adr`: `N/A (live monitoring rule for in-progress campaign)`

## 2026-04-23 (Treat Persistent Skills as Incomplete Until They Affect Prompts and Credit Paths)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Consider the current cross-run skill loop only partially complete until persistent `skill_markers` are actually consumed by downstream tools and can refresh their own usage/quality signals.
- `rationale`: The live audit shows that skills are stored and recalled, but the active LLM tool path still reads only `lesson_markers`, and success credit is attached only to recalled lessons. This means the current feature demonstrates persistence but not operational reuse, while also encouraging verbose example-specific `skill_text` artifacts that weaken transfer.
- `alternatives_rejected`: Treat storage + recall into `Decision` as sufficient evidence of reusable skills, keep raw objective fragments as canonical skill text, or analyze protocol payloads without distinguishing raw vs clamped adaptations.
- `linked_adr`: `N/A (live audit rule for Sprint 9 skill/protocol persistence)`

## 2026-04-24 (Invalidate C3 Raw Final-Pass Claims Without Delivered Plans)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Do not use raw C3 `evaluation.final_pass_rate` from the final campaign as a primary success metric unless each counted pass is backed by a delivered TravelPlanner plan artifact.
- `rationale`: The final campaign audit found that Gemma and DeepSeek C3 can receive `final_pass=True` despite `assistant_response` being `No travel plan generated.` and no structured plan being present in the exported summary. This creates empty-plan false positives and would overstate stigmergic C3 performance if reported directly.
- `alternatives_rejected`: Report the raw 10.0% Gemma C3 and 58.3% DeepSeek C3 final-pass rates without qualification, collapse delivery and final-pass into one column, or discard the whole campaign instead of preserving baselines and rescoring affected C3 arms.
- `linked_adr`: `N/A (final campaign scoring correction)`

## 2026-04-24 (Treat Final C3 as an Invalid Cross-Run Learning Assembly)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Treat the final C3/skills campaign as a failed implementation assembly, not as valid evidence that stigmergic cross-run skills or protocols are ineffective.
- `rationale`: Validation did not apply the persisted coordination protocols because adapt/eval namespaces diverged, Gemma adapt inherited the default Qwen model instead of training Gemma, skills were stored as verbose raw objective fragments and were not consumed by the active planning prompt, and the protocol compiler was disabled in the C3 configs. These defects break attribution before model-quality comparisons can be interpreted.
- `alternatives_rejected`: Attribute the result primarily to weak model quality, conclude that the skills idea is scientifically disproven, or keep C3 as a primary comparison arm without a clean preflight/rerun.
- `linked_adr`: `N/A (final C3 root-cause audit)`

## 2026-04-24 (Rerun C3 Only With Strict Delivered-Plan Contracts)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Treat C3 reruns as valid only when the runtime and campaign artifacts expose artifact delivery, strict final pass, explicit protocol namespace, skill injection counts, and compiler usage/fallback status.
- `rationale`: The previous C3 campaign failed at the measurement and assembly boundary: empty plans could pass, adapt/eval namespaces diverged, skills were persisted without action-prompt injection, and compiler status was ambiguous. Making these fields explicit in every per-query and aggregate artifact turns future negative results into interpretable evidence rather than silent implementation failures.
- `alternatives_rejected`: Keep using raw `final_pass` as the primary metric, rely on derived namespace hashes, continue shell-loop campaigns without preflight manifests, or test full C3 before isolating protocol, skills, and compiler arms.
- `linked_adr`: `N/A (C3 refactor implementation rule)`

## 2026-04-24 (Baseline Completion Requires Valid JSON, Not File Count)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Treat zero-byte or unparsable baseline query artifacts as failed queries unless they are rerun with logs and replaced by valid JSON outputs.
- `rationale`: The legacy Gemma baseline runner masked stderr and ignored non-zero exits, so `ls *.json | wc -l` reported complete folders even when several query artifacts were empty. This affects LangGraph, MetaGPT, and two simpler baselines; counting only files would overstate campaign completeness and hide environment/API failures.
- `alternatives_rejected`: Accept 180/180 file counts as completion, infer missing stderr causes from aggregate rates, or silently drop empty files from denominators.
- `linked_adr`: `N/A (baseline artifact validity rule)`

## 2026-04-24 (Proceed With V6 Clean, Hold Compiler C3)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Proceed only with a clean V6 smoke/full run after provider recovery, while holding `compiler_only` and `full_c3` until the protocol compiler emits operational TravelPlanner graphs.
- `rationale`: The rerun C3 smoke proves OpenRouter access is restored, but the compiler path still produces empty-plan runs with low marker counts and no delivered artifacts. Since `travelplanner_v6_clean_gemma.yaml` disables the compiler and cross-run mechanisms, V6 clean can still establish the required post-reset baseline without being contaminated by this C3-specific failure.
- `alternatives_rejected`: Launch full C3 despite 0/5 delivery, treat nonzero token spend as sufficient smoke success, or delay V6 clean until every C3 mechanism is repaired.
- `linked_adr`: `N/A (post-smoke launch gate)`

## 2026-04-25 (Do Not Treat Empty Top-Level Plans as Runtime Failure Without Checking Internal Eval)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: When a TravelPlanner run has `evaluation.query_results.strict_final_pass=true` but top-level `final_plan=[]`, classify it as an export-contract defect and repair extraction before interpreting campaign quality.
- `rationale`: V6 clean Gemma initially appeared to fail 10/10 with `empty_plan_from_llm`, yet the internal adapter evaluation already found delivered valid plans. The bug was an empty finalize marker shadowing valid plan-marker artifacts, so relying on top-level fields alone would have incorrectly invalidated V6 clean.
- `alternatives_rejected`: Discard V6 clean as a model/runtime flop, rerun full campaigns before fixing export extraction, or trust empty finalize markers over non-empty validated plan artifacts.
- `linked_adr`: `N/A (TravelPlanner export contract rule)`

## 2026-04-25 (Treat V6 Clean TravelPlanner as Controlled Negative Evidence)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Use the completed V6 clean Gemma TravelPlanner run as a controlled baseline and negative tradeoff result, not as evidence that stigmergic orchestration outperforms strong solo baselines on this benchmark.
- `rationale`: V6 clean completed reproducibly and delivered plans reliably, but its 99/180 strict pass rate is slightly below `solo_direct` and `solo_cot`, below `solo_self_refine`, and substantially more expensive in tokens/runtime. This supports the emerging interpretation that the current TravelPlanner adapter does not expose enough useful coordination surface for stigmergy to pay off globally.
- `alternatives_rejected`: Hide the cost disadvantage, claim superiority from delivery rate alone, compare only against weaker orchestration baselines, or continue optimizing TravelPlanner C3 as the main thesis proof.
- `linked_adr`: `N/A (TravelPlanner V6 interpretation rule)`

## 2026-04-26 (Use MigrationBench as the Primary Post-TravelPlanner Evaluation Track)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Make MigrationBench the primary next benchmark for the DSR evaluation, with TravelPlanner retained as a controlled limiting case and C3 relaunched only through isolated mechanism ablations after the migration adapter and evaluator are stable.
- `rationale`: MigrationBench provides repository-level, execution-based Java migration tasks with an official evaluator and strong relevance to the framework's intended code-transformation contribution. It exposes a better surface for repair loops, tool use, memory, coordination, and auditability than TravelPlanner, while allowing comparisons against strong solo, planner-executor, deterministic, and agentless/self-debug baselines.
- `alternatives_rejected`: Build a new benchmark from scratch, continue optimizing TravelPlanner as the main proof, or launch full C3 before validating the migration adapter, runner, baselines, and official scoring path.
- `linked_adr`: `documentation/redisgn_v2/plan_migrationbench_scientific_campaign.md`

## 2026-04-26 (Freeze Integrated C3 and Make V7 Elastic Colony the Next Architecture Track)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Freeze integrated C3 as the next primary architecture claim and instead build a V7 Elastic Colony track with isolated mechanisms for dynamic ticks, elastic agent pools, progressive decomposition, and visible specialization.
- `rationale`: The current runtime has fixed agent creation, fixed hard tick loops, and static decomposition depth, so adding skills/protocol/compiler on top does not solve the deeper rigidity problem. A colony-style architecture must first demonstrate that it can adapt effort, population, task granularity, and specialization before reintroducing C3 mechanisms as optional add-ons.
- `alternatives_rejected`: Continue repairing full C3 directly, launch a combined elastic architecture without ablations, or keep `num_agents` and `max_ticks` as unexamined constants in the MigrationBench campaign.
- `linked_adr`: `documentation/redisgn_v2/plan_migrationbench_scientific_campaign.md`

## 2026-04-27 (Publish a Documentation-Only Deep Research Context Branch)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Publish the MigrationBench plan and Deep Research brief as a documentation-only commit on `codex/t0-travelplanner-multi-city` for GitHub-connected external analysis.
- `rationale`: The local worktree contains many unrelated implementation and campaign artifacts, so pushing the whole state would confuse the external reviewer and risk leaking noisy context. A targeted documentation commit gives ChatGPT enough current context to critique the architecture and evaluation plan without contaminating the branch with unrelated local changes.
- `alternatives_rejected`: Ask the external agent to inspect the default branch only, paste the entire local context into ChatGPT manually, or commit all dirty worktree changes just to expose recent plans.
- `linked_adr`: `documentation/redisgn_v2/deep_research_brief_for_chatgpt.md`

## 2026-04-27 (Adopt Deep Research Constraints for MigrationBench/V7)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Adopt the external Deep Research report's stricter constraints: MigrationBench supports a code-migration claim only, V6 static precedes V7, `agentless_self_debug` is mandatory, cross-run learning is disabled on main eval, and `compute_protocol_score` is telemetry rather than a scientific endpoint.
- `rationale`: The report agrees with the direction but highlights the main ways the study could become invalid: overclaiming from a Java/Maven benchmark, launching V7 before a stable static baseline, omitting strong agentless baselines, leaking cross-run adaptation into evaluation, and relying on opaque scalar self-optimization scores.
- `alternatives_rejected`: Present MigrationBench as universal proof, launch `v7_elastic_colony` directly, keep agentless as optional, allow protocol/skill learning on the evaluation split, or use `compute_protocol_score` as a publication-grade selector.
- `linked_adr`: `documentation/redisgn_v2/deep_research_report_integration.md`

## 2026-04-28 (Keep The CFP Draft Conceptual But Soften Overclaims)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Preserve the AI&Learning2026 submission as a conceptual contribution centered on persistent markers, while softening novelty, determinism, and AI Act claims before submission.
- `rationale`: The draft fits the CFP well and has a distinctive mechanism, but its credibility depends on avoiding empirical or legal overreach before the associated experimental program is fully published.
- `alternatives_rejected`: Rewrite it as an empirical performance paper, broaden it into generic AI governance, or leave strong claims such as "inédit" and unconditional AI Act alignment untouched.
- `linked_adr`: `documentation/cfp_ailearning2026/abstract_etendu.md`

## 2026-04-27 (Use Yan 2026 To Anchor The AI&Learning Submission)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Frame the AI&Learning2026 submission around stigmergic markers as a hybrid organizational learning medium, anchored in Yan, Husted, and Fath's exploration/exploitation hybridization argument.
- `rationale`: The CFP explicitly foregrounds organizational learning with AI, exploration, exploitation, and hybridization. Persistent markers provide a concrete mechanism for collective memory, traceability, reinforcement, decay, and governance, making the contribution more distinctive than a generic agentic-AI discussion.
- `alternatives_rejected`: Center the submission on benchmark performance, broad AI governance, or generic human-AI collaboration without a concrete stigmergic learning mechanism.
- `linked_adr`: `https://easychair.org/cfp/AI-Learning-2026`

## 2026-04-27 (Adopt Evaluator-First Framing For Any From-Scratch Redesign)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: If redesigning from scratch, frame StigmergiAgentic as an evaluator-first, patch-first experimental system before treating it as an adaptive multi-agent colony.
- `rationale`: The second Deep Research report correctly identifies that the project risk is not lack of agent ideas, but adding adaptive mechanisms before the official evaluator, patch contract, baselines, campaign artifacts, and split-aware knowledge boundaries are stable.
- `alternatives_rejected`: Start with a richer V7 colony runtime, keep domain adapters as intelligence-heavy planners, or allow cross-run skills/protocols to mutate final-eval behavior without an offline split-aware knowledge plane.
- `linked_adr`: `/Users/lotfi/Downloads/deep-research-report (2).md`

## 2026-04-27 (Use a Short Handoff To Drive MigrationBench Implementation)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Add a concise MigrationBench implementation handoff alongside the long scientific plan, and instruct implementation agents to start from the handoff while treating the master plan as the research authority.
- `rationale`: The master plan is intentionally detailed and scientifically grounded, but it is too long for a focused implementation pass. A handoff file preserves the key constraints: evaluator-first order, mandatory baselines, cross-run disabled, strict output contract, and V6 static before V7.
- `alternatives_rejected`: Ask the next agent to infer implementation order from the full plan, start directly with V7 runtime changes, or optimize prompts before the MigrationBench evaluator and artifact contract are stable.
- `linked_adr`: `documentation/redisgn_v2/migrationbench_implementation_handoff.md`

## 2026-04-27 (Harden Main30 Around DeepSeek And Official MigrationBench Semantics)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Switch the MigrationBench primary model to DeepSeek direct API `deepseek-v4-flash` and harden `main_30` around official preflight, official SD-Feedback where possible, manifest-driven denominators, clean workspace isolation, harness-computed patches, and explicit power-analysis limits.
- `rationale`: A two-day `main_30` can produce a credible pilot/memoir result only if model capability, evaluator reproducibility, baseline strength, patch validity, and denominator semantics are locked before implementation. Gemma risks all arms failing; a naive agentless baseline risks becoming a strawman; and `n=30` cannot prove small effects.
- `alternatives_rejected`: Keep Gemma as primary, imitate SD-Feedback without trying the official baseline, infer denominators from output files, allow raw LLM diffs, reuse dirty workspaces, or present `main_30` as powered proof of 5-10 point gains.
- `linked_adr`: `documentation/redisgn_v2/migrationbench_implementation_handoff.md`

## 2026-04-27 (Require Deterministic Limits And Provider-Accurate DeepSeek Requests)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Add deterministic per-instance campaign limits, standardize typed edit primitives, timebox official SD-Feedback integration to one engineering day, and update the DeepSeek client path so `deepseek-v4-flash` pricing and non-thinking mode are actually enforced.
- `rationale`: Provider maximum output tokens are useful for code migration, but without hard per-instance caps a bad repair loop can invalidate cost/runtime comparisons and waste budget. A shared edit schema prevents baseline-specific patch noise, and YAML reasoning settings are not scientifically meaningful unless the client sends the provider's documented request fields.
- `alternatives_rejected`: Use an LLM-as-judge as the primary kill switch, let each baseline invent its own edit format, keep trying official SD-Feedback indefinitely, or rely on `reasoning.mode` documentation without client support.
- `linked_adr`: `documentation/redisgn_v2/migrationbench_implementation_handoff.md`

## 2026-04-27 (Run Main30 In Monitor-Only Mode Without Per-Instance Hard Caps)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Remove hard `main_30` per-instance caps for tokens, runtime, LLM calls, and repair cycles, and replace them with explicit `monitor_only` telemetry plus manual abort support.
- `rationale`: The primary research risk is now under-observing stigmergic repair behavior rather than API cost. DeepSeek token pricing is low enough that a high-token run can be allowed, as long as cost/runtime/call/cycle telemetry is preserved and manually aborted runs remain full-denominator failures unless rerun cleanly.
- `alternatives_rejected`: Keep a 500K token cap, cap runtime at 1800 seconds, stop after fixed repair cycles, or use an LLM-as-judge to automatically terminate runs.
- `linked_adr`: `documentation/redisgn_v2/migrationbench_implementation_handoff.md`

## 2026-04-27 (Implement MigrationBench V6 Static Before Any V7/C3 Work)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Implement the MigrationBench track as a patch-first V6 static harness with official preflight, clean workspace isolation, shared typed edits, strong baseline hooks, manifest-driven runners, and strict output contracts before adding V7 elastic colony or C3 mechanisms.
- `rationale`: The next scientific risk is invalid measurement, not insufficient architectural ambition. A stable harness makes failures attributable to migration strategy or orchestration rather than dirty workspaces, malformed diffs, missing outputs, or denominator drift.
- `alternatives_rejected`: Start with V7 dynamic agents, repair integrated C3 first, optimize prompts before official evaluator compatibility, or let each baseline define its own patch format.
- `linked_adr`: `documentation/redisgn_v2/migrationbench_implementation_handoff.md`

## 2026-04-28 (Use Robust Compose Commands For MigrationBench Services)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Run MigrationBench Docker services with exec-form command blocks, escaped container environment variables, and explicit `/opt/venv/bin/python`.
- `rationale`: Folded shell commands dropped Python script arguments, host-side Compose interpolation could erase container defaults, and `bash -lc` reset `PATH` enough to bypass the installed virtualenv. Explicit command wiring keeps preflight and campaign launches reproducible.
- `alternatives_rejected`: Keep folded `bash -c` strings, rely on host-exported variables, or depend on shell PATH resolution for the Python interpreter.
- `linked_adr`: `docker-compose.campaign.yml`

## 2026-04-28 (Gate MigrationBench Preflight On Evaluator Process Health)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Treat official evaluator process execution as the Docker preflight gate, while keeping unmigrated-base success as a separate diagnostic field.
- `rationale`: The smoke repos can clone, checkout, import MigrationBench, and run Maven through the official evaluator, but unmigrated repositories are not expected to satisfy the final Java migration contract. Conflating those two signals would incorrectly block scientifically valid campaign execution.
- `alternatives_rejected`: Require `official_base_java8_success=True` before running campaigns, ignore official evaluator dependency failures, or hide base success diagnostics entirely.
- `linked_adr`: `scripts/run_migrationbench_official_preflight.py`

## 2026-04-28 (Run MigrationBench Campaigns From Immutable Docker Image Code)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Remove repository source/config bind mounts from MigrationBench Docker services and require image rebuilds before smoke/full campaign execution.
- `rationale`: Docker Desktop bind mounts from the macOS workspace produced `Errno 35 Resource deadlock avoided` while reading YAML configs. Copying code/config into the image at build time improves reproducibility and avoids host filesystem locking artifacts during benchmark runs.
- `alternatives_rejected`: Keep source/config bind mounts for faster iteration, retry the same failing container, or work around the error with ad hoc local file copies.
- `linked_adr`: `docker-compose.campaign.yml`

## 2026-04-29 (Force Clean Workspaces For MigrationBench Main Campaigns)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Default MigrationBench Docker campaigns to `MIGRATION_FORCE=true` so each instance workspace is recreated before execution.
- `rationale`: A `no_change` arm produced one delivered artifact despite all rows being classified as `empty_patch`, proving stale workspace contamination. Clean workspaces are more important than resume speed for publication-grade patch benchmarks.
- `alternatives_rejected`: Continue the partial `main_30_clean` run, rely on users to remember `--force`, or accept nonzero artifact delivery in `no_change`.
- `linked_adr`: `docker-compose.campaign.yml`

## 2026-04-29 (Make No-Change Baseline Emit Explicit Empty Patch)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: The MigrationBench `no_change` baseline must write an explicit empty patch and explicit `patch_delivered=false` stats instead of exporting `git diff`.
- `rationale`: One repository produced a non-empty workspace diff with no intended changes, which made artifact delivery nonzero while the failure reason remained `empty_patch`. A no-op control must be semantically empty independent of checkout normalization.
- `alternatives_rejected`: Continue using `workspace.export_patch`, patch the aggregator to hide the inconsistency, or accept the `no_change` arm with nonzero artifact delivery.
- `linked_adr`: `adapters/migrationbench/scientific_baselines.py`

## 2026-04-29 (Use 1800s Per-Instance Timeout For MigrationBench Main30)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Add an explicit per-instance timeout to MigrationBench campaigns and default `main_30` Docker runs to `1800` seconds per instance.
- `rationale`: `main_30_clean_v3` stalled on one `solo_direct` instance without an active timeout. A 300-second cap would be too aggressive because one legitimate official-eval path already took about 620 seconds; 1800 seconds bounds pathological hangs while preserving room for Maven/LLM/stigmergic execution.
- `alternatives_rejected`: Leave timeout unset, use a universal 300-second hard cap, or rely on provider request timeouts alone.
- `linked_adr`: `scripts/run_migrationbench_framework_benchmark.py`

## 2026-04-29 (Filter MigrationBench Final Results To Task Contract Markers)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: MigrationBench stigmergic evaluation must select only `task` markers ending in `::finalize_patch` that contain the benchmark contract field `strict_success`.
- `rationale`: A successful instance created both a final task marker and a lesson marker whose ID also ended in `::finalize_patch`; suffix-only selection exported the lesson as a benchmark row, corrupting the `stigmergic_v6_static` aggregate.
- `alternatives_rejected`: Interpret the corrupted aggregate, post-process `runs.json` manually, or disable lesson creation globally for MigrationBench.
- `linked_adr`: `adapters/migrationbench/adapter.py`

## 2026-04-29 (Rebuild MigrationBench From Minimal No-Cache Context)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Clear MigrationBench scratch workspaces and rebuild the campaign image without cache from a minimal temporary context when Docker Desktop stalls on the full repository context.
- `rationale`: The rerun needed fresh checkouts after a result-extraction fix, but the workspace scratch had grown to about 11GB and Docker Desktop repeatedly stalled while loading the full repository context. A minimal build context preserves reproducibility while avoiding irrelevant cached workspaces, external clones, and host filesystem artifacts.
- `alternatives_rejected`: Reuse the existing image, rerun with stale workspaces, keep forcing Compose to build from the full repository context, or delete all Docker images/volumes with an aggressive system prune.
- `linked_adr`: `.dockerignore`

## 2026-04-29 (Treat No-Cache Stigmergic Main30 As Valid Negative Result)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Interpret `main_30_stigmergic_fixed_nocache/stigmergic_v6_static` as a completed, denominator-valid, negative result for the V6 static stigmergic arm.
- `rationale`: The Docker run exited successfully, produced 30 rows for 30 requested instances, and preserved the expected benchmark artifacts. The failure is in the artifact funnel: 29/30 delivered, 27/30 applied, but 0/30 passed official evaluation, so this is not a cache, timeout, or result-extraction failure.
- `alternatives_rejected`: Discard the run because success is zero, merge it with the previous corrupted stigmergic aggregate, or relaunch again before comparing against the already valid baselines.
- `linked_adr`: `campaign_results/migrationbench/main_30_stigmergic_fixed_nocache/stigmergic_v6_static/benchmark_summary.json`

## 2026-04-30 (Require Build-Feedback Repair Before Claiming Migration Stigmergy)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Do not treat the current V6 static MigrationBench adapter as a strong stigmergic implementation until patch proposal is coupled to build/test feedback and repair markers.
- `rationale`: The current graph inspects, proposes, runs build, and finalizes, but finalization only depends on the patch proposal and the build result does not drive revised edits. This makes the arm behave like a shallow patch generator with telemetry rather than an adaptive migration system.
- `alternatives_rejected`: Explain 0/30 only as benchmark difficulty, rerun the same adapter unchanged, or claim stigmergic value from patch delivery/applicability without official success.
- `linked_adr`: `adapters/migrationbench/adapter.py`

## 2026-04-30 (Add MigrationBench V7 Repair Colony As Opt-In Arm)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Add `stigmergic_v7_repair_colony` as a separate MigrationBench-first framework arm instead of mutating `stigmergic_v6_static`.
- `rationale`: V7 changes the scientific treatment from one-shot patch generation to closed-loop branch repair with elastic agents. Keeping it opt-in preserves V6 as a negative baseline and makes ablations easier to interpret.
- `alternatives_rejected`: Patch V6 in place, revive C3 as the main architecture, or add repair logic only inside prompts without marker-level control flow.
- `linked_adr`: `config/migrationbench_v7_repair_colony_deepseek.yaml`

## 2026-05-04 (Phase 5 V10 — Harden BranchingRepair A3 With Auditable Selection)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Push signature dedup, repeated-failure suppression, and the explainable `SelectionRationale` into `core_v10/strategy_runner.py` and propagate them through `scripts/bench/telemetry.py`. Add `scripts/bench/compare_strategies.py` to run A1/A2/A3 on the same fixture and emit `comparison.json`.
- `rationale`: Phase 5 DoD requires "selection explicable par preuves" and "comparaison A1/A2/A3". Putting dedup+rationale in the runner means every adapter (toy, MigrationBench, future) inherits Phase 5 for free, the EventLog stays the single source of truth (live==replay invariant preserved), and ablations are reproducible without bespoke wrappers.
- `alternatives_rejected`: External wrapper around the runner (would split the EventLog actor identity); keep selection implicit through `HypothesisGraph.select_best` only (no audit trail); block Phase 5 until Phase 3 typed-blackboard ships (would gate scientific deliverables on unrelated Phase-3 work — chose to land A2 as a linear-repair placeholder instead).
- `linked_adr`: `documentation/decisions/20260504-phase5-a3-branching-repair.md`

## 2026-05-04 (Do Not Treat A1/A2/A3 main_30 As Framework Evidence Yet)

- `repo_slug`: `stigmergiagentic-33b989`
- `decision`: Treat `campaign_results/v10/ablation_main30/comparison.json` as a harness-valid but treatment-invalid diagnostic run until candidate generation, repair generation, and branching activation are implemented and measured.
- `rationale`: A2 and A3 used a no-op repair provider and the same deterministic single-candidate POM provider as A1; A3 produced no fan-out, no dedup, and no repeat-failure suppression. The zero strict-success result is therefore not an interpretable comparison of repair or stigmergic coordination.
- `alternatives_rejected`: Promote the run as Phase 6-ready evidence, tune prompts on top of the current no-op repair loop, or explain the zero result as only benchmark difficulty without checking mechanism activation.
- `linked_adr`: `campaign_results/v10/ablation_main30/comparison.json`
