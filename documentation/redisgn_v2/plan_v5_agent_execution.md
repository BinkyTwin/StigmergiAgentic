# Plan d'exécution V5-full — Instructions pour agent IA

**Date** : 2026-04-16  
**Objectif** : Implémenter les tâches T7, T8, T9, T10, puis lancer un benchmark V5-full vs V0 pour mesurer le gain réel des améliorations.  
**Repo** : `/Users/lotfi/Documents/EMLV/Memoire/StigmergiAgentic`  
**Branche active** : `codex/t0-travelplanner-multi-city`

---

## Contexte — ce qui est déjà fait

| Tâche | État | Détail |
|---|---|---|
| T0 multi-city | ✅ fait | commit `0e4fa9a` — `adapter.py` génère des markers par ville |
| T1 config V4-only | ✅ fait | `config/travelplanner_v4_only.yaml` existe et est complet |
| T5 continue-on-error | ✅ fait | `scripts/run_travelplanner_framework_benchmark.py` utilise `failed_query_payload()` + `FAILURE_TOLERANCE_RATIO=0.30` |
| V4 corrections (5) | ✅ fait | local_sensing, time_decay, frequentation, emergent_resolution, feedback_loop activés dans le preset V4-only |

**Ce qui n'existe pas encore** : T7, T8, T9, T10.

**Baseline de référence (V0)** : run `output/travelplanner_framework_compare/20260409_233919/` — StigmergiAgentic à 8.5% final_pass, 55.4% delivery_rate. **Ne pas re-runner V0**, utiliser ce run existant comme point de comparaison.

---

## Contraintes absolues à ne jamais violer

- ❌ Ne jamais modifier `core/` (orchestrator, agent, pressure, marker, etc.)
- ❌ Ne jamais modifier `third_party/travelplanner_official/` ni `scripts/eval_travelplanner_official.py`
- ❌ `markers.session_isolation: true` doit rester dans tous les configs
- ❌ T8 : utiliser **uniquement** le split `train` pour le tuning — jamais `validation`
- ❌ T9 : les exemples few-shot doivent venir de `load_dataset("osunlp/TravelPlanner", "train")` uniquement
- ✅ Après chaque tâche : `uv run pytest tests/ -q` doit rester à ≥ 235 passed

---

## T10 — Créer `config/ablation/v5_full.yaml`

**Durée estimée** : 10 minutes  
**Priorité** : faire en premier (les autres tâches le référencent)

### Ce que tu dois créer

Fichier : `config/ablation/v5_full.yaml`

Ce fichier est une copie de `config/travelplanner_v4_only.yaml` avec deux changements :
- `orchestrator.max_ticks: 80` (au lieu de 30)
- `agents.num_agents: 6` (au lieu de 3)

Le reste est identique — toutes les corrections V4 restent activées, `session_isolation: true` reste.

Ajouter un commentaire en tête :
```
# V5-full preset — V4 + max_ticks=80 + num_agents=6 + marker shaping (T7) + prompts enrichis (T9) + hyperparams tunés (T8).
# NE PAS MODIFIER ce fichier manuellement après le tuning T8 — les valeurs alpha/beta/temperature seront mises à jour par scripts/tune_aco_travelplanner.py
```

### Test d'acceptation T10

```bash
uv run python main.py --adapter travelplanner --config config/ablation/v5_full.yaml --objective "Query 0"
```
Doit terminer sans erreur de config.

---

## T7 — Marker shaping dans `adapters/travelplanner/tools.py`

**Durée estimée** : 3-4 heures  
**Fichier cible** : `adapters/travelplanner/tools.py`  
**Principe** : quand un tool détecte une mauvaise situation (violations, résultats vides), il ajuste `intensity` et `inhibition` du marker résultat pour guider les agents vers le bon comportement. **Aucune modification du `core/`**.

### Règles de shaping à implémenter

**Règle 1 — ValidateConstraintsTool** (classe à la ligne 1181) :
- Si `evaluation.final_pass == False` et des violations existent → sur le marker `validate_constraints` :
  - Remonter `intensity` à `0.9`
  - Réduire `inhibition` à `0.0`
  - Cela stimule le replan
- Si `commonsense_violations` détectées (commonsense_macro_pass == False) → sur le marker de plan correspondant (via `depends_on`) :
  - Augmenter `inhibition` de `+0.3` (plafonné à 1.0)
  - Cela décourage la réutilisation du même chemin de planification

**Règle 2 — `_BaseTravelSearchTool`** (classe à la ligne 19 — parent de SearchHotelsTool, SearchRestaurantsTool, etc.) :
- Si le résultat `results` est vide (`[]`) → sur le marker search :
  - Maintenir `intensity` à son niveau actuel (ne pas le réduire avec `intensity_step`)
  - Cela stimule la retry

**Règle 3 — PlanDayTool** (classe à la ligne 127) :
- Si le plan retourné par le LLM est `[]` (échec parsing) → sur le marker plan :
  - Remonter `intensity` à `0.8`
  - Ne pas décrémenter l'intensité

### Comment modifier le code

Dans `ValidateConstraintsTool.execute()` (autour de la ligne 1243-1296), dans la section où `evaluation.final_pass == False` :

```python
# Shaping T7 : violations → stimuler le replan
if not evaluation.final_pass and failed_constraints:
    updated.intensity = 0.9
    updated.inhibition = 0.0

# Shaping T7 : commonsense violations → inhiber le chemin fautif
if not evaluation.commonsense_macro_pass:
    plan_m = self._resolve_plan_marker(marker=marker, environment=environment)
    if plan_m is not None:
        shaped_plan = Marker.from_dict(plan_m.to_dict())
        shaped_plan.inhibition = min(1.0, float(shaped_plan.inhibition) + 0.3)
        # l'ajouter à marker_updates dans le ActionResult
```

Dans `_BaseTravelSearchTool.execute()`, si `results == []` : ne pas appliquer `intensity_step` (laisser `intensity` inchangée).

Dans `PlanDayTool.execute()`, si `plan == []` après parsing : remonter `intensity` à `0.8` avant de retourner l'`ActionResult`.

### Nouveau test unitaire à créer

Fichier : `tests/unit/test_travelplanner_marker_shaping.py`

Trois tests :
1. `test_validate_shaping_on_violation` : simuler un marker avec `evaluation.final_pass=False` + violations → vérifier `intensity=0.9` et `inhibition=0.0` dans le marker retourné
2. `test_search_shaping_empty_results` : simuler un search tool avec `results=[]` → vérifier que `intensity` ne baisse pas
3. `test_plan_shaping_empty_plan` : simuler un PlanDayTool retournant `plan=[]` → vérifier `intensity=0.8`

### Test d'acceptation T7

```bash
uv run pytest tests/unit/test_travelplanner_marker_shaping.py -v
uv run pytest tests/ -q  # doit rester ≥ 235 passed
```

---

## T9 — Few-shots dans `_build_prompt()` de `adapters/travelplanner/tools.py`

**Durée estimée** : 2-3 heures  
**Fichier cible** : `adapters/travelplanner/tools.py`, classe `PlanDayTool`, méthode `_build_prompt()` (ligne ~445)

### Ce que tu dois faire

1. **Charger 2 exemples few-shot depuis le split `train`** au moment de l'initialisation de `PlanDayTool.__init__()` :
   ```python
   # IMPORTANT : uniquement depuis le split "train", jamais "validation"
   from datasets import load_dataset
   ds = load_dataset("osunlp/TravelPlanner", "train", trust_remote_code=True)
   ```
   Choisir 2 exemples représentatifs du train :
   - 1 exemple avec `visiting_city_number=1` (cas simple)
   - 1 exemple avec `visiting_city_number >= 2` (cas multi-city)
   
   Les exemples doivent contenir la query + le plan correct attendu.

2. **Les injecter dans `_build_prompt()`** juste avant la section `"Use only plausible values..."` (ligne ~508) :
   ```
   Examples (from training split only):
   Example 1: <query_json> -> <plan_json>
   Example 2: <query_json> -> <plan_json>
   ```

3. **Ajouter dans le prompt** une consigne explicite pour le cas multi-city (quand `city_sequence` a >1 ville) :
   ```
   IMPORTANT for multi-city trips: You MUST include one day per city transition (transportation day) 
   and at least one stay day per intermediate city.
   ```

4. **Documenter dans un commentaire inline** quelle source est utilisée :
   ```python
   # Few-shot examples loaded from osunlp/TravelPlanner split="train" ONLY.
   # Never use split="validation" here — would contaminate the benchmark.
   ```

### Gestion du cas où le dataset n'est pas disponible

Si `load_dataset` échoue (pas de connexion, pas d'accès), `_build_prompt()` doit continuer sans les few-shots (pas de crash). Ajouter un try/except autour du chargement et logger un warning.

### Test d'acceptation T9

```bash
uv run pytest tests/ -q  # ≥ 235 passed
# Smoke run 5 queries :
uv run python scripts/run_travelplanner_query_export.py --query-idx 0 --config config/ablation/v5_full.yaml
```

Le prompt loggué doit contenir la section "Examples" ou un warning si le dataset n'est pas disponible.

---

## T8 — Script de tuning α/β sur split `train`

**Durée estimée** : 2h code + ~$15-25 API pour le run  
**Fichier à créer** : `scripts/tune_aco_travelplanner.py`  
**Contrainte absolue** : utiliser **uniquement** `split="train"` — zéro query du split `validation`

### Ce que le script doit faire

1. **Définir la grille** :
   ```python
   GRID = {
       "alpha": [0.5, 1.0, 1.5],
       "beta":  [1.0, 2.0, 3.0],
       "temperature": [0.1, 0.3],
   }
   # 3 × 3 × 2 = 18 combinaisons
   ```

2. **Pour chaque combinaison** :
   - Partir du preset `config/ablation/v5_full.yaml`
   - Override les valeurs `pressures.alpha`, `pressures.beta`, `agents.selection_temperature`
   - Runner 30 queries depuis le split `train` (indices 0 à 29), 2 seeds (42, 43)
   - Utiliser le script existant `scripts/run_travelplanner_framework_benchmark.py` avec `--split train --framework stigmergic --start 0 --end 29`
   - Collecter `final_pass_rate` et `delivery_rate`

3. **Sélectionner la meilleure combinaison** selon `final_pass_rate` maximal sur le train (en cas d'égalité, prendre le meilleur `delivery_rate`)

4. **Mettre à jour automatiquement `config/ablation/v5_full.yaml`** avec les valeurs gagnantes dans `pressures.alpha`, `pressures.beta`, `agents.selection_temperature`

5. **Sauvegarder les résultats** dans `output/tuning/tuning_results_<timestamp>.json` avec :
   - Toutes les 18 combinaisons + leurs scores
   - La combinaison retenue
   - Un commentaire rappelant que le tuning a été fait sur `split="train"` uniquement

### Interface CLI du script

```bash
uv run python scripts/tune_aco_travelplanner.py \
  --base-config config/ablation/v5_full.yaml \
  --split train \
  --n-queries 30 \
  --seeds 42 43 \
  --out-dir output/tuning \
  --apply          # met à jour v5_full.yaml avec les meilleurs hyperparams
```

### Test d'acceptation T8

```bash
# Dry-run sur 5 queries pour vérifier que le script tourne :
uv run python scripts/tune_aco_travelplanner.py \
  --base-config config/ablation/v5_full.yaml \
  --split train --n-queries 5 --seeds 42 --out-dir output/tuning
# Vérifier que output/tuning/tuning_results_*.json est créé
# Vérifier que config/ablation/v5_full.yaml est mis à jour après --apply
uv run pytest tests/ -q  # ≥ 235 passed
```

---

## Ordre d'exécution recommandé

```
1. T10  (10 min)  → créer config/ablation/v5_full.yaml
2. T7   (3-4h)   → marker shaping dans tools.py + test unitaire
3. T9   (2-3h)   → few-shots dans _build_prompt()
4. T8   (2h code + run) → script de tuning + run sur train + update v5_full.yaml
5. Vérification finale : uv run pytest tests/ -q → ≥ 235 passed
6. Lancer le benchmark V5-full (voir section suivante)
```

---

## Lancement du benchmark final

Une fois T7, T8, T9, T10 terminés, lancer le benchmark V5-full :

```bash
# Pour chaque seed (42, 43, 44), lancer :
uv run python scripts/run_travelplanner_framework_benchmark.py \
  --framework stigmergic \
  --config config/ablation/v5_full.yaml \
  --split validation \
  --start 0 --end 179 \
  --seed 42 \
  --out-dir output/travelplanner_framework_compare/<timestamp>/stigmergic_v5_seed42

# Répéter pour --seed 43 et --seed 44
```

### Comparaison avec V0

V0 = run existant `output/travelplanner_framework_compare/20260409_233919/` :
- StigmergiAgentic sans T0, sans T7, sans T8, sans T9, sans T10
- Scores : delivery=55.4%, final_pass=8.5% (référence)

V5-full = nouveau run après T0+V4+T7+T8+T9+T10 :
- Cible : delivery ≥ 70%, final_pass ≥ 12%

### Lire les résultats

```bash
cat output/travelplanner_framework_compare/<timestamp>/stigmergic_v5_seed42/benchmark_summary.json
cat output/travelplanner_framework_compare/<timestamp>/stigmergic_v5_seed42/official_eval.json
```

---

## Critères de succès global

- [ ] `uv run pytest tests/ -q` → ≥ 235 passed (après chaque tâche)
- [ ] `config/ablation/v5_full.yaml` existe avec `max_ticks: 80` et `num_agents: 6`
- [ ] `tests/unit/test_travelplanner_marker_shaping.py` passe (3 tests)
- [ ] `scripts/tune_aco_travelplanner.py` tourne sur le split `train` uniquement
- [ ] `config/ablation/v5_full.yaml` contient les hyperparams issus du tuning train
- [ ] Benchmark V5-full terminé sur 3 seeds × 180 queries
- [ ] `benchmark_summary.json` contient `failure_reasons` et `final_pass_rate`
- [ ] `official_eval.json` produit par le scorer officiel pour chaque seed

---

## Références fichiers clés

| Fichier | Rôle |
|---|---|
| `adapters/travelplanner/tools.py` | Cible T7 (shaping) + T9 (prompts). `PlanDayTool` ligne 127, `ValidateConstraintsTool` ligne 1181, `_build_prompt()` ligne ~445 |
| `config/travelplanner_v4_only.yaml` | Point de départ pour créer `v5_full.yaml` (T10) |
| `config/ablation/v5_full.yaml` | À créer (T10), mis à jour par T8 |
| `scripts/run_travelplanner_framework_benchmark.py` | Script benchmark déjà complet (T5 ✅) |
| `scripts/tune_aco_travelplanner.py` | À créer (T8) |
| `tests/unit/test_travelplanner_marker_shaping.py` | À créer (T7) |
| `output/travelplanner_framework_compare/20260409_233919/` | Run V0 de référence — ne pas toucher |
