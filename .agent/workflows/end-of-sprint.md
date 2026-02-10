---
description: Checklist complète pour la fin de sprint
---

# Fin de Sprint - Checklist pour Agents

Cette checklist doit être suivie **systématiquement** à la fin de chaque sprint, avant de committer et pousser vos changements.

## ✅ Phase 1 : Validation du Code

### Tests
- [ ] Tous les tests unitaires passent : `uv run pytest tests/ -v`
- [ ] La couverture de code est maintenue/améliorée : `uv run pytest tests/ --cov`
- [ ] Les tests d'intégration passent (si applicable)
- [ ] Aucun test n'a été désactivé sans justification documentée

### Qualité du Code
- [ ] Le code respecte PEP 8 : `ruff check .`
- [ ] Le formatage est correct : `black --check .`
- [ ] Les type hints sont présents : `mypy agents/ environment/ stigmergy/` (si configuré)
- [ ] Aucun warning critique dans les logs

### Vérifications Fonctionnelles
- [ ] Le code implémente bien les spécifications de `consigne/plan_poc_stigmergique.md`
- [ ] Les agents suivent le pattern `perceive → should_act → decide → execute → deposit`
- [ ] Aucune communication directe entre agents (seulement via pheromones)
- [ ] Les guardrails sont respectés (token budget, anti-loop, etc.)

## 📝 Phase 2 : Documentation

### Fichiers à Mettre à Jour

- [ ] **construction_log.md** : ajouter résumé du sprint
  ```bash
  # Ajouter à documentation/construction_log.md
  ## Sprint [DATE]
  ### Fonctionnalités développées
  - [liste]
  
  ### Challenges rencontrés
  - [liste]
  
  ### Décisions techniques
  - [liste]
  ```

- [ ] **AGENTS.md** : mettre à jour si changements architecturaux
  - Architecture modifiée ?
  - Nouveaux agents ou pheromones ?
  - Nouvelles commandes ?
  - Nouvelles dépendances ?

- [ ] **Code comments** : docstrings ajoutées pour nouveaux modules/fonctions

- [ ] **decisions/** : documenter décisions techniques importantes si applicable

### Vérification
- [ ] Aucun TODO critique non résolu dans le code
- [ ] Les commentaires sont en anglais et clairs
- [ ] Les noms de variables sont descriptifs et conformes aux conventions

## 🔧 Phase 3 : Commits Git

### Préparation
- [ ] Exécuter le script de fin de sprint : `./scripts/sprint_end.sh`
- [ ] Vérifier l'état Git : `git status`
- [ ] Vérifier que vous êtes sur la bonne branche (PAS main !) : `git branch --show-current`

### Commits Atomiques

**Format obligatoire :**
```
<type>(<scope>): <description courte en anglais>

[corps optionnel avec détails]

[footer: références]
```

**Types autorisés :**
- `feat` : nouvelle fonctionnalité
- `fix` : correction de bug
- `docs` : documentation uniquement
- `test` : tests uniquement
- `refactor` : refactoring sans changement de comportement
- `chore` : tâches diverses (deps, config)

**Scopes pour ce projet :**
- `scout`, `transformer`, `tester`, `validator` (agents)
- `pheromone`, `guardrails`, `decay` (environment)
- `metrics`, `loop`, `config` (système)
- `thesis`, `architecture` (documentation)

**Exemples :**
```bash
git add agents/scout_agent.py
git commit -m "feat(scout): implement AST-based pattern detection for print statements"

git add tests/test_scout.py
git commit -m "test(scout): add unit tests for pattern detection"

git add documentation/construction_log.md
git commit -m "docs(thesis): add sprint summary for 2026-02-10"
```

### Checklist Commits
- [ ] Commits logiquement séparés (un commit = une unité logique)
- [ ] Message de commit suit la convention
- [ ] Pas de `git add .` (sélection manuelle des fichiers)
- [ ] Chaque commit compile et les tests passent

## 🔄 Phase 4 : Synchronisation

### Mise à Jour
- [ ] Récupérer les dernières modifications : `git fetch origin`
- [ ] Rebaser sur develop : `git rebase origin/develop`
- [ ] Résoudre les conflits si nécessaire
  ```bash
  # En cas de conflit
  git status  # voir les fichiers en conflit
  # Éditer les fichiers manuellement
  git add <fichiers_résolus>
  git rebase --continue
  ```
- [ ] Vérifier que les tests passent toujours après rebase

### Push
- [ ] Pousser la branche : `git push origin <nom-branche>`
- [ ] Si force push nécessaire après rebase : `git push --force-with-lease origin <nom-branche>`

## 📄 Phase 5 : Pull Request

### Créer la PR sur GitHub
- [ ] Créer PR vers `develop` (jamais vers `main` directement)
- [ ] Titre clair et descriptif
- [ ] Remplir le template de PR (voir `.github/PULL_REQUEST_TEMPLATE.md`)
- [ ] Lier les issues pertinentes
- [ ] Ajouter des labels appropriés (feature, bugfix, docs, etc.)

### Contenu de la PR
- [ ] Description complète des changements
- [ ] Screenshots/exemples si applicable
- [ ] Notes sur les décisions techniques
- [ ] Liste des TODOs futurs identifiés
- [ ] Références aux specs dans `consigne/`

## 🎯 Phase 6 : Vérifications Finales

### Avant de Marquer "Ready for Review"
- [ ] Relire son propre code sur GitHub (vue diff)
- [ ] Vérifier qu'aucun fichier de config local n'est commité (.env, etc.)
- [ ] Vérifier qu'aucun code de debug n'est laissé (print, debugger, etc.)
- [ ] Vérifier que requirements.txt est à jour si nouvelles dépendances

### Auto-Review
- [ ] Le code respecte les principes de stigmergy (pas de couplage direct)
- [ ] Les pheromones sont bien utilisées pour la coordination
- [ ] Les guardrails sont respectés
- [ ] Le code est testable et testé

## 📊 Métriques à Vérifier

- [ ] Token usage reste dans le budget : vérifier logs
- [ ] Nombre de retry < 3 par fichier
- [ ] Confidence scores cohérents pour les validations
- [ ] Temps d'exécution raisonnable

## ⚠️ Points de Blocage Fréquents

**Si les tests échouent :**
- Vérifier les dépendances : `uv pip list`
- Vérifier les variables d'environnement
- Lancer en mode debug : `pytest -v --pdb`

**Si conflit Git :**
- Ne jamais forcer sans comprendre
- Consulter l'historique : `git log --oneline --graph`
- Demander review si incertain

**Si documentation incomplète :**
- Retour à Phase 2, ne pas skipper
- Documentation = partie intégrante du livrable pour le mémoire

## ✨ Checklist Rapide (TL;DR)

```bash
# 1. Tests
uv run pytest tests/ -v --cov

# 2. Quality
ruff check .
black .

# 3. Script auto
./scripts/sprint_end.sh

# 4. Review changes
git status
git diff

# 5. Commit par unité logique
git add <files>
git commit -m "type(scope): message"

# 6. Sync
git fetch origin
git rebase origin/develop

# 7. Push
git push origin <branch>

# 8. PR sur GitHub
```

## 🎓 Pour le Mémoire

**N'oubliez pas :** Ce projet est un POC pour un mémoire de Master. La documentation est aussi importante que le code.

- Chaque décision technique doit être documentée
- Les expérimentations doivent être traçables
- Les metrics doivent être exportables
- L'audit log doit être complet

---

**Dernière mise à jour :** 2026-02-10
