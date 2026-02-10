# Documentation du POC — Orchestration Stigmergique Multi-Agents

Cette documentation trace l'ensemble du processus de construction du POC pour le mémoire de Master EMLV. Comme le développement est réalisé majoritairement avec l'assistance d'IA (Claude Code et GitHub Copilot), cette documentation servira d'**annexe technique** démontrant la rigueur méthodologique et les choix architecturaux.

## Structure de la Documentation

### 📝 Journaux de Construction

- **[construction_log.md](construction_log.md)** — Chronologie détaillée de toutes les actions de développement
- **[technical_notes.md](technical_notes.md)** — Notes techniques, découvertes, et problèmes résolus

### 🎯 Décisions Architecturales

Le dossier `decisions/` contient les ADR (Architecture Decision Records) :
- Format : `YYYYMMDD-titre-decision.md`
- Chaque ADR documente : contexte, alternatives considérées, décision, conséquences

### 📊 Captures et Diagrammes

Le dossier `screenshots/` contient :
- Captures d'écran de l'exécution du système
- Graphiques de métriques générés
- Diagrammes d'architecture (Mermaid exports)

## Guide d'Utilisation pour les Assistants IA

### Pour Claude Code

Lors de chaque session de travail :
1. **Avant de coder** : Lire `construction_log.md` pour comprendre l'état actuel
2. **Pendant le développement** : Ajouter une entrée dans `construction_log.md` avec :
   - Date et heure
   - Objectif de la session
   - Actions effectuées
   - Décisions prises
3. **Pour les décisions importantes** : Créer un ADR dans `decisions/`
4. **En cas de problème résolu** : Documenter dans `technical_notes.md`

### Pour GitHub Copilot

Référence rapide des patterns stigmergiques :
- Voir `technical_notes.md` pour les patterns de code récurrents
- Consulter les ADRs pour comprendre les choix architecturaux
- Respecter la structure documentée dans `../AGENTS.md`

## Principe de Documentation Continue

> **Règle d'or** : Chaque modification significative du code doit être accompagnée d'une mise à jour de la documentation.

Cela garantit :
- ✅ Traçabilité complète pour le jury du mémoire
- ✅ Compréhension du raisonnement derrière chaque choix
- ✅ Reproductibilité des expérimentations
- ✅ Conformité avec les exigences académiques

## Liens Rapides

- [Plan d'architecture POC](../consigne/plan_poc_stigmergique.md)
- [Guide Claude](../CLAUDE.md)
- [Guide Copilot/Codex](../AGENTS.md)
- [Code source principal](../main.py)
- [Tests](../tests/)

---

**Dernière mise à jour** : 2026-02-09  
**Auteur** : Lotfi (avec assistance IA Claude Code & GitHub Copilot)
