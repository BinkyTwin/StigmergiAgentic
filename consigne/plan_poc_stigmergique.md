# 🐜 Plan détaillé — POC Orchestration Stigmergique

**Projet** : Orchestration stigmergique de systèmes multi-agents LLM  
**Cas d'usage** : Migration Python 2 → Python 3  
**Auteur** : Abdelatif Djeddou — Mémoire EMLV  
**Date** : 8 février 2026  
**Provider LLM** : OpenRouter (pony-alpha pour le dev, modèle frontière pour les résultats finaux)

---

## 1. Vision d'ensemble

### 1.1 Ce qu'on construit

Un système où **4 agents LLM spécialisés** migrent automatiquement du code Python 2 vers Python 3, coordonnés **uniquement** via un environnement partagé (phéromones numériques). Aucun agent ne communique directement avec un autre. L'environnement (dépôt Git + fichiers JSON de phéromones) est le seul médium de coordination — c'est le principe stigmergique de Grassé (1959), opérationnalisé via le paradigme Agents & Artifacts de Ricci et al. (2007).

### 1.2 Ce qu'on veut prouver

| Question de recherche | Ce que le POC doit démontrer |
|---|---|
| **RQ1 — Mécanisme** | Les phéromones numériques (tâche, statut, qualité) suffisent à coordonner des agents LLM sans superviseur central |
| **RQ2 — Performance** | La coordination stigmergique atteint ou dépasse le baseline Agentless (Xia et al., 2024) sur un périmètre de migration Py2→Py3, avec un coût maîtrisé |
| **RQ3 — Gouvernance** | Les traces environnementales permettent l'auditabilité complète (tracking + tracing au sens de Santoni de Sio & van den Hoven, 2018) |

### 1.3 Architecture à 30 000 pieds

```
┌─────────────────────────────────────────────────────┐
│                 BOUCLE PRINCIPALE                    │
│            (round-robin, pas superviseur)            │
│                                                     │
│   ┌──────┐  ┌────────────┐  ┌────────┐  ┌────────┐ │
│   │Scout │  │Transformer │  │Tester  │  │Validator│ │
│   │  🔍  │  │     ⚡     │  │   🧪   │  │   ✅   │ │
│   └──┬───┘  └─────┬──────┘  └───┬────┘  └───┬────┘ │
│      │            │             │            │      │
│      ▼            ▼             ▼            ▼      │
│  ┌─────────────────────────────────────────────┐    │
│  │      ENVIRONNEMENT PARTAGÉ (médium)         │    │
│  │                                             │    │
│  │  📋 tasks.json     (phéromones de tâche)    │    │
│  │  🏷️ status.json    (phéromones de statut)   │    │
│  │  ⭐ quality.json   (phéromones de qualité)  │    │
│  │  📁 target_repo/   (code Git)               │    │
│  │  🛡️ guardrails.py  (contraintes env.)       │    │
│  └─────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────┘
```

**Principe fondamental** : chaque agent lit → décide → agit → dépose une trace. La trace stimule l'agent suivant. C'est la boucle action → trace → stimulus → action.

---

## 2. Structure du projet

```
stigmergic-poc/
│
├── agents/                     # Les 4 agents spécialisés
│   ├── __init__.py
│   ├── base_agent.py           # Classe abstraite commune
│   ├── scout.py                # Analyse codebase Py2
│   ├── transformer.py          # Génération code Py3
│   ├── tester.py               # Exécution tests
│   └── validator.py            # Validation + renforcement
│
├── environment/                # Le médium stigmergique
│   ├── __init__.py
│   ├── pheromone_store.py      # CRUD phéromones (JSON)
│   ├── guardrails.py           # Contraintes environnementales
│   └── decay.py                # Évaporation temporelle
│
├── stigmergy/                  # Orchestration
│   ├── __init__.py
│   ├── loop.py                 # Boucle principale round-robin
│   ├── config.yaml             # Paramètres (seuils, decay, budget)
│   └── llm_client.py           # Client OpenRouter unifié
│
├── target_repo/                # Dépôt Python 2 à migrer (Git)
│   └── (cloné dynamiquement)
│
├── pheromones/                 # Store de traces (versionné)
│   ├── tasks.json
│   ├── status.json
│   └── quality.json
│
├── metrics/                    # Collecte et analyse
│   ├── __init__.py
│   ├── collector.py            # Enregistrement par tick
│   ├── pareto.py               # Analyse coût-précision
│   └── export.py               # Export CSV pour analyse
│
├── baselines/                  # Comparaisons
│   ├── single_agent.py         # 1 seul agent fait tout
│   └── sequential.py           # Pipeline séquentiel (type Agentless)
│
├── tests/
│   ├── test_pheromone_store.py
│   ├── test_agents.py
│   ├── test_guardrails.py
│   └── test_migration.py
│
├── docs/
│   ├── architecture.md
│   └── pheromone_spec.md
│
├── requirements.txt
├── README.md
└── main.py                     # Point d'entrée
```

---

## 3. Spécification des phéromones

### 3.1 Phéromones de TÂCHE (quantitatives)

Déposées par le **Scout**. Indiquent les fichiers à migrer et leur priorité.

```json
{
  "file": "utils.py",
  "intensity": 0.87,
  "patterns_found": ["print_stmt", "dict_iteritems", "unicode_literals"],
  "pattern_count": 14,
  "dependencies": ["config.py", "helpers.py"],
  "dep_count": 3,
  "created_at": "2026-02-08T10:00:00Z",
  "created_by": "scout"
}
```

**Règle d'intensité** : `intensity = normalize(pattern_count × 0.6 + dep_count × 0.4)`  
**Évaporation** : `-0.05 par tick` si non traitée (incite à traiter vite les fichiers prioritaires)

### 3.2 Phéromones de STATUT (qualitatives)

Déposées par **chaque agent** après action. Marquent l'état du fichier dans le pipeline.

```json
{
  "file": "utils.py",
  "status": "transformed",
  "previous_status": "pending",
  "agent": "transformer",
  "timestamp": "2026-02-08T10:05:00Z",
  "metadata": {
    "tokens_used": 1240,
    "patterns_migrated": ["print_stmt", "dict_iteritems"],
    "diff_lines": 23
  }
}
```

**États possibles** : `pending → in_progress → transformed → tested → validated | failed → retry`

### 3.3 Phéromones de QUALITÉ (quantitatives)

Déposées par le **Tester** et renforcées/évaporées par le **Validator**.

```json
{
  "file": "utils.py",
  "confidence": 0.92,
  "tests_total": 18,
  "tests_passed": 17,
  "tests_failed": 1,
  "coverage": 0.78,
  "issues": ["test_unicode_handling: AssertionError"],
  "timestamp": "2026-02-08T10:08:00Z"
}
```

**Renforcement** : si tests passent → `confidence += 0.1` (plafonné à 1.0)  
**Évaporation** : si tests échouent → `confidence -= 0.2` et status → `retry`

---

## 4. Spécification des agents

### 4.1 Base Agent (classe abstraite)

Tous les agents partagent le même cycle :

```python
class BaseAgent:
    def perceive(self, pheromone_store) -> dict:
        """Lit les phéromones pertinentes (filtre par type/seuil)"""

    def should_act(self, perception) -> bool:
        """Décide s'il y a du travail à faire (seuil d'activation)"""

    def decide(self, perception) -> Action:
        """Appelle le LLM pour décider quoi faire"""

    def execute(self, action) -> Result:
        """Exécute l'action (modifier fichier, lancer test, etc.)"""

    def deposit(self, result, pheromone_store):
        """Dépose les traces dans l'environnement"""
```

### 4.2 Scout 🔍

| Propriété | Valeur |
|---|---|
| **Lit** | Structure du dépôt, imports, syntaxe Python 2 |
| **Seuil d'activation** | Fichiers `.py` sans phéromone de tâche existante |
| **Action** | Analyse AST + appel LLM pour identifier les patterns Py2 |
| **Dépose** | Phéromones de tâche (fichier, patterns, priorité) + statut `pending` |
| **Prompt LLM** | "Analyse ce fichier Python 2. Liste les patterns à migrer vers Python 3. Estime la complexité." |

### 4.3 Transformer ⚡

| Propriété | Valeur |
|---|---|
| **Lit** | Phéromones de tâche (triées par intensité décroissante), phéromones de qualité des fichiers similaires |
| **Seuil d'activation** | `task.intensity > 0.3` ET `status == "pending"` |
| **Action** | Appel LLM pour générer le code Python 3 |
| **Dépose** | Code transformé + diff + statut `transformed` + tokens consommés |
| **Prompt LLM** | "Migre ce fichier Python 2 vers Python 3. Patterns identifiés : {patterns}. Préserve la sémantique. Retourne le fichier complet." |
| **Apprentissage stigmergique** | Lit les phéromones de qualité des fichiers déjà validés pour ajuster sa stratégie (ex : un pattern qui réussit souvent → le reproduire) |

### 4.4 Tester 🧪

| Propriété | Valeur |
|---|---|
| **Lit** | Phéromones de statut `transformed` |
| **Seuil d'activation** | Au moins 1 fichier en statut `transformed` |
| **Action** | Exécute `pytest` sur le fichier transformé, vérifie la syntaxe Python 3 |
| **Dépose** | Phéromones de qualité (tests passés/échoués, coverage) + statut `tested` |
| **Pas d'appel LLM** | Cet agent est déterministe (exécution de tests). Optionnel : appel LLM pour diagnostiquer les échecs. |

### 4.5 Validator ✅

| Propriété | Valeur |
|---|---|
| **Lit** | Phéromones de qualité + statut `tested` |
| **Seuil d'activation** | `confidence > 0.8` pour validation directe, `confidence < 0.5` pour rollback, entre les deux → escalade humaine |
| **Action — Valide** | Git commit du fichier migré + renforcement phéromones (+0.1) + statut `validated` |
| **Action — Rollback** | Git revert + évaporation phéromones (-0.2) + statut `retry` |
| **Action — Escalade** | Marque le fichier pour review humaine + statut `needs_review` |
| **Dépose** | Log de validation + métriques de décision |

---

## 5. Guardrails (contraintes environnementales)

Implémentés dans `environment/guardrails.py`. L'agent ne connaît pas les règles — c'est l'environnement qui refuse ou accepte (Grisold et al., 2025).

| Guardrail | Type | Implémentation | Référence théorique |
|---|---|---|---|
| **Traçabilité** | Structurel | Chaque écriture dans pheromone_store est horodatée et signée par l'agent | Art. 14 EU AI Act (Fink, 2025) |
| **Budget tokens** | Plafond | `if total_tokens > config.max_tokens: terminated = True` | Kapoor et al. (2024) |
| **Rollback auto** | Validation | `if tests_failed > config.max_failures: git revert` | Xia et al. (2024) |
| **Escalade humaine** | HOTL | `if 0.5 < confidence < 0.8: status = "needs_review"` | Holmström et al. (2023) |
| **Anti-boucle** | Sécurité | `if retry_count > 3: skip + log` | Cursor (2025) leçons apprises |
| **Scope lock** | Concurrence | Un seul agent peut modifier un fichier à la fois (verrou simple) | Cursor (2025) |

---

## 6. Métriques et évaluation

### 6.1 Métriques collectées à chaque tick

| Métrique | Type | Objectif |
|---|---|---|
| `files_migrated` | Compteur | Progression |
| `files_validated` | Compteur | Taux de succès |
| `files_failed` | Compteur | Taux d'échec |
| `files_needs_review` | Compteur | Escalade humaine |
| `total_tokens` | Compteur | Coût |
| `total_ticks` | Compteur | Temps |
| `tokens_per_file` | Ratio | Efficacité |
| `success_rate` | Ratio | `validated / total` |
| `rollback_rate` | Ratio | `failed / (validated + failed)` |
| `human_escalation_rate` | Ratio | `needs_review / total` |

### 6.2 Comparaisons (baselines)

| Configuration | Description | Ce qu'on mesure |
|---|---|---|
| **Stigmergique (4 agents)** | Architecture complète du POC | Performance de référence |
| **Single-agent** | 1 seul agent fait scan + transform + test + validate | Est-ce que la coordination apporte quelque chose ? |
| **Séquentiel (Agentless-like)** | Pipeline fixe sans phéromones : scan → transform → test → validate | Surcoût de la stigmergie vs pipeline simple |
| **Hiérarchique** | 1 superviseur distribue les tâches aux 3 workers | Stigmergie vs command-and-control |

### 6.3 Analyse Pareto coût-précision

Pour chaque configuration : plot `(coût en tokens, taux de succès)` → identifier la frontière de Pareto (Kapoor et al., 2024). Si stigmergique est sur la frontière ou la domine, le mécanisme est justifié.

---

## 7. Plan de sprints

### Sprint 1 — Environnement (3 jours)

**Objectif** : le médium stigmergique fonctionne indépendamment des agents.

- [ ] `pheromone_store.py` : CRUD JSON (read, write, query par filtre)
- [ ] `decay.py` : mécanisme d'évaporation configurable (decay_rate par tick)
- [ ] `guardrails.py` : vérifications basiques (budget, anti-boucle, scope lock)
- [ ] `config.yaml` : paramètres initiaux (seuils, decay_rate, budget max)
- [ ] `tests/test_pheromone_store.py` : tests unitaires du store
- [ ] `tests/test_guardrails.py` : tests des contraintes

**Livrable** : un store de phéromones testable avec `pytest`, decay fonctionnel, guardrails actifs.

### Sprint 2 — Agents unitaires (4 jours)

**Objectif** : chaque agent fonctionne isolément avec l'environnement.

- [ ] `llm_client.py` : client OpenRouter (pony-alpha) avec retry et logging des tokens
- [ ] `base_agent.py` : classe abstraite avec le cycle perceive → should_act → decide → execute → deposit
- [ ] `scout.py` : scan d'un fichier Py2, dépôt de phéromones de tâche
- [ ] `transformer.py` : lecture phéromone de tâche, génération Py3, dépôt du résultat
- [ ] `tester.py` : détection de `transformed`, exécution pytest, dépôt de qualité
- [ ] `validator.py` : lecture qualité, commit/rollback/escalade
- [ ] Trouver et préparer **1 dépôt Python 2 open source** de test (petit : ~10-20 fichiers)
- [ ] Tests unitaires de chaque agent en isolation

**Livrable** : chaque agent peut tourner seul sur 1 fichier et déposer ses traces correctement.

### Sprint 3 — Boucle complète + métriques (3 jours)

**Objectif** : les 4 agents tournent ensemble, coordonnés uniquement par les phéromones.

- [ ] `loop.py` : boucle round-robin avec critères d'arrêt
- [ ] `main.py` : point d'entrée CLI (`python main.py --repo <url> --config config.yaml`)
- [ ] `collector.py` : enregistrement métriques à chaque tick
- [ ] `export.py` : export CSV/JSON des résultats
- [ ] Premier run complet sur le dépôt de test
- [ ] Debug des interactions émergentes (boucles infinies, agents inactifs, conflits)
- [ ] Ajustement des seuils et du decay_rate

**Livrable** : un POC qui migre un petit dépôt Py2→Py3 de bout en bout, avec logs et métriques exportables.

### Sprint 4 — Baselines + analyse (3 jours)

**Objectif** : comparer stigmergique vs alternatives.

- [ ] `baselines/single_agent.py` : même tâche, 1 agent
- [ ] `baselines/sequential.py` : pipeline fixe sans phéromones
- [ ] Optionnel : baseline hiérarchique (superviseur + workers)
- [ ] Runs multiples (5 minimum) pour chaque configuration (variabilité stochastique)
- [ ] `pareto.py` : génération du graphique Pareto coût-précision
- [ ] Analyse des traces de phéromones : quels patterns émergent ?
- [ ] Rédaction des résultats quantitatifs

**Livrable** : tableau comparatif des 3-4 configurations, graphique Pareto, analyse des mécanismes stigmergiques observés.

### Sprint 5 — Robustesse + scale (3 jours, optionnel)

**Objectif** : tester la robustesse et préparer le switch vers un modèle frontière.

- [ ] Test sur un 2e dépôt plus gros (~50-100 fichiers)
- [ ] Test avec un modèle frontière (Claude Sonnet / GPT-4o via OpenRouter)
- [ ] Comparaison pony-alpha vs modèle frontière (qualité, coût, comportement émergent)
- [ ] Test de résilience : que se passe-t-il si un agent échoue ? si l'API timeout ?
- [ ] Benchmark optionnel sur TravelPlanner (diversifier au-delà de la migration)
- [ ] Documentation finale du POC

**Livrable** : résultats à échelle plus réaliste, données prêtes pour la section résultats du mémoire.

---

## 8. Dépôts Python 2 candidats pour les tests

| Dépôt | Taille | Intérêt |
|---|---|---|
| **python/mypy** (anciennes versions) | Moyen | Bien documenté, tests existants |
| **Un micro-projet GitHub "Python 2 only"** | Petit | Contrôlable, rapide à itérer |
| **six library test suite** | Petit | Cas d'usage direct Py2/Py3 |
| **Créer un dépôt synthétique** | ~15 fichiers | Couverture contrôlée de tous les patterns Py2 |

**Recommandation** : commencer par un dépôt synthétique maîtrisé (Sprint 2), puis passer à un vrai dépôt open source (Sprint 4-5).

---

## 9. Stack technique

| Composant | Choix | Justification |
|---|---|---|
| **Langage** | Python 3.11+ | Écosystème naturel pour le sujet |
| **LLM Provider** | OpenRouter | Flexibilité de modèle (gratuit → payant) |
| **LLM Phase dev** | pony-alpha | Gratuit, suffisant pour valider l'architecture |
| **LLM Phase résultats** | Claude Sonnet / GPT-4o | Résultats publiables |
| **Store phéromones** | Fichiers JSON locaux | Simple, versionnable, inspectable |
| **Tests** | pytest | Standard Python, output parsable |
| **Versioning** | Git (local) | Le médium stigmergique lui-même |
| **Config** | YAML | Lisible, modifiable sans code |
| **Métriques** | CSV + matplotlib | Graphiques Pareto pour le mémoire |

---

## 10. Risques identifiés et mitigations

| Risque | Probabilité | Impact | Mitigation |
|---|---|---|---|
| pony-alpha trop faible pour générer du code correct | Haute | Moyen | Valider l'archi d'abord, switcher de modèle pour les résultats |
| Boucle infinie (agent retry sans fin) | Moyenne | Haut | Guardrail anti-boucle (max 3 retries) + budget tokens |
| Conflits Git entre agents | Moyenne | Moyen | Scope lock (1 agent par fichier) |
| Latence API dégradant l'expérience | Moyenne | Faible | Async optionnel, mais round-robin séquentiel suffit |
| Coût API explosif en phase résultats | Moyenne | Haut | Budget plafond configurable + mesure dès le Sprint 3 |
| Résultats non significatifs (stigmergie ≈ séquentiel) | Moyenne | Haut | C'est un résultat en soi — le mémoire doit discuter honnêtement les conditions où la stigmergie apporte ou non de la valeur |

---

## 11. Liens avec le mémoire

| Section du mémoire | Ce que le POC alimente |
|---|---|
| **RQ1 (Mécanisme)** | Types de phéromones, règles locales, patterns émergents observés |
| **RQ2 (Performance)** | Tableau comparatif, Pareto coût-précision, taux de succès |
| **RQ3 (Gouvernance)** | Logs d'auditabilité, guardrails en action, escalade humaine |
| **Entretiens** | Le POC sert de démo lors des entretiens semi-directifs |
| **Cadre conceptuel** | Validation empirique des 3 piliers (conceptuel, managérial, technique) |

---

## 12. Checklist avant de coder

- [ ] Créer le repo GitHub `stigmergic-poc`
- [ ] Initialiser l'environnement Python (`pyproject.toml` ou `requirements.txt`)
- [ ] Obtenir la clé API OpenRouter
- [ ] Vérifier que pony-alpha fonctionne sur un prompt simple de migration
- [ ] Préparer le dépôt synthétique Python 2 de test
- [ ] Relire les sections 2, 3 et 9 de la revue pour ancrer les choix de design

---

*Ce plan est un document vivant — à mettre à jour au fil des sprints.*
