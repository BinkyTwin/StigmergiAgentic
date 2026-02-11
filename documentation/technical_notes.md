# Notes Techniques — POC Stigmergique

Ce document contient les notes techniques, découvertes, patterns de code, et problèmes résolus durant le développement.

## Table des Matières

- [Patterns Stigmergiques Récurrents](#patterns-stigmergiques-récurrents)
- [Configuration et Thresholds](#configuration-et-thresholds)
- [Problèmes Résolus](#problèmes-résolus)
- [Optimisations](#optimisations)
- [Références Bibliographiques](#références-bibliographiques)

---

## Patterns Stigmergiques Récurrents

### Pattern 1 : Perceive → Should Act → Decide → Execute → Deposit

Tous les agents suivent ce cycle. Implémentation type :

```python
class MyAgent(BaseAgent):
    def perceive(self) -> dict:
        """Lit l'environnement (pheromones) sans le modifier"""
        return self.environment.read_pheromones(self.agent_id)
    
    def should_act(self, perception: dict) -> bool:
        """Décide si l'intensité phéromonale justifie une action"""
        return perception.get('intensity', 0) > self.threshold
    
    def decide(self, perception: dict) -> dict:
        """Planifie l'action à exécuter"""
        return {'action': 'transform', 'file': perception['file']}
    
    def execute(self, decision: dict) -> dict:
        """Exécute l'action (avec effet de bord)"""
        result = self._do_transformation(decision['file'])
        return result
    
    def deposit(self, result: dict) -> None:
        """Dépose une nouvelle phéromone pour l'agent suivant"""
        self.environment.write_pheromone({
            'agent_id': self.agent_id,
            'timestamp': time.time(),
            'result': result
        })
```

### Pattern 2 : Coordination Indirecte via Phéromones

❌ **JAMAIS faire** :
```python
# INTERDIT : appel direct entre agents
transformer.process(scout.get_task())
```

✅ **TOUJOURS faire** :
```python
# Agent 1 dépose
environment.write_pheromone('tasks.json', task_data)

# Agent 2 lit (dans un autre cycle)
tasks = environment.read_pheromone('tasks.json')
```

### Pattern 3 : Évaporation et Renforcement

```python
# Évaporation automatique (géré par environment/decay.py)
intensity_new = max(0, intensity_old + decay_rate)

# Renforcement positif
if test_passed:
    confidence += 0.1
    
# Renforcement négatif
if test_failed:
    confidence -= 0.2
    retry_count += 1
```

---

## Configuration et Thresholds

### Valeurs Critiques (`stigmergy/config.yaml`)

| Paramètre | Valeur | Justification |
|-----------|--------|---------------|
| `transformer_intensity_threshold` | 0.3 | Trop bas → actions inutiles ; trop haut → paralysie |
| `validator_confidence_threshold` | 0.8 | Auto-commit si > 0.8 ; rollback si < 0.5 |
| `task_pheromone_decay` | -0.05 | Évaporation progressive pour éviter l'accumulation |
| `max_retry_count` | 3 | Anti-boucle infinie ; au-delà → escalation humaine |
| `max_tokens_total` | 100000 | Budget LLM pour rester dans les coûts raisonnables |

### Optimisation des Thresholds

Processus expérimental pour ajuster :
1. Lancer 5 runs avec valeur par défaut
2. Mesurer : taux de succès, tokens utilisés, nombre d'itérations
3. Ajuster ±20%
4. Comparer avec Pareto frontier
5. Conserver le meilleur compromis coût/précision

---

## Problèmes Résolus

### Problème 1 : Race Conditions sur `pheromones/*.json`

**Symptôme** : Fichiers JSON corrompus lors d'écritures concurrentes

**Cause** : Pas de lock atomique entre lecture et écriture

**Solution** :
```python
import fcntl

def atomic_write(file_path, data):
    with open(file_path, 'r+') as f:
        fcntl.flock(f, fcntl.LOCK_EX)  # Verrou exclusif
        f.seek(0)
        json.dump(data, f, indent=2)
        f.truncate()
        fcntl.flock(f, fcntl.LOCK_UN)  # Libération
```

**Référence** : `environment/pheromone_store.py:45`

---

### Problème 2 : Évaporation Trop Rapide des Phéromones

**Symptôme** : Les tâches disparaissent avant d'être traitées

**Cause** : Decay rate `-0.1` était trop agressif pour un cycle de 4 agents

**Solution** : Réduire à `-0.05` et ajouter un seuil minimum `intensity_floor = 0.1`

**ADR** : Voir `decisions/20260209-pheromone-decay-rate.md`

---

### Problème 3 : LLM Timeouts avec OpenRouter

**Symptôme** : Exceptions `ReadTimeout` sur de gros fichiers Python 2

**Cause** : Timeout par défaut de 30s insuffisant

**Solution** :
```python
import httpx

client = httpx.Client(timeout=120.0)  # 2 minutes
```

**Commit** : `abc1234` (voir `git log`)

---

## Optimisations

### Optimisation 1 : Cache des Embeddings LLM

Pour éviter de re-calculer les embeddings des mêmes patterns Python 2 :

```python
# stigmergy/llm_client.py
@lru_cache(maxsize=1000)
def get_embedding(text: str) -> list[float]:
    # Appel API coûteux mis en cache
    ...
```

**Gain** : -40% tokens utilisés sur tests répétés

---

### Optimisation 2 : Batch des Appels API

Au lieu de transformer fichier par fichier, grouper les petits fichiers :

```python
batch = []
for file in files:
    if file.lines < 100:
        batch.append(file)
        
# Un seul appel LLM avec contexte groupé
results = llm.transform_batch(batch)
```

**Gain** : -25% latence totale

---

## Sprint 1 Implementation Notes (2026-02-10)

### Environment Runtime Standardization (`uv`)

- Local runtime is pinned with `uv` + CPython 3.11 to match the project spec.
- All validation commands are executed through `uv run` to avoid host Python drift.
- `requirements.txt` remains the single source of truth for Sprint 1 dependency resolution.

### Pheromone Store Reliability Pattern

- JSON persistence is implemented with file-level locks (`fcntl.flock`) to avoid race corruption.
- Each `write`/`update` appends an immutable event to `pheromones/audit_log.jsonl`.
- Query operators support `eq`, `gt`, `gte`, `lt`, `lte`, `in` for deterministic selection.

### Guardrails as Environment-Native Constraints

- Token budget enforcement raises immediately when `total_tokens_used > max_tokens_total`.
- Scope lock prevents cross-agent concurrent mutation on files in `in_progress`.
- Zombie lock TTL requeues stale files (`in_progress` -> `pending`) with `retry_count += 1`.
- Retry anti-loop marks entries as `skipped` once retry ceiling is exceeded.

### Testability and Reproducibility

- Sprint 1 includes focused tests for store CRUD/query/locking/decay and guardrails behavior.
- Validation sequence was executed twice with identical pass results to check reproducibility.
- A pytest path bootstrap (`tests/conftest.py`) was added to ensure stable local imports.

### Resume FR (mémoire)

- Le médium stigmergique est maintenant opérationnel de manière autonome (sans agents).
- Les contraintes de gouvernance sont implémentées côté environnement (pas côté agents).
- La traçabilité est démontrable via un journal append-only aligné avec RQ3.

---

## Sprint 2 Implementation Notes (2026-02-11)

### Agent Runtime Contract

- `BaseAgent` now enforces the shared lifecycle: `perceive -> should_act -> decide -> execute -> deposit`.
- `run()` returns a deterministic boolean signal (`True` acted, `False` idle), simplifying loop-level stop conditions for Sprint 3.
- Agent logs are standardized with `[agent_name]` context.

### Scout Detection Strategy

- Pattern detection uses a hybrid pass:
  - AST pass when file parsing is possible
  - Regex fallback for Python 2-only syntax that Python 3 AST cannot parse
- Each detection carries explicit provenance (`source = ast | regex | llm`) in task pheromones for auditability.
- Task intensity is normalized batch-wise with min-max and clamped to config bounds.

### Transformer Prompting and Selection

- Candidate selection follows environmental constraints only:
  - `status = pending`
  - `task.intensity > transformer_intensity_min`
  - `inhibition < inhibition_threshold`
- Prompt assembly includes:
  - task patterns from `tasks.json`
  - up to 3 validated examples (`confidence >= 0.8`) with overlapping patterns
  - retry context from prior quality issues when available
- Status transitions implemented as: `pending -> in_progress -> transformed | failed`.

### Tester Confidence Model

- Test discovery order:
  1. `tests/test_<module>.py`
  2. `test_<module>.py` next to source file
  3. fallback `py_compile + import`
- Confidence computation:
  - `tests_passed / tests_total` when tests are discovered
  - neutral `0.5` when no test exists (fallback success)
- Coverage is collected when pytest path is used and stored as informational metadata.

### Validator Decisioning and Git Operations

- Confidence thresholds in config now drive terminal routing:
  - `>= 0.8` -> `validated` + commit + `confidence += 0.1`
  - `[0.5, 0.8)` -> `needs_review`
  - `< 0.5` -> rollback + `confidence -= 0.2` + `retry|skipped`
- Rollback uses file-scoped checkout to preserve unrelated changes in repository state.

### Test Harness and Fixture Isolation

- Added Sprint 2 test suite:
  - unit tests for `LLMClient`, `BaseAgent`, each specialized agent
  - integration tests for all required handoffs + full one-file cycle
- Added fixture repository `tests/fixtures/synthetic_py2_repo/` with all 19 Python 2 patterns represented.
- Fixture subtree is explicitly ignored from project-level pytest collection to avoid accidental execution as part of core tests.

---

## Références Bibliographiques

### Stigmergie

- Grassé, P.-P. (1959). La reconstruction du nid et les coordinations interindividuelles chez *Bellicositermes natalensis* et *Cubitermes* sp. *Insectes Sociaux*, 6(1), 41–80.
- Ricci, A., Viroli, M., & Omicini, A. (2007). Give agents their artifacts: the A&A approach for engineering working environments in MAS. *AAMAS*.

### Baselines de Comparaison

- Xia, C. S., et al. (2024). Agentless: Demystifying LLM-based Software Engineering Agents. *arXiv:2407.01489*.

### Auditabilité IA

- EU AI Act (2024). Article 14 : Exigences de transparence pour les systèmes à haut risque.

---

## À Compléter au Fur et à Mesure

Cette section sera enrichie durant le développement. Ajouter :
- Nouveaux patterns découverts
- Bugs critiques + solutions
- Optimisations testées
- Références académiques pertinentes

---

**Dernière mise à jour** : 2026-02-09
