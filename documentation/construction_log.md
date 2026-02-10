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

## Instructions pour les Futures Entrées

À chaque session de développement :
1. Copier le format ci-dessus
2. Remplir tous les champs (même si certains sont vides, le marquer explicitement)
3. Être **précis** et **factuel** — cette documentation sera lue par un jury académique
4. Ajouter des références aux fichiers modifiés avec chemins relatifs à la racine du projet
5. Documenter **pourquoi** pas seulement **quoi** — le raisonnement est essentiel pour un mémoire

---

**Rappel** : Cette documentation doit demonstrer la **rigueur scientifique** de la démarche, même avec l'assistance de l'IA.
