# Plan V5.1 — Amélioration scientifique du framework StigmergiAgentic

**Date** : 2026-04-12 (v5.1-final — corrigé suite double revue expert)
**Baseline empirique** : run `20260409_233919` (qwen3.5-9b, 3 seeds × 180 queries × 6 bras)
**Score actuel** : StigmergiAgentic Final Pass = 8.5 ± 0.6% (+107% vs Direct Solo 4.1%)
**Cible v5** : Final Pass ≥ 12% à backbone constant, sans tricher, sur le même split validation

---

## Changelog v5 → v5.1

| Correction | Raison |
| --- | --- |
| **Nouvelle T0** : refonte multi-city de l'adaptateur TravelPlanner | Cause structurelle n°1 du delivery_rate à 55% — l'adaptateur encode un seul dest par query alors que TravelPlanner a des queries multi-city |
| **T2 reformulée** : failure taxonomy query-level | `stop_reason` existe déjà dans `core/orchestrator.py:42` et est exporté dans `main.py:267` — pas besoin de le réinventer. Le vrai besoin est une taxonomie d'échec au niveau de chaque query |
| **T4 reformulée** : diagnostic précis avant patch | Le problème n'est pas la signature `runner.run_query` mais une sortie JSON tronquée/invalidée autour de `scientific_baselines.py:335` — ou un crash multi-city dans `_inject_default_search_payloads` |
| **T5 reformulée** : robustesse campagne, pas retry LLM | `llm/client.py:213-280` a déjà retry + backoff + `_is_retryable` + `min_429_backoff_seconds`. Le vrai problème est la résilience au niveau campagne (reprise partielle, 429 cumulés sur 180+ queries) |
| **T6 refondue** : ablation incrémentale (7 configs au lieu de 2) | Le plan v5 original mélangeait V4 + heuristique + tuning + prompts + agents dans un seul preset → 7 variables confondues. Chaque transition doit isoler une seule variable |
| **T9 corrigée** : cibler `tools.py:437` pas `llm/prompts.py` | Les prompts TravelPlanner sont construits dans `adapters/travelplanner/tools.py:437`, pas dans `llm/prompts.py` qui contient les prompts core |
| **T11 corrigée** : McNemar exact au lieu de Wilcoxon | `final_pass` est binaire (pass/fail) — Wilcoxon est pour des métriques continues appariées. McNemar exact (ou sign test) est le test canonique pour du binaire apparié |
| **T0 durcie (v5.1-final)** : construction `city_sequence` pas simple parsing | `dest` dans `workspace.py:365` est un scalaire. Il faut construire une séquence de N villes depuis `visiting_city_number` + la DB TravelPlanner, pas parser une chaîne |
| **T5 durcie (v5.1-final)** : continue-on-error, pas checkpointing | Le checkpoint par query existe déjà (`run_travelplanner_framework_benchmark.py:298-300`). Le vrai fix est de remplacer le `raise RuntimeError` (ligne 318) par un `continue` avec `failure_reason` |
| **T7 durcie (v5.1-final)** : marker shaping au lieu d'injection heuristique | `heuristic_fn` dans `core/agent.py:272` n'existe que sous `local_sensing`. Pas de hook domain générique. Option recommandée : shaping des markers (intensité/inhibition) dans l'adaptateur, core intact |

---

## Contexte rapide

La campagne `output/travelplanner_framework_compare/20260409_233919/` compare 6 philosophies d'organisation multi-agents à backbone constant (`qwen/qwen3.5-9b` via OpenRouter) sur le split `validation` TravelPlanner (180 queries × 3 seeds, scorer officiel).

**Résultats observés** (pack scientifique reconstruit le 2026-04-12 après correction des baselines) :

| Philosophy | Seeds | Delivery | CS Macro | HC Micro | HC Macro | **Final Pass** |
| --- | --- | --- | --- | --- | --- | --- |
| Direct Solo | 3/3 | 57.9 ± 0.6 | 15.0 ± 0.6 | 19.8 ± 0.8 | 12.2 ± 0.6 | **4.0 ± 0.6** |
| CoT Solo | 3/3 | 51.0 ± 0.6 | 17.6 ± 0.8 | 21.4 ± 0.6 | 11.8 ± 0.6 | **5.8 ± 0.3** |
| Self-Refine Solo | 2/3 | 56.4 ± 0.4 | 18.3 ± 0.0 | 20.9 ± 1.1 | 12.2 ± 0.8 | **8.3 ± 0.0** |
| Central Planner-Executor | 3/3 | 58.5 ± 0.3 | 1.1 ± 0.6 | 20.6 ± 0.6 | 14.8 ± 0.9 | **0.9 ± 0.3** |
| Central Graph Supervisor | 3/3 | 56.8 ± 2.3 | 8.9 ± 0.6 | 18.8 ± 0.6 | 12.4 ± 1.2 | **2.2 ± 0.0** |
| **StigmergiAgentic** | 3/3 | 55.4 ± 0.3 | 15.2 ± 1.2 | **22.8 ± 0.6** | **14.0 ± 0.6** | **8.5 ± 0.6** |

**Pairwise McNemar exact (StigmergiAgentic vs chaque baseline)** :

| Comparaison | Wins/Losses/Ties | Δ Final Pass | McNemar p | CI 95% | Lecture |
| --- | --- | --- | --- | --- | --- |
| vs Direct Solo | 9/3/168 | +3.3pp | 0.1460 | [-0.6, 7.2] | Avantage non significatif |
| vs CoT Solo | 6/2/172 | +2.2pp | 0.2891 | [-0.6, 5.6] | Avantage non significatif |
| vs Self-Refine Solo | 5/6/169 | -0.6pp | 1.0000 | [-3.9, 2.8] | Parité (Self-Refine aussi itératif) |
| **vs Central Planner-Executor** | **12/0/168** | **+6.7pp** | **0.0005** | [3.3, 10.6] | **Hautement significatif** |
| **vs Central Graph Supervisor** | **13/3/164** | **+5.6pp** | **0.0213** | [1.7, 10.0] | **Significatif à 5%** |

**Classement Final Pass** : StigmergiAgentic (8.5%) > Self-Refine (8.3%, 2/3) > CoT (5.8%) > Direct (4.0%) > Graph Supervisor (2.2%) > Planner-Executor (0.9%)

**Observation clé** : la hiérarchie est inversée — les architectures **les plus centralisées sont les pires**. Planner-Executor a le meilleur delivery_rate (58.5%) mais le pire final_pass (0.9%) : il livre beaucoup de plans, mais presque tous incorrects (commonsense_macro = 1.1%). C'est le mode d'échec "Disobey Task Specification" identifié par MAST (Cemri et al., 2025). La coordination stigmergique produit moins de plans mais de bien meilleure qualité.

**Self-Refine à parité** : la parité avec Self-Refine (p=1.0) n'est pas une faiblesse — Self-Refine est un pattern itératif (critique → révise), pas hiérarchique. La stigmergie bat les centralisés, pas les itératifs. C'est un résultat cohérent avec la thèse.

**Note** : Self-Refine Solo reste à 2/3 seeds (seed 43 a échoué — erreur `scientific_baselines.py:449` dans `_call_llm`). À fixer pour publication (T3).

**Cause racine identifiée (v5.1)** : le goulot principal n'est pas un problème de prompts ou d'hyperparams — c'est un **défaut structurel multi-city**. L'adaptateur dans `adapter.py:181-263` encode un seul aller-retour `org → dest → org` et crée un seul set hotels/restaurants pour `dest`, alors que TravelPlanner a des queries avec `visiting_city_number > 1` (parcours multi-villes sur 3, 5 ou 7 jours). Le delivery_rate à 55% et le plafond final_pass à 8.5% en découlent directement.

---

## Objectifs du plan v5.1

1. **Corriger le goulot structurel multi-city** dans l'adaptateur TravelPlanner pour augmenter le delivery_rate
2. **Quantifier la contribution des 5 corrections V4** via ablation incrémentale propre (une seule variable par transition)
3. **Fixer les 3 baselines défaillantes** pour obtenir des comparaisons signées
4. **Tuner les hyper-paramètres stigmergiques** sur le split `train` uniquement
5. **Ajouter une heuristique ACO domain-aware** dans l'adaptateur (pas le core)
6. **Publier les résultats finaux** avec McNemar exact (binaire) + bootstrap CI95 (continues) + frontière Pareto

---

## Contraintes absolues (ne pas tricher)

- ❌ **Aucune exposition aux queries du split `validation`** pendant le tuning, les prompts few-shot, les heuristiques ou la mémoire. Tout doit venir du split `train`.
- ❌ **Aucune modification** de `third_party/travelplanner_official/` ni de `scripts/eval_travelplanner_official.py`.
- ❌ **`markers.session_isolation: true`** doit rester activé — pas de persistance inter-queries.
- ❌ **Aucun hardcoding domain-specific dans `core/`** — toute logique TravelPlanner reste dans `adapters/travelplanner/`.
- ❌ **Pas de changement de backbone** entre bras d'une même campagne.
- ✅ **Autorisé** : activation des features V4, tuning hyperparams, amélioration prompts avec few-shots train, heuristique ACO domain-aware dans l'adaptateur, fixes bugs baselines, refonte multi-city dans l'adaptateur.
- ✅ **Obligatoire** : chaque modification de code doit passer `uv run pytest tests/ -q` (actuellement 235 passed).

---

## Tâches d'exécution

### T0 — Construction de la séquence de villes (city sequence) dans l'adaptateur TravelPlanner

- **Priorité** : P0 (cause racine — doit passer avant T6)
- **Effort** : 5-8h
- **Diagnostic** : les queries TravelPlanner avec `visiting_city_number > 1` produisent des itinéraires multi-villes. Or le pipeline entier traite `dest` comme un scalaire :
  - `workspace.py:365` normalise `dest` en `str(raw.get("dest", "")).strip()` → scalaire
  - `adapter.py:181` crée un seul marker flights vers `query.get("dest")`
  - `adapter.py:263` crée un seul marker hotels pour `query.get("dest")`
  - `tools.py:528` injecte les search fallbacks pour un seul `city = query.get("dest")`
  - `tools.py:753` souffre du même biais single-city
  - L'itinéraire final rate les villes intermédiaires → échec commonsense/hard constraints → final_pass = 0
- **Pourquoi "parser `dest` comme liste" ne suffit pas** : dans TravelPlanner, `dest` est souvent un seul nom de ville (la destination principale), et `visiting_city_number` indique combien de villes le voyageur doit visiter. Les villes candidates doivent être **inférées** depuis la base de données TravelPlanner (villes accessibles depuis `org`, proches de `dest`, dans le même état/région) — pas simplement parsées depuis la chaîne `dest`.
- **Architecture de la solution** :
  1. **Étape 1 : construire `city_candidates`** dans `adapters/travelplanner/workspace.py` ou `adapter.py` :
     - Lire `visiting_city_number` depuis la query (ex : 3)
     - Lire `dest` comme la destination principale (ex : "Denver")
     - Interroger la base de données TravelPlanner (table `cities` ou équivalent) pour trouver les N-1 villes candidates accessibles depuis `org` et voisines de `dest`
     - Si la base ne suffit pas, utiliser les villes qui apparaissent dans les résultats de `search_flights` comme destinations intermédiaires
     - Produire une `city_sequence: list[str]` ordonnée (ex : `["Minneapolis", "Denver", "Boulder"]`)
  2. **Étape 2 : générer les markers par ville** dans `adapter.py:initial_markers()` :
     - Pour chaque ville de `city_sequence` : un set de markers `search_hotels_{city}`, `search_restaurants_{city}`, `search_attractions_{city}`
     - Des markers de transition inter-city (flights/ground entre villes consécutives) avec `depends_on` vers la ville précédente
     - Le marker `plan_itinerary` dépend de **tous** les markers search de **toutes** les villes
  3. **Étape 3 : adapter les search tools** dans `tools.py` :
     - `_inject_default_search_payloads()` (ligne 528) : itérer sur `city_sequence` au lieu d'un seul `city`
     - Générer des clés séparées par ville : `search_hotels_Denver`, `search_hotels_Boulder`, etc.
  4. **Étape 4 : adapter le prompt de planification** dans `tools.py` :
     - `_build_planning_prompt()` (ligne 437) : mentionner les N villes dans l'ordre de visite, avec les search data par ville
     - Ajouter une consigne explicite : "Visit these cities in order: ..."
- **Fichiers à toucher** :
  - `adapters/travelplanner/workspace.py` — ajouter une méthode `build_city_sequence(query) -> list[str]` qui interroge la DB
  - `adapters/travelplanner/adapter.py` — refactorer `initial_markers()` pour itérer sur `city_sequence`
  - `adapters/travelplanner/tools.py` — `_inject_default_search_payloads()` et `_build_planning_prompt()`
- **Test d'acceptation** :
  - Nouveau test unitaire `tests/unit/test_travelplanner_multi_city.py` :
    - Une query avec `visiting_city_number=3` produit ≥ 3 markers search_hotels, ≥ 3 search_restaurants, ≥ 3 search_attractions
    - Les markers inter-city ont des `depends_on` cohérents formant un DAG linéaire
    - `build_city_sequence()` retourne exactement `visiting_city_number` villes
  - Smoke run : 10 queries multi-city (choisir dans le split **train**) → delivery_rate ≥ 50% sur ces 10
  - Tests existants passent : `uv run pytest tests/ -q` → ≥ 235 passed
- **Contrainte** : toute la logique multi-city reste dans `adapters/travelplanner/`. Le `core/` ne change pas.
- **Impact attendu** : c'est le **levier #1** — une fois que le framework voit les bonnes villes, il peut produire des plans corrects. Gain attendu : delivery_rate +10 à +20pp, final_pass +3 à +6pp.

### T1 — Créer le preset V4-only (pas V4-full)

- **Priorité** : P0 (critique)
- **Effort** : 30 min
- **Fichier à créer** : `config/travelplanner_v4_only.yaml`
- **Actions** :
  1. Copier `config/travelplanner.yaml` vers `config/travelplanner_v4_only.yaml`
  2. Fixer explicitement :
     - `agents.local_sensing.enabled: true`
     - `markers.time_decay.enabled: true`
     - `reinforcement.frequentation.enabled: true`
     - `orchestrator.emergent_resolution.enabled: true`
     - `emergence.feedback_loop.enabled: true`
  3. **Ne pas changer** : `alpha`, `beta`, `temperature`, `num_agents`, `max_ticks` (rester aux valeurs par défaut)
  4. Garder `markers.session_isolation: true` (anti-tricherie)
  5. Commentaire en tête : `# V4-only preset — active les 5 corrections stigmergiques V4 sans autre changement. Pour ablation pure.`
- **Test d'acceptation** : `uv run python main.py --adapter travelplanner --config config/travelplanner_v4_only.yaml --objective "Query 0"` termine sans erreur.
- **Note** : ce preset mesure l'apport des corrections V4 **seules**, sans contamination par le tuning ou les prompts (cf. erreur méthodologique corrigée en v5.1).

### T2 — Failure taxonomy query-level dans l'adaptateur

- **Priorité** : P0 (critique)
- **Effort** : 2-3h
- **Contexte** : `core/orchestrator.py:42` expose déjà `stop_reason: str` dans `OrchestratorResult` et `main.py:267` le propage dans le JSON. **Le core n'a pas besoin d'être modifié.** Ce qui manque, c'est une taxonomie d'échec granulaire **au niveau query** dans l'adaptateur.
- **Fichiers à toucher** :
  - `adapters/travelplanner/adapter.py` : à la fin de `evaluate_run()` ou équivalent, ajouter un champ `failure_reason: str` dans le résultat par query, avec les valeurs :
    - `ok` — plan livré et évalué normalement
    - `empty_plan_from_llm` — le LLM retourne `[]` ou un plan vide
    - `empty_plan_after_max_attempts` — parsing fail sur toutes les retries
    - `validator_replan_exhausted` — la boucle `validate_constraints` dépasse `max_retries`
    - `schema_parse_failed` — le JSON output LLM est invalide
    - `missing_search_results` — les dépendances search ne sont pas toutes résolues
    - `multi_city_unsupported` — query multi-city non gérée (avant T0)
    - `budget_exhausted` / `max_ticks` / `idle_cycles` — reprend le `stop_reason` de l'orchestrateur
  - `scripts/run_travelplanner_framework_benchmark.py` : logger `failure_reason` par query dans le pack scientifique (`runs.json`)
- **Test d'acceptation** :
  - `uv run pytest tests/ -q` → ≥ 235 passed
  - Un run de 10 queries montre une distribution `failure_reason` exploitable dans les logs
- **Contrainte** : ne pas modifier `core/orchestrator.py` (il est déjà correct).

### T3 — Fixer Self-Refine Solo baseline seed 43 (2/3 → 3/3)

- **Priorité** : P0 (critique)
- **Effort** : 1-2h
- **État actuel** : seeds 42 et 44 fonctionnent (8.3% final_pass chacune). Seed 43 échoue avec `scientific_baselines.py:449` dans `_call_llm`. Résultats valides : delivery=56.4%, cs_macro=18.3%, final_pass=8.3%.
- **Diagnostic préalable** (avant tout patch) :
  1. Exécuter un micro-run unitaire : 1 query × seed 43 pour `solo_self_refine` avec logging verbeux
  2. Capturer le traceback complet à la ligne 449
  3. Hypothèses à tester : (a) erreur LLM provider (429/timeout) spécifique à la seed 43 sur le volume de 180 queries ; (b) parsing JSON du self-critique ; (c) exception non-retriable non capturée
- **Fichier à toucher** : `adapters/travelplanner/scientific_baselines.py` — fonction `_call_llm` autour de la ligne 449
- **Contrainte** : **ne pas changer la philosophie Self-Refine** (iteratively critique + revise). Juste corriger le bug d'intégration.
- **Test d'acceptation** : campagne pilot (10 queries × seed 42) produit 1/1 successful full run pour `solo_self_refine`.

### T4 — Fixer Central Planner-Executor baseline (0/3)

- **Priorité** : P0 (critique)
- **Effort** : 1-2h
- **Diagnostic préalable** (avant tout patch) :
  1. Exécuter un micro-run unitaire : 1 query × seed 42 pour `planner_executor` avec logging verbeux
  2. Hypothèses à tester (par ordre de probabilité) :
     - (a) `max_response_tokens` trop bas → blueprint JSON tronqué en sortie de `_call_schema` à `scientific_baselines.py:335`
     - (b) crash dans `_inject_default_search_payloads` → query multi-city (cause commune T0)
     - (c) exception non-capturée en amont de `_call_schema` (pas `ValidationError`/`json.JSONDecodeError`)
  3. **Ne pas** partir du principe que c'est la signature `runner.run_query` — le fallback à `scientific_baselines.py:341-353` est déjà implémenté
- **Fichier à toucher** : `adapters/travelplanner/scientific_baselines.py`
- **Contrainte** : préserver l'architecture planner → executor séquentielle
- **Test d'acceptation** : campagne pilot 10 queries/seed 42 → 1/1 success pour `planner_executor`

### T5 — Continue-on-error et robustesse campagne

- **Priorité** : P0 (critique)
- **Effort** : 2h
- **Contexte** :
  - `llm/client.py:213-280` a déjà retry + backoff + `_is_retryable` + `min_429_backoff_seconds`. **Ne pas toucher au client LLM.**
  - Le checkpoint par query **existe déjà** (`run_travelplanner_framework_benchmark.py:298-300` : `if result_path.exists() and not args.force: runs.append(...); continue`).
  - **Le vrai problème** : la ligne 318-323 fait `raise RuntimeError(...)` au premier `returncode != 0`, tuant la seed entière. Sur 180 queries, un seul échec (429 cumulé, timeout Docker, JSON tronqué) fait perdre tout le run.
- **Le fix ciblé** (dans `scripts/run_travelplanner_framework_benchmark.py`) :
  1. **Remplacer le `raise RuntimeError` (ligne 318-323)** par un `continue` avec logging :
     - Capturer `failure_reason` (codes : `exporter_crash`, `timeout`, `returncode_nonzero`)
     - Écrire un `result_path` avec `{"query_idx": N, "status": "failed", "failure_reason": "...", "stderr_tail": "..."}` pour que le checkpoint fonctionne à la reprise
     - Continuer à la query suivante
  2. **Ajouter un compteur `failed_queries`** et un seuil de tolérance (ex : si > 30% des queries échouent, avertir mais ne pas crasher)
  3. **À la fin de la seed**, loguer le ratio `succeeded/total` et `failure_reason` distribution dans `benchmark_summary.json`
  4. **Documenter explicitement la sémantique du scorer officiel** :
     - `scripts/eval_travelplanner_official.py` évalue la plage complète de queries demandée
     - Une query manquante dans `runs.json` est traitée comme un plan vide `[]`, donc comme un échec sur le dénominateur complet
     - T5 améliore la résilience de campagne et la traçabilité des échecs, **pas** le dénominateur de l'évaluation officielle
  - `llm/client.py` (vérification seulement) :
    - Vérifier que `_is_retryable` catche bien `RateLimitError`, `APIConnectionError`, codes HTTP 429/502/503
    - Si manquant, ajouter ces types — sinon ne rien toucher
- **Test d'acceptation** :
  - Relancer un arm/seed qui échouait avant sur une query → la seed continue et produit un `official_eval.json` sur le dénominateur complet, avec les queries ratées comptées comme échecs documentés
  - Le `benchmark_summary.json` contient `"failed_queries": k, "failure_reasons": {...}`
- **Contrainte** : ne pas modifier la logique de retry interne au client LLM. Ne pas ajouter du checkpointing qui existe déjà.

### T6 — Campagne ablation incrémentale (7 configs)

- **Priorité** : P0 (critique, dépend de T0, T1, T2, T3-T5)
- **Effort** : ~8-16h wall-clock (7 configs × 3 seeds × 180 queries)
- **Principe méthodologique** : **une seule variable change par transition**. Cela produit une ablation scientifiquement propre où l'apport de chaque correction est isolé et mesurable.
- **Configs à exécuter** :

| Config | Description | Variable ajoutée |
| --- | --- | --- |
| **V0** | Baseline actuelle (V4-off, code v5.0) | — (référence) |
| **V0+MC** | V0 + refonte multi-city (T0) | Multi-city |
| **V4** | V0+MC + 5 corrections V4 (`travelplanner_v4_only.yaml`) | Local sensing, time decay, frequentation, emergent resolution, feedback loop |
| **V4+H** | V4 + heuristique ACO domain-aware (T7) | Heuristique |
| **V4+H+P** | V4+H + prompts enrichis (T9) | Prompts |
| **V4+H+P+T** | V4+H+P + hyperparams tunés sur train (T8) | α, β, temperature |
| **V5-full** | V4+H+P+T + max_ticks=80, num_agents=6 (T10) | Resources |

- **Seeds** : 42, 43, 44
- **Queries** : 180 (split validation)
- **Pack scientifique** : stocker dans `output/travelplanner_framework_compare/<timestamp>/` avec le tag `v5.1_incremental_ablation`
- **Test d'acceptation** :
  - `paper_table_primary.csv` contient les 7 configs + les baselines externes (Direct, CoT, Self-Refine, Planner-Executor, Graph Supervisor)
  - Statistiques pairwise pour chaque transition consécutive (V0→V0+MC, V0+MC→V4, V4→V4+H, V4+H→V4+H+P, V4+H+P→V4+H+P+T, V4+H+P+T→V5-full)
  - McNemar exact sur `final_pass` (binaire, unité = query appariée, N=180 paires par seed, poolé sur 3 seeds = 540 paires) pour chaque paire consécutive
  - Wilcoxon signed-rank sur `delivery_rate` et `hard_constraint_macro` (continues, unité = score moyen par seed, N=3 observations appariées par paire de configs — **attention : N=3 est faible pour Wilcoxon, considérer bootstrap CI95 comme complément ou pooler au niveau query**)
- **Contrainte** : les configs doivent être versionnées dans `config/ablation/` (un fichier YAML par config). Chaque config ne diffère de la précédente que par un seul groupe de paramètres.

### T7 — Heuristique domain-aware pour TravelPlanner

- **Priorité** : P1 (renforcement, mesuré comme étape V4+H dans T6)
- **Effort** : 3-5h
- **Contexte technique** : dans `core/agent.py:272-288`, `heuristic_fn` est créé **seulement** si `local_sensing.enabled = True`, et il est hardcodé sur `_affinity_heuristic`. Il n'existe pas de hook générique `domain_heuristic_fn` dans le core. Deux options :

  **Option A — Marker shaping dans l'adaptateur (recommandée, core intact)** :
  Au lieu d'injecter une fonction heuristique dans `compute_pressures`, influencer les décisions en **shaping les markers eux-mêmes** côté adaptateur :
  - Quand un tool `validate_constraints` détecte des violations, augmenter l'`intensity` et réduire l'`inhibition` du marker `plan_itinerary` (pour provoquer un replan)
  - Quand un tool `search_*` retourne des résultats vides, augmenter l'`intensity` du marker correspondant (pour que les agents le reprennent)
  - Quand des `commonsense_violations` sont détectées, augmenter l'`inhibition` du marker fautif
  - Cela se fait dans les callbacks `ActionResult` des tools, dans `adapters/travelplanner/tools.py`
  - **Avantage** : le `core/` reste 100% intact. Les modifications sont localisées dans l'adaptateur.
  - **Inconvénient** : moins élégant qu'une vraie heuristique ACO — on influence les entrées du calcul de pression, pas la formule elle-même.

  **Option B — Extension propre du core (petite modification)** :
  Ajouter un paramètre optionnel `domain_heuristic_fn` à `StigmergicAgent.__init__()` :
  - Si fourni, il est composé avec l'`_affinity_heuristic` (si local_sensing est activé) ou utilisé seul
  - L'adaptateur injecte sa fonction via `DomainAdapter.create_agents()` ou un hook de configuration
  - **Avantage** : plus propre architecturalement, conforme au pattern `heuristic_fn` de `compute_pressures`
  - **Inconvénient** : modification (petite) du `core/` — à justifier dans l'ADR

  **Choix recommandé** : **Option A** pour le plan v5.1 (core intact, résultat mesurable dans l'ablation). L'Option B peut être implémentée en v6 après validation empirique.

- **Fichiers à toucher (Option A)** :
  - `adapters/travelplanner/tools.py` : dans les méthodes `execute()` de `ValidateConstraintsTool` et `PlanItineraryTool`, ajuster `intensity` et `inhibition` du marker résultat selon la qualité du résultat
  - Les ajustements sont basés uniquement sur la *structure des markers* (payload violations, résultats vides), pas sur les queries du validation split
- **Règles de shaping** :
  - Si `validate_constraints` retourne des violations → marker `plan_itinerary` : `intensity` remonté à 0.9, `inhibition` réduit à 0.0 (stimule le replan)
  - Si un search tool retourne `results: []` → marker search correspondant : `intensity` maintenu élevé (stimule la retry)
  - Si `commonsense_violations` détectées → marker fautif : `inhibition` augmenté de 0.3 (décourage la réutilisation du même chemin)
- **Test d'acceptation** :
  - Nouveau test unitaire `tests/unit/test_travelplanner_marker_shaping.py` qui vérifie les 3 règles de shaping
  - Run de smoke : 10 queries → delivery_rate et Final Pass ne régressent pas
- **Contrainte** : aucune modification de `core/`. Le shaping ne peut pas dépendre de la query courante, uniquement de l'état des markers dans l'environnement.

### T8 — Tuning α/β sur subset train

- **Priorité** : P1 (mesuré comme étape V4+H+P+T dans T6)
- **Effort** : ~4h wall-clock + budget API
- **Fichiers à créer/toucher** :
  - `scripts/tune_aco_travelplanner.py` (nouveau) — grid search limité
  - Utilise le split `train` uniquement (vérifier disponibilité via `datasets.load_dataset("osunlp/TravelPlanner", "train")`)
- **Grid** : `alpha ∈ {0.5, 1.0, 1.5}` × `beta ∈ {1.0, 2.0, 3.0}` × `temperature ∈ {0.1, 0.3}` = 18 combinaisons
- **Échantillon** : 30 queries du train par combinaison, 2 seeds → 1080 runs LLM max
- **Critère** : retenir la combinaison maximisant Final Pass sur le **train**
- **Résultat** : créer `config/ablation/v4_hpt.yaml` avec les meilleurs hyperparams (séparé de `travelplanner_v4_only.yaml` pour garder l'ablation propre)
- **Contrainte** : **ZÉRO** query du `validation` split touchée pendant ce tuning. Commit explicite sur ce point.

### T9 — Améliorer les prompts tools avec few-shots train

- **Priorité** : P1 (mesuré comme étape V4+H+P dans T6)
- **Effort** : 2-3h
- **Fichier à toucher** : `adapters/travelplanner/tools.py` (fonction `_build_planning_prompt` autour de la **ligne 437**, **pas** `llm/prompts.py` qui contient les prompts core)
- **Actions** :
  1. Pour la fonction de planning (ligne 437) : ajouter 1-2 exemples few-shot issus du split `train` (queries + plans corrects, incluant des cas multi-city)
  2. Pour `validate_constraints` : forcer le format JSON `{ "violations": [...], "suggestions": [...] }`
  3. Adapter le prompt au contexte multi-city (après T0) : mentionner explicitement les N villes à visiter dans l'ordre
- **Contrainte** : les exemples few-shots doivent provenir de `load_dataset("osunlp/TravelPlanner", "train")`. Jamais de `validation`. Documenter explicitement dans un commentaire inline quel split est utilisé.
- **Test d'acceptation** : tests existants passent + smoke run 10 queries avec delivery_rate ≥ 65%

### T10 — Augmenter `max_ticks` et `num_agents`

- **Priorité** : P2 (mesuré comme étape V5-full dans T6)
- **Effort** : 1h
- **Fichier à toucher** : `config/ablation/v5_full.yaml` (pas le default, pas le v4_only)
- **Actions** :
  - `orchestrator.max_ticks: 80`
  - `agents.num_agents: 6`
- **Test d'acceptation** : pilot run 20 queries, delivery_rate ne régresse pas

### T11 — Tests statistiques appropriés

- **Priorité** : P1
- **Effort** : 1-2h
- **Fichiers à créer/toucher** :
  - `metrics/significance.py` (nouveau module généraliste) :
    - `mcnemar_exact(wins, losses)` → p-value (test exact binomial sur les paires discordantes) — **pour métriques binaires** comme `final_pass`
    - `wilcoxon_signed_rank(values_a, values_b)` → p-value — **pour métriques continues** comme `delivery_rate`, `hard_constraint_macro`
    - `bootstrap_ci95(values, n_resamples=1000)` → (low, high) — pour intervalles de confiance
  - `scripts/run_travelplanner_framework_benchmark.py` ou notebook : utiliser `metrics/significance.py` pour les pairwise
- **Choix du test selon la métrique** :
  - `final_pass` (binaire pass/fail par query) → **McNemar exact** sur la table 2×2 des discordances (wins=A réussit & B échoue, losses=A échoue & B réussit)
  - `delivery_rate`, `commonsense_macro`, `hard_constraint_macro` (continues, appariées) → **Wilcoxon signed-rank** ou **t-test apparié**
- **Test d'acceptation** :
  - `paper_table_primary.csv` contient `final_pass_mcnemar_p` et `delivery_rate_wilcoxon_p`
  - `paper_table_primary.csv` contient `final_pass_ci95_low` et `final_pass_ci95_high`
- **Contrainte** : `metrics/significance.py` doit être généraliste (pas d'import de `adapters/travelplanner/`)

### T12 — Frontière de Pareto coût/précision

- **Priorité** : P1
- **Effort** : 1h
- **Fichier à toucher** : `metrics/pareto.py` (existe déjà)
- **Action** : exécuter sur les 7 configs d'ablation + baselines externes et produire `output/.../pareto_v5.png` + `pareto_v5.csv`
- **Axes** : tokens LLM cumulés (coût) × Final Pass (précision)
- **Test d'acceptation** : figure PNG lisible dans le pack scientifique

### T13 — Rédiger un ADR v5.1

- **Priorité** : P1 (tracer les changements pour le mémoire)
- **Effort** : 1h
- **Fichier à créer** : `documentation/decisions/20260412-sprint7-v5-benchmark-improvements.md`
- **Contenu** :
  - Context : 8.5% baseline, goulot multi-city identifié, erreur méthodologique d'ablation corrigée
  - Decision : T0-T12, ablation incrémentale 7 configs
  - Consequences : nouvelles métriques, tests McNemar/Wilcoxon, frontière Pareto
  - Validation evidence : résultats campagne v5.1

---

## Critères d'acceptation globaux du plan v5.1

- [ ] `uv run pytest tests/ -q` → ≥ 235 passed (pas de régression)
- [ ] T0 : queries multi-city (visiting_city_number > 1) produisent des markers par ville
- [ ] Campagne ablation incrémentale complète : 7 configs × 3 seeds × 180 queries
- [ ] Baselines externes fixées : Self-Refine 3/3 (actuellement 2/3 — seed 43 manquante), Planner-Executor 3/3 ✅, Graph Supervisor 3/3 ✅
- [ ] StigmergiAgentic V5-full Final Pass **≥ 12%** (vs 8.5% baseline V4-off)
- [ ] StigmergiAgentic V5-full delivery_rate **≥ 75%** (vs 55.4% baseline)
- [ ] Chaque transition d'ablation mesurée avec son propre p-value (McNemar pour binaire, Wilcoxon pour continu)
- [ ] Au moins 2 transitions consécutives statistiquement significatives (p < 0.05)
- [ ] CI95 bootstrap exportés dans le pack scientifique
- [ ] Frontière Pareto générée et discutée dans l'ADR
- [ ] Aucune modification de `core/` au-delà de ce qui est déjà implémenté
- [ ] Aucune modification de `third_party/travelplanner_official/`
- [ ] Documentation `documentation/redisgn_v2/sprint_07_artifact.md` mise à jour

---

## Dépendances entre tâches

```text
T0 (multi-city) ──────────────┐
T1 (preset v4_only) ──────────┤
T2 (failure taxonomy) ────────┤
T3 (fix self-refine) ─────────┤
T4 (fix planner-executor) ────┤
T5 (robustesse campagne) ─────┤
                               │
T7 (heuristique) ─────────────┤    (chaque T7-T10 produit un config/ablation/*.yaml)
T8 (tuning α/β sur train) ────┤
T9 (prompts tools.py) ────────┤
T10 (max_ticks, num_agents) ───┤
                               │
                               └──> T6 (ablation incrémentale) ──> T11 ──> T12 ──> T13
```

- **T0** : indépendant, P0, **doit être fait en premier** (4-6h)
- **T1** : indépendant de T0 (30 min)
- **T2-T5** : parallèles à T0 (baseline fixes + instrumentation)
- **T7-T10** : parallèles, produisent chacun leur fichier config dans `config/ablation/`
- **T6** : dépend de **tout le reste** — c'est la campagne finale qui combine les 7 configs
- **T11** : après T6 (analyse statistique)
- **T12** : après T11 (Pareto sur résultats signés)
- **T13** : en dernier (ADR de consolidation)

**Règle critique** : T7, T8, T9, T10 ne contaminent **jamais** le preset `travelplanner_v4_only.yaml`. Chaque tâche crée son propre preset incrémental dans `config/ablation/`. L'ablation T6 les empile dans l'ordre.

---

## Budget API estimé

- **T6** (ablation incrémentale) : 7 configs × 3 seeds × 180 queries ≈ 3780 runs LLM → ~$25-50 sur qwen3.5-9b
- **T8** (tuning) : 18 combos × 2 seeds × 30 queries = 1080 runs → ~$15-25
- **Smoke runs + debugging** (T0, T3-T5, T7, T9) : ~$15-30
- **Total estimé** : $55-105 pour l'ensemble du plan v5.1

---

## Livrables finaux

1. `adapters/travelplanner/adapter.py` (refonte multi-city T0 + heuristique ACO T7)
2. `adapters/travelplanner/tools.py` (multi-city search fallbacks T0 + prompts enrichis T9)
3. `adapters/travelplanner/scientific_baselines.py` (baselines fixées T3-T4)
4. `config/travelplanner_v4_only.yaml` (preset V4-pure T1)
5. `config/ablation/` (7 presets d'ablation incrémentale T6)
6. `scripts/run_travelplanner_framework_benchmark.py` (robustesse campagne T5 + failure taxonomy T2)
7. `scripts/tune_aco_travelplanner.py` (nouveau script de tuning train-only T8)
8. `metrics/significance.py` (nouveau module McNemar + Wilcoxon + bootstrap T11)
9. `metrics/pareto.py` (exécuté sur ablation T12)
10. `tests/unit/test_travelplanner_multi_city.py` (nouveau test T0)
11. `tests/unit/test_travelplanner_marker_shaping.py` (nouveau test T7)
12. `output/travelplanner_framework_compare/<v5.1_timestamp>/scientific_pack/` (campagne complète)
13. `documentation/decisions/20260412-sprint7-v5-benchmark-improvements.md` (ADR T13)
14. `documentation/redisgn_v2/sprint_07_artifact.md` (sprint closure)

---

## Posture scientifique

Ce plan v5.1 ne cherche pas à **maximiser aveuglément** le score. Il cherche à :

1. **Identifier et corriger la cause racine** (multi-city) plutôt que de compenser par des hyperparams
2. **Isoler proprement la contribution de chaque correction** via ablation incrémentale — une seule variable par transition
3. **Utiliser les bons tests statistiques** : McNemar exact pour le binaire (final_pass), Wilcoxon pour le continu (delivery_rate)
4. **Maintenir la philosophie stigmergique intacte** : aucune logique hiérarchique réintroduite dans `core/`
5. **Rester reproductible** : tous les hyperparams, splits, configs et seeds sont documentés et versionnés
6. **Ne jamais tricher** sur le split `validation` qui est la métrique officielle

**Un 12% V5-full obtenu honnêtement avec une ablation propre vaut plus qu'un 20% obtenu dans un preset fourre-tout** — surtout pour un journal DSR qui vérifiera la démarche méthodologique.

---

## Références clés (pour les agents)

### Fichiers core (ne pas modifier sauf T2 observabilité)

- `core/orchestrator.py` — runtime tick-based, `OrchestratorResult` (stop_reason déjà présent ligne 42)
- `core/pressure.py` — formule ACO τ^α·η^β, accepte `heuristic_fn`
- `core/marker.py` — `Marker` dataclass et `StateMachine`
- `core/agent.py` — `StigmergicAgent`, `AgentAffinityProfile`, `local_sensing`
- `core/emergence.py` — 8 métriques d'émergence + feedback loop
- `core/guardrails.py` — `GuardrailEngine`, budget/retry/TTL/traceability

### Fichiers adaptateur (zone de modification principale)

- `adapters/base.py` — contrat `DomainAdapter`
- `adapters/travelplanner/adapter.py` — **cible principale T0 + T7** (initial_markers multi-city + heuristique ACO)
- `adapters/travelplanner/tools.py` — **cible T0 + T9** (search multi-city + prompts, prompt planning à **ligne 437**)
- `adapters/travelplanner/scientific_baselines.py` — **cible T3 + T4** (baselines à fixer, `_call_schema` ligne 335)
- `adapters/travelplanner/evaluator.py` — ne pas toucher

### LLM client (vérification seulement)

- `llm/client.py` — retry + backoff déjà implémentés (lignes 213-280). Vérifier `_is_retryable` pour 429/502/503.
- `llm/prompts.py` — contient les prompts **core** (think, decompose). **PAS** les prompts TravelPlanner.

### Config

- `config/default.yaml` — référence, ne pas modifier (backward compat)
- `config/travelplanner.yaml` — preset domain, point de départ pour T1
- **À créer** : `config/travelplanner_v4_only.yaml` (T1), `config/ablation/*.yaml` (T6)

### Tests

- `tests/unit/*` — 200+ tests unitaires à préserver
- `tests/integration/test_travelplanner.py` — intégration TravelPlanner
- **À créer** : `tests/unit/test_travelplanner_multi_city.py`, `tests/unit/test_travelplanner_marker_shaping.py`
- Commande : `uv run pytest tests/ -q`

### Documentation pré-existante

- `documentation/v3_oc1_oc5_alignment_audit.md` — audit OC1-OC5 (2026-03-06)
- `documentation/decisions/20260322-sprint6-v4-stigmergic-corrections.md` — ADR-013 (origine des 5 corrections V4)
- `documentation/redisgn_v2/sprint_06_artifact.md` — état V3+V4 opt-in
- `consigne/revue_litterature_v2_DSR.pdf` — revue DSR (fondements théoriques)

### Benchmark de référence

- Notebook : `output/jupyter-notebook/travelplanner-organization-philosophy-scientific-comparison-openrouter-qwen35-9b.ipynb`
- Pack scientifique : `output/travelplanner_framework_compare/20260409_233919/scientific_pack/`
- Dataset : `osunlp/TravelPlanner` sur HuggingFace, split `validation` (180 queries) pour éval, split `train` pour tuning

---

**Fin du plan v5.1.** Ce document est exécutable en l'état par un agent IA disposant d'un accès au repo et des credentials OpenRouter. Toutes les corrections issues de la revue expert du 2026-04-12 ont été intégrées.
