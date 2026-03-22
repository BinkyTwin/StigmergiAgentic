# Plan V4 : Refactorisation stigmergique du framework StigmergiAgentic

> **Date :** 2026-03-22
> **Auteur :** Audit Claude Opus 4.6 + Lotfi
> **Branche de depart :** `codex/openrouter-qwen35-9b-cleanup` (Sprint 6 V3)

---

## Contexte

### Probleme identifie

L'audit d'alignement entre la revue de litterature DSR (objectifs OC1-OC5, principes stigmergiques theorises) et la codebase V3 Sprint 6 revele que le framework, bien qu'il implemente une **coordination indirecte via markers** (coeur de la stigmergie), viole 4 principes fondamentaux :

1. **Sensing global** au lieu de local
2. **Boucle synchrone** au lieu d'asynchrone
3. **Evaporation schedulee** au lieu de continue
4. **Arbitrage centralise** au lieu d'emergent

Ces ecarts rendent les revendications de "stigmergie" scientifiquement fragiles face a un jury informe.

### Score actuel

- **TravelPlanner final_pass_rate : 10%** (180 queries, validation split, Qwen 3.5 9B via OpenRouter)
- **Baseline SwarmAgentic : 32.2%** (GPT-4o) — comparaison non equitable (modele ~50x plus gros)
- delivery_rate: 58.3%, hard_constraint_macro: 14.4%, commonsense_macro: 17.8%
- Plans 7 jours : vides. Plans 5 jours : faibles.

### Objectif

Refactoriser le code pour introduire 5 proprietes stigmergiques genuines, tout en preservant la compatibilite arriere (209 tests existants, API publique, interface DomainAdapter).

---

## Audit : ce qui est et n'est pas stigmergique

### Authentiquement stigmergique (a preserver)

| Propriete | Implementation | Conforme a |
|-----------|---------------|------------|
| Coordination indirecte | Agents ne communiquent jamais entre eux, uniquement via markers | Heylighen 2016a, Grasse 1959 |
| Agents role-free | Meme logique `StigmergicAgent` pour tous | Bonabeau et al. 1999 |
| Stigmergie cognitive | Artefacts riches (payloads, metadata) interpretes par LLM | Ricci et al. 2007 |
| Guardrails environnementaux | Contraintes dans l'environnement, pas dans les agents | Grisold et al. 2025 |
| Construction incrementale | Markers evoluent via machine a etats | Theraulaz & Bonabeau 1999 |
| LLM comme outil passif | Le LLM ne controle pas la boucle, il est invoque par les outils | Design original |

### Violations a corriger

| Principe theorique | Violation actuelle | Ref. theorique | Impact |
|---|---|---|---|
| **Sensing local** | `perceive_and_decide()` lit TOUS les markers en snapshot global | Heylighen 2016a : "perception locale" ; Parunak 1997 : "localite de perception" | Pas de specialisation emergente, tous les agents identiques |
| **Evaporation continue** | `apply_decay()` ne tourne que quand l'orchestrateur appelle `maintain()` | Bonabeau et al. 1999 : evaporation autonome des pheromones | Les markers ne "vivent" pas, pas de dynamique temporelle |
| **Renforcement par frequentation** | Reward shaping explicite via `quality_score` + sigmoid | Dorigo et al. 1996 (ACO) : renforcement par frequentation de chemins | Pas d'apprentissage emergent par trafic |
| **Resolution de conflits emergente** | Locks SQLite transactionnels (`BEGIN IMMEDIATE`) | Serugendo et al. 2005 : auto-organisation sans controle externe | Arbitrage centralise, pas emergent |
| **Feedback d'emergence** | Metriques post-hoc (8 metriques) jamais utilisees par les agents | Holland 1995 : boucle de retroaction adaptative | Pas d'auto-regulation du systeme |

---

## Plan d'implementation (5 features, approche sequentielle)

### Sequence

```
Etape 1: P1 Local Sensing          → tester → valider impact
Etape 2: P2 Evaporation temporelle → tester → valider impact
Etape 3: P3 Frequentation          → tester → valider impact
Etape 4: P4 Resolution emergente   → tester → valider impact (NICE TO HAVE)
Etape 5: P5 Feedback emergence     → tester → valider impact (NICE TO HAVE)
```

Approche sequentielle pour isoler l'impact de chaque changement sur le benchmark.

---

### P1 — Local Sensing (CRITIQUE)

**But :** Au lieu de lire TOUS les markers, chaque agent percoit un sous-ensemble filtre par affinite de type, seuil d'intensite et proximite semantique.

**Fichiers :** `core/agent.py`, `config/default.yaml`

#### 1. Nouvelle classe `AgentAffinityProfile`

```python
@dataclass(slots=True)
class AgentAffinityProfile:
    type_counts: dict[str, int]      # marker_type -> nb fois travaille
    target_keywords: dict[str, int]  # keyword -> frequence
    total_actions: int = 0
```

**Methodes :**
- `record_action(marker_type, target)` — apres chaque execution reussie
- `type_affinity(marker_type) -> float [0,1]` — frequence relative
- `semantic_affinity(target) -> float [0,1]` — overlap mots-cles avec historique
- `combined_affinity(marker_type, target) -> float [0,1]` — moyenne ponderee

Initialise dans `StigmergicAgent.__init__()`, appele dans `execute()` apres succes.

#### 2. Configuration

```yaml
agents:
  local_sensing:
    enabled: false  # defaut = comportement actuel (backward compat)
    intensity_threshold: 0.0
    type_affinity_weight: 0.4
    semantic_affinity_weight: 0.3
    recency_weight: 0.3
    max_candidates: 0  # 0 = pas de limite
    affinity_exploration_rate: 0.2  # proba d'ignorer le filtre (exploration)
```

#### 3. Modification de `_candidate_markers()`

Quand `local_sensing.enabled=true`, apres les filtres existants :
1. Filtrer par `intensity_threshold`
2. Scorer chaque marker : `type_affinity * w1 + semantic_affinity * w2 + recency * w3`
3. Avec proba `exploration_rate`, garder tous les candidats (exploration aleatoire)
4. Sinon, trier par score desc et garder top `max_candidates`

**Point cle :** Le `EnvironmentSnapshot` reste COMPLET — le filtrage est au niveau agent. Chaque agent voit un sous-ensemble different → specialisation emergente.

#### 4. Injection dans `compute_pressures()`

La fonction `heuristic_fn(marker, action)` est deja supportee dans `core/pressure.py` :

```python
def _affinity_heuristic(self, marker, action) -> float:
    return base_weight * (1.0 + self.affinity.combined_affinity(marker.marker_type, marker.target))
```

S'injecte naturellement dans la formule ACO : `pheromone^alpha * heuristic^beta`.

#### 5. Tests

- Nouveau `tests/unit/test_local_sensing.py` (6-8 tests)
- Valider que `enabled=false` produit le meme comportement qu'avant
- Valider que le cold start (total_actions=0) retourne affinite neutre (0.5)
- Valider que `exploration_rate=1.0` desactive tout filtrage

#### Risques

| Risque | Mitigation |
|--------|-----------|
| Sur-specialisation | `affinity_exploration_rate` force l'exploration aleatoire |
| Cold start | Affinite neutre (0.5) quand `total_actions == 0` |

---

### P2 — Evaporation temporelle continue (IMPORTANT)

**But :** L'intensite des markers decroit en fonction du temps reel ecoule, pas seulement a chaque tick.

**Fichiers :** `core/marker.py`, `core/marker_store.py`, `core/decay.py`, `core/environment.py`, `config/default.yaml`

#### 1. Nouveau champ `last_active_at` sur `Marker`

```python
last_active_at: str = ""  # ISO-8601 UTC, vide = fallback sur updated_at
```

#### 2. Migration SQLite

```sql
ALTER TABLE markers ADD COLUMN last_active_at TEXT NOT NULL DEFAULT '';
```
Avec try/except pour idempotence.

#### 3. Nouvelle fonction `effective_intensity()` dans `core/decay.py`

```python
def effective_intensity(
    stored_intensity: float,
    last_active_at: str,
    now: str,
    decay_type: str,
    decay_rate: float,
    decay_period_seconds: float,
    clamp: tuple[float, float],
) -> float:
```

- Si `last_active_at` vide ou `decay_period_seconds <= 0` : retourne `stored_intensity` (backward compat)
- Sinon : `periods = elapsed_seconds / decay_period_seconds`, applique exponentielle ou lineaire
- Clampe au floor (defaut 0.1) pour eviter l'evaporation totale

#### 4. Modifier `Environment.snapshot()`

Quand `time_decay.enabled=true`, appliquer `effective_intensity()` sur chaque marker du snapshot AVANT de le retourner. Les valeurs stockees ne changent pas — seule la lecture est affectee.

**C'est de l'evaporation continue :** chaque lecture voit une intensite reduite par le temps ecoule depuis la derniere activite.

#### 5. Configuration

```yaml
markers:
  time_decay:
    enabled: false
    decay_period_seconds: 60.0
```

#### 6. Tests

- 4 nouveaux tests dans `tests/unit/test_decay.py` pour `effective_intensity()`
- 1 nouveau test dans `tests/unit/test_environment.py` pour snapshot avec time_decay
- Tests existants inchanges

---

### P3 — Renforcement par frequentation (IMPORTANT)

**But :** Remplacer le reward shaping explicite par un renforcement base sur le trafic. Les markers lus par plusieurs agents gagnent en intensite (comme les pistes de pheromones renforcees par le passage des fourmis).

**Fichiers :** `core/marker_store.py`, `core/reinforcement.py`, `core/environment.py`, `core/orchestrator.py`, `config/default.yaml`

#### 1. Table `marker_reads` dans SQLite

```sql
CREATE TABLE IF NOT EXISTS marker_reads (
    marker_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    tick INTEGER NOT NULL,
    read_at TEXT NOT NULL,
    PRIMARY KEY (marker_id, agent_id, tick)
);
```

#### 2. Methodes `record_read()` et `read_count()` dans `MarkerStore`

- `record_read(marker_id, agent_id, tick)` — INSERT OR IGNORE
- `read_count(marker_id, since_tick=0) -> int` — COUNT(*)

#### 3. Enregistrement des lectures

Callback optionnel `on_perceive` dans `StigmergicAgent.__init__()`. L'orchestrateur le connecte au store. Les markers percus sont enregistres automatiquement.

#### 4. Nouvelle fonction `frequentation_boost()` dans `core/reinforcement.py`

```python
def frequentation_boost(
    read_count: int,
    base_boost: float = 0.01,
    max_boost: float = 0.1,
    diminishing_factor: float = 0.5,
) -> float:
```

Rendements decroissants : `boost = base_boost * (1 - diminishing_factor^read_count) / (1 - diminishing_factor)`, cappe a `max_boost`.

#### 5. Application dans `maintain()`

Apres decay, nouvelle etape : query `marker_reads` pour les lectures du tick courant, calculer les boosts, appliquer aux intensites stockees.

#### 6. Coexistence avec le renforcement explicite

Les deux mecanismes composent additivement. Pour passer en pur frequentation : `reinforcement.enabled: false` + `frequentation.enabled: true`.

#### 7. Configuration

```yaml
reinforcement:
  frequentation:
    enabled: false
    read_boost: 0.01
    completion_boost: 0.05
    max_boost_per_tick: 0.1
```

#### 8. Tests

- Nouveau `tests/unit/test_frequentation.py` (5-6 tests)
- Tests existants inchanges

---

### P4 — Resolution de conflits emergente (NICE TO HAVE)

**Depend de P1** (profil d'affinite).

**Fichiers :** `core/environment.py`, `core/orchestrator.py`, `config/default.yaml`

Au lieu de locks sequentiels, quand plusieurs agents ciblent le meme marker :
1. Grouper les decisions par `marker_id` (contention groups)
2. Si 1 seul contender : lock direct (comme avant)
3. Si contention : selection probabiliste ponderee par affinite
4. `weight_i = affinity_i + base_probability` normalise et echantillonne
5. Fallback vers l'arbitrage classique en cas d'echec

```yaml
orchestrator:
  emergent_resolution:
    enabled: false
    base_probability: 0.1
```

---

### P5 — Feedback d'emergence (NICE TO HAVE)

**Fichiers :** `core/emergence.py`, `core/orchestrator.py`, `config/default.yaml`

Nouvelle fonction `compute_adaptations(metrics, config) -> dict` :

| Condition | Adaptation |
|-----------|-----------|
| `colony_specialization < 0.3` | Reduire `exploration_rate` (narrower sensing) |
| `colony_specialization > 0.8` | Augmenter `exploration_rate` (broader sensing) |
| `lock_contention_rate > 0.3` | Augmenter `inhibition_increment` |
| `parallel_utilization < 0.3` | Reduire `selection_temperature` (more greedy) |
| `pressure_entropy < 0.2` | Augmenter `selection_temperature` (more exploration) |

Applique tous les N ticks. Config in-memory uniquement, pas les fichiers YAML. Audite dans le JSONL.

```yaml
emergence:
  feedback_loop:
    enabled: false
    interval_ticks: 5
    max_adaptation_delta: 0.2
```

---

## Compatibilite arriere

| Feature | Defaut | Quand desactive | Cassure |
|---------|--------|-----------------|---------|
| P1 Local Sensing | `enabled: false` | `_candidate_markers()` inchange | Aucune |
| P2 Time Decay | `enabled: false` | `snapshot()` retourne intensite stockee | Aucune |
| P3 Frequentation | `enabled: false` | Pas de tracking, pas de boost | Aucune |
| P4 Resolution emergente | `enabled: false` | Arbitrage sequentiel classique | Aucune |
| P5 Feedback emergence | `enabled: false` | Metriques calculees mais pas feedbackees | Aucune |

**Toutes les features sont opt-in.** Les 209 tests existants passent sans modification.

---

## Fichiers critiques a modifier

| Fichier | P1 | P2 | P3 | P4 | P5 |
|---------|----|----|----|----|-----|
| `core/agent.py` | **MAJEUR** | - | mineur | - | - |
| `core/marker.py` | - | mineur | - | - | - |
| `core/marker_store.py` | - | **MAJEUR** | **MAJEUR** | - | - |
| `core/decay.py` | - | **MAJEUR** | - | - | - |
| `core/pressure.py` | mineur | - | - | - | - |
| `core/reinforcement.py` | - | - | **MAJEUR** | - | - |
| `core/environment.py` | - | **MAJEUR** | mineur | mineur | - |
| `core/orchestrator.py` | - | - | mineur | **MAJEUR** | **MAJEUR** |
| `core/emergence.py` | - | - | - | - | **MAJEUR** |
| `config/default.yaml` | mineur | mineur | mineur | mineur | mineur |
| `config/travelplanner.yaml` | mineur | mineur | mineur | mineur | mineur |

---

## Impact attendu sur TravelPlanner

- **P1 (Local Sensing)** : Agents se specialisent (search_flights vs search_hotels vs plan_itinerary) au lieu de se battre pour les memes markers. Reduction des ticks gaspilles.
- **P2 (Time Decay)** : Markers stalls perdent naturellement de la priorite. Focus sur le travail actif.
- **P3 (Frequentation)** : Sous-taches que plusieurs agents considerent (haute valeur) gagnent en intensite. "Pistes de pheromones" emergentes.
- **Estimation :** P1+P2+P3 combines : de 10% vers 18-25% (avec Qwen 3.5 9B).

### Note sur la comparaison equitable

Le run actuel est avec **Qwen 3.5 9B**. SwarmAgentic rapporte 32.2% avec **GPT-4o**.

Actions necessaires :
1. Re-evaluer avec un modele comparable (GPT-4o ou Claude Sonnet) pour comparaison equitable
2. Documenter les resultats par modele pour la frontiere de Pareto cout-performance (Kapoor et al. 2024)
3. Si le budget le permet, tester GPT-4o-mini comme compromis cout/performance

---

## Verification

1. `uv run pytest tests/unit tests/integration -v` → 209+ tests (existants + nouveaux)
2. Activer les features une par une et valider :
   - `local_sensing.enabled: true` → agents developpent des affinites differentes au fil des ticks
   - `time_decay.enabled: true` → intensites plus basses pour markers anciens dans le snapshot
   - `frequentation.enabled: true` → markers populaires gagnent en intensite dans le store
3. Run TravelPlanner avec toutes les features activees et comparer au baseline 10%
4. Verifier que toutes features `enabled: false` produit exactement le meme comportement qu'avant
5. Comparer les metriques d'emergence (specialization_entropy, collaboration_density) avant/apres
