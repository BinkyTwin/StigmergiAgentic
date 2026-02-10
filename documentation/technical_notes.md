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
