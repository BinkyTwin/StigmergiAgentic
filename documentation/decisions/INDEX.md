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

**Dernière mise à jour** : 2026-03-04
