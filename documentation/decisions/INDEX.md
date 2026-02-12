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

**Dernière mise à jour** : 2026-02-12
