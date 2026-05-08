# Index des ADRs (Architecture Decision Records)

Cet index liste toutes les décisions architecturales prises durant le développement du POC.

## Format de Nommage

Les ADRs suivent le format : `YYYYMMDD-titre-court.md`

## Liste des ADRs

| # | Date | Titre | Statut | Décision |
|---|------|-------|--------|----------|
| 001 | 2026-02-09 | [Template ADR](TEMPLATE_ADR.md) | Accepté | Template de base pour tous les ADRs futurs |
| 002 | 2026-02-10 | [Sprint 1 Environment Medium and Runtime Standardization](20260210-sprint1-environment-medium.md) | Accepté | JSON store + POSIX locking + append-only audit + uv runtime |
| 003 | 2026-02-11 | [Sprint 2 Agent Layer, LLM Client, and Synthetic Fixture Strategy](20260210-sprint2-agents-unitaires.md) | Accepté | Agents unitaires + client LLM + fixtures versionnées + tests mock-first |
| 004 | 2026-02-12 | [Sprint 2.5 Docker Infrastructure for Tests & Migrations](20260212-sprint2.5-docker-infrastructure.md) | Accepté | Docker multi-stage + docker-compose + Makefile pour exécution reproductible |
| 005 | 2026-02-12 | [Sprint 3 Full Orchestration Loop with Blocking Gate on docopt/docopt@0.6.2](20260212-sprint3-loop-gating-docopt.md) | Accepté | Loop/CLI/metrics Sprint 3 + fallback adaptatif + gate bloquant local/Docker validé |
| 006 | 2026-02-12 | [Sprint 3 LLM Cost Budgeting with Uncapped Output Tokens](20260212-sprint3-llm-cost-budget-and-uncapped-output.md) | Accepté | Suppression du cap output dur + budget USD optionnel basé sur pricing OpenRouter et usage réel |
| 007 | 2026-02-26 | [Sprint 1 V2 Core Reset and SQLite Marker Store](20260226-sprint1-v2-core-reset-and-sqlite-marker-store.md) | Accepté | Hard reset runtime V0.1 + core générique V2 (Marker, MarkerStore WAL, Guardrails, Audit, Config, 31 tests) |
| 008 | 2026-02-26 | [Sprint 2 V2 Generic Agent Runtime (Pressure + Orchestrator)](20260226-sprint2-v2-agent-orchestrator-runtime.md) | Accepté | Runtime générique Sprint 2 (tool registry, pressure model, environment, agent, orchestrator async/sync, port LLM client, 61 tests unitaires) |
| 009 | 2026-02-26 | [Sprint 3 V2 Infrastructure Tools and Assistant Mode](20260226-sprint3-v2-infrastructure-tools-and-assistant-mode.md) | Accepté | Ajout couche `tools/`, adaptateur assistant, CLI `main.py`, validation stricte config tools, 85 tests |
| 010 | 2026-03-04 | [Sprint 4 V3 Runtime Overhaul](20260304-sprint4-v3-runtime-overhaul.md) | Accepté | Async LLM structuré, DAG dépendances, renforcement, isolation de session, contexte workspace, 131 tests |
| 011 | 2026-03-04 | [Sprint 5 V3 Memory, Emergence, and Lesson Markers](20260304-sprint5-v3-memory-emergence-lessons.md) | Accepté | Mémoire agentique, métriques d’émergence, markers lesson, pressure heuristique, dashboard CLI, 168 tests |
| 012 | 2026-03-05 | [Sprint 6 V3 TravelPlanner Adapter and Programmatic Fidelity Evaluation](20260305-sprint6-travelplanner-adapter-and-fidelity-eval.md) | Accepté | Nettoyage legacy V0.1 + adaptateur TravelPlanner complet (workspace/tools/evaluator) + métriques paper-facing + intégration CLI + 209 tests |
| 013 | 2026-03-22 | [Sprint 6 V4 Stigmergic Corrections and Opt-In Runtime Adaptivity](20260322-sprint6-v4-stigmergic-corrections.md) | Accepté | Local sensing, temporal decay, frequentation, emergent contention resolution, and feedback adaptation added as opt-in runtime features with 235 tests |
| 014 | 2026-04-16 | [Sprint 7 V5-Full Execution Hardening](20260416-sprint7-v5-full-execution-hardening.md) | Accepté | TravelPlanner-side V5 execution improvements: marker shaping, train-only few-shots/tuning, V5 preset, and benchmark-runner subset alignment |
| 015 | 2026-04-18 | [Sprint 8 V6 General Runtime Controls and Targeted Repair](20260418-sprint8-v6-general-runtime-controls.md) | Accepté | Generic V6 phase-1 runtime controls: lock telemetry, unified recovery controller, stickiness, targeted repair contract, and frozen V6 ablation presets |
| 016 | 2026-04-21 | [Sprint 9 Groundwork for Persistent Skills, Protocol Artifacts, and Objective-Conditioned Protocol Compilation](20260421-sprint9-groundwork-persistent-skills-protocols-and-compiler.md) | Accepté | Add opt-in config/schema/prompt/runtime seams for Sprint 9 while preserving Sprint 8 behavior by default |
| 017 | 2026-04-21 | [Sprint 9 Full Implementation: Persistent Skills, Protocol Artifacts, and Cross-Run Coordination](20260421-sprint9-full-implementation-persistent-skills-protocols-and-cross-run-coordination.md) | Déprécié par ADR 018 | Complete C1/C2/C3 wiring: skill promotion, protocol persistence with baseline/latest/best slots, and cross-run config adaptation |
| 018 | 2026-05-03 | [Pivot V10 — Refonte from-scratch après invalidation de l'hypothèse fondatrice V3](20260503-pivot-v10-from-scratch.md) | Accepté | Création de `core_v10/` indépendant de `core/` legacy : EventLog + HypothesisGraph + Blackboard typé + Verifier multi-statut + ablations A0..A6 avec stigmergie au cœur (H2) avant MCTS ; archivage V3 sur `archive/v3-sprint9` |
| 019 | 2026-05-04 | [Phase 5 V10 — BranchingRepair A3, signature dedup, repeated-failure suppression, explainable selector](20260504-phase5-a3-branching-repair.md) | Accepté | Extension de `core_v10/strategy_runner.py` : `_SignatureTracker`, events `candidate.deduped` / `candidate.repeat_failure_suppressed` / `selection.completed`, dataclass `SelectionRationale`, propagation dans `scripts/bench/telemetry.py`, ablation harness `scripts/bench/compare_strategies.py` (A1/A2/A3), 10 nouveaux tests verts (136/136 V10) |
| 020 | 2026-05-05 | [Phase 6 V10 — StigmergicBlackboard A4](20260505-phase-6-stigmergic-blackboard-a4.md) | Accepté | Pré-enregistrement et livraison A4 : `SignalStore`, `signal.emitted`, `signal.applied`, feedback→signal policy, métriques `pheromone_hit_rate`, `feedback_reuse_rate`, `repeated_failure_suppression`, comparaison A3 vs A4 |
| 021 | 2026-05-06 | [V11 — Stigmergic Medium Kernel](20260506-v11-stigmergic-medium-kernel.md) | Accepté | Couche causale V11 au-dessus de V10 : `signal.read`, affordances, scheduler workers, `decision.influenced`, `trajectory.diverged`, operators typés B6, ladder B2/B5/B6, smoke automatisé et télémétrie replayable |
| 022 | 2026-05-07 | [V12 — Autonomous Agents over a Stigmergic Medium](20260507-v12-autonomous-agents-over-medium.md) | Accepté | Pivot V12 après dérive B6 : le médium guide sans patcher, l’agent LLM choisit tools+params, S2/V12 partagent les mêmes tools, `core_v12/` introduit ToolCall/ToolProposal/AgentLocalView/AgentLoop |
| 023 | 2026-05-08 | [V12.4 — Stigmergic SD-Feedback Agent](20260508-v12-4-stigmergic-sd-feedback-agent.md) | Accepté | SD-Feedback redevient la boucle de vérité : tools read-only, canal explicite `propose_patch`, verifier automatique, accept/revert au funnel, médium comme augmentation compacte du feedback |

---

## Instructions

Quand créer un ADR :
1. ✅ Choix d'architecture significatif (ex: structure des phéromones)
2. ✅ Décision de configuration critique (ex: thresholds)
3. ✅ Changement de dépendance majeure (ex: remplacer OpenRouter par un autre provider)
4. ✅ Décision impactant les résultats de recherche (ex: méthode de calcul de Pareto)

Quand NE PAS créer un ADR :
1. ❌ Corrections de bugs simples
2. ❌ Ajout de commentaires ou documentation
3. ❌ Refactoring sans changement de comportement
4. ❌ Mise à jour de dépendances mineures

---

**Dernière mise à jour** : 2026-05-08
