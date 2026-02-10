# Journal de Construction du POC

Ce document trace chronologiquement toutes les étapes de développement du POC d'orchestration stigmergique.

## Format des Entrées

Chaque entrée suit ce format :

```markdown
### YYYY-MM-DD HH:MM — Titre de la Session

**Assistant IA utilisé** : Claude Code / GitHub Copilot / Autre

**Objectif** : Description concise de ce qui doit être accompli

**Actions effectuées** :
- Action 1
- Action 2
- ...

**Décisions prises** :
- Décision 1 (avec justification)
- Décision 2 (avec justification)

**Problèmes rencontrés** :
- Problème 1 → Solution appliquée
- Problème 2 → Solution appliquée

**Résultat** : État final de la session (succès / partiel / échec)

**Fichiers modifiés** :
- `chemin/fichier1.py` — Description de la modification
- `chemin/fichier2.py` — Description de la modification

---
```

## Log des Sessions

### 2026-02-09 16:10 — Mise en Place de la Documentation

**Assistant IA utilisé** : Claude Code (Antigravity)

**Objectif** : Créer une structure de documentation complète pour le POC qui servira d'annexe au mémoire

**Actions effectuées** :
- Création du dossier `documentation/` avec sous-dossiers `decisions/` et `screenshots/`
- Création de `AGENTS.md` basé sur `CLAUDE.md` pour guider GitHub Copilot
- Création de `documentation/README.md` expliquant la structure
- Création de ce journal de construction (`construction_log.md`)
- Création de `technical_notes.md` pour les notes techniques
- Création du template ADR dans `decisions/`

**Décisions prises** :
- Adopter le format ADR (Architecture Decision Records) pour documenter les décisions importantes
- Structurer la documentation en 3 axes : chronologie (construction_log), décisions (ADRs), notes techniques
- Maintenir deux fichiers de guidance : `CLAUDE.md` pour Claude Code et `AGENTS.md` pour Copilot/Codex

**Résultat** : Structure complète de documentation mise en place

**Fichiers créés** :
- `AGENTS.md` — Guide pour GitHub Copilot/Codex
- `documentation/README.md` — Vue d'ensemble de la documentation
- `documentation/construction_log.md` — Ce fichier
- `documentation/technical_notes.md` — Notes techniques
- `documentation/decisions/TEMPLATE_ADR.md` — Template pour les ADRs

---

### 2026-02-10 15:55 — Sprint 1 Environment Bootstrap and Core Medium

**Assistant IA utilisé** : Codex (GPT-5.3 codex)

**Objectif** : Implémenter Sprint 1 de bout en bout (environment store + decay + guardrails + tests) avec exécution standardisée via `uv` et Python 3.11

**Actions effectuées** :
- Création de la branche `codex/sprint1-environment`
- Bootstrap de l'environnement local avec `uv` (`uv python install 3.11`, `uv venv`, `uv pip install -r requirements.txt`)
- Création des modules `environment/decay.py`, `environment/guardrails.py`, `environment/pheromone_store.py`
- Création de `stigmergy/config.yaml` avec la configuration complète section 4.9
- Mise en place des tests Sprint 1 (`tests/test_pheromone_store.py`, `tests/test_guardrails.py`)
- Ajout d'un bootstrap de path pour pytest (`tests/conftest.py`)
- Validation locale des commandes de test via `uv run pytest` (deux exécutions reproductibles)
- Mise à jour des guides `AGENTS.md` et `CLAUDE.md` pour inclure le workflow `uv`
- Ajout d'un ADR Sprint 1 et mise à jour de l'index des ADRs

**Décisions prises** :
- Standardiser toutes les commandes Python/tests sur `uv run` pour reproductibilité locale
- Implémenter un pheromone store JSON avec verrouillage POSIX (`fcntl.flock`) + audit trail append-only
- Garder `requirements.txt` comme source de vérité Sprint 1 (pas de migration `pyproject.toml` à ce stade)

**Problèmes rencontrés** :
- `ModuleNotFoundError: environment` lors de la collecte pytest → Ajout de `tests/conftest.py` pour injecter la racine du repo dans `sys.path`

**Résultat** : Sprint 1 implémenté et validé localement (tests verts)

**Fichiers modifiés** :
- `environment/pheromone_store.py` — CRUD JSON, query filters, locking, audit trail, decay
- `environment/guardrails.py` — Budget guardrail, anti-loop, scope lock, TTL, trace stamping
- `environment/decay.py` — Decay exponentiel/linéaire et inhibition gamma
- `stigmergy/config.yaml` — Paramètres initiaux complets
- `tests/test_pheromone_store.py` — Tests unitaires/intégration ciblée du store
- `tests/test_guardrails.py` — Tests des contraintes guardrails
- `tests/conftest.py` — Bootstrap import path pytest
- `.gitignore` / `.env.example` / `requirements.txt` — Fichiers d'infrastructure Sprint 1
- `AGENTS.md` / `CLAUDE.md` — Mise à jour des commandes en mode `uv`
- `documentation/decisions/20260210-sprint1-environment-medium.md` — ADR Sprint 1

---

## Instructions pour les Futures Entrées

À chaque session de développement :
1. Copier le format ci-dessus
2. Remplir tous les champs (même si certains sont vides, le marquer explicitement)
3. Être **précis** et **factuel** — cette documentation sera lue par un jury académique
4. Ajouter des références aux fichiers modifiés avec chemins relatifs à la racine du projet
5. Documenter **pourquoi** pas seulement **quoi** — le raisonnement est essentiel pour un mémoire

---

**Rappel** : Cette documentation doit demonstrer la **rigueur scientifique** de la démarche, même avec l'assistance de l'IA.
