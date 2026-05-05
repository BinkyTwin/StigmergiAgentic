# Décisions — switch modèles & design de la campagne scientifique finale

**Date** : 2026-04-22
**Contexte** : campagne finale de comparaison pour le mémoire EMLV
**Rédigé par** : lotfi + agent
**Statut** : acté

Ce document fige les choix méthodologiques de la campagne scientifique finale. Il
est destiné à être cité dans les sections "Methodology", "Experimental setup" et
"Threats to validity" du mémoire.

---

## 1. Modèle principal : Gemma 2 27B

**Choix** : Gemma (`google/gemma-4-31b-it` sur OpenRouter) devient le modèle
principal pour toutes les comparaisons inter-frameworks.

**Motivation** :

- Pilote à 9 queries (stigmergiagentic, phase adapt) :
  - Qwen 3.5 9B → `5/9 final_pass (55,6 %)`
  - Gemma → `7/9 final_pass (77,8 %)`
- Écart absolu +22 pts sur les queries 3-jours (les "faciles"). L'écart
  s'amplifie sur les queries plus longues (cf. campagne complète
  `output/travelplanner_framework_compare/20260409_233919` où Qwen plafonnait
  entre 1,1 % et 8,3 % selon le framework).
- Qwen 3.5 9B présente un comportement capricieux transverse déjà observé par
  l'utilisateur sur d'autres projets.

**Représentativité** : Gemma 27B = modèle moyen stable, représentatif de l'état
de l'art open-source accessible en inférence hébergée.

## 2. Modèle fort : DeepSeek V3 (stigmergie uniquement)

**Choix** : DeepSeek V3 (`deepseek-chat` via `https://api.deepseek.com/v1`) est
utilisé **uniquement sur la configuration stigmergique C3**. Il n'est pas
exécuté sur les baselines.

**Motivation** :

- Mesurer le plafond de performance atteignable sous orchestration
  stigmergique.
- Isoler l'effet "capacité du modèle" de l'effet "orchestration".
- Caching serveur DeepSeek automatique sur préfixe système stable → coût
  réduit ( hit rate attendu > 50 % compte tenu de la longueur des prompts
  système stables).
- L'infrastructure client a été étendue pour capturer
  `prompt_cache_hit_tokens` / `prompt_cache_miss_tokens` et appliquer la
  tarification correcte (voir `llm/client.py::STATIC_PRICING`).

**Justification du périmètre restreint** : comparer DeepSeek sur les baselines
n'apporte pas d'information supplémentaire — les baselines Gemma couvrent déjà
la variance topologique. L'axe recherché est "orchestration × capacité".

## 3. Modèle stress-test : Qwen 3.5 9B (résultat existant réutilisé)

**Choix** : le résultat Qwen 3.5 9B × stigmergie C3 déjà disponible dans
`output/travelplanner_framework_compare/v6c_retry_20260420_seed42/v6_C/seed42/`
est réutilisé tel quel comme point "stress-test modèle faible".

**Chiffres clés** :

- `final_pass_rate = 23,88 %` (43/180)
- `success_rate = 97,8 %` (176 queries complétées)
- `tokens_total = 7 395 250`, `cost_total = $0,77`
- `avg_coordination_overhead = 21,4`

**Motivation** : Qwen 9B = stress-test montrant que la stigmergie compense
partiellement un modèle faible. Pas de re-run Qwen puisque le résultat existe.

**Hypothèse testable associée** : `gain_stigmergie(Qwen) > gain_stigmergie(Gemma) >
gain_stigmergie(DeepSeek)` — rendement décroissant de l'orchestration avec la
capacité du modèle.

## 4. Périmètre stigmergie : C3 uniquement

**Choix** : dans les comparaisons finales, la stigmergie est représentée par
**une seule configuration, C3** (skills + protocols read-only + cross_run
activé). C2, baseline V6, adapt_scientific sortent du périmètre de publication.

**Motivation** : C3 est la configuration finale et la plus complète. Les
configurations intermédiaires (C2, V6 base) ont été utiles pour l'ablation
pendant le développement mais ne participent pas à la comparaison
inter-frameworks finale.

## 5. Baselines de comparaison

**Matrice retenue** (toutes en Gemma) :

| Famille | Framework |
|---|---|
| Single-agent | `solo_direct` |
| Single-agent + CoT | `solo_cot` |
| Single-agent + itératif | `solo_self_refine` |
| Hiérarchie centralisée 2-niveaux | `planner_executor` (corrigé 2026-04-22) |
| Hiérarchie centralisée N-niveaux | `langgraph_supervisor` |
| Hiérarchie statique séquentielle (SOPs) | `metagpt_sequential` (nouveau) |
| Décentralisé / swarm | `stigmergiagentic` C3 |

### 5.1 Ajout MetaGPT

**Choix** : ajout d'un baseline `metagpt_sequential` couvrant la famille
"pipeline séquentiel fixe avec rôles SOPs".

**Pipeline** :

1. `ProductManager` → extrait les contraintes hard/commonsense explicites.
2. `Architect` → produit la structure macro (séquence de villes, skeleton
   par jour).
3. `Engineer` → itinéraire détaillé (4 appels LLM / query max si pas de
   review).
4. `Reviewer` → valide contre les contraintes officielles et répare si besoin
   (5e appel optionnel).

Implémentation dans `adapters/travelplanner/scientific_baselines.py::_run_metagpt_sequential`.

**Motivation** : AgentVerse, MetaGPT et ChatDev sont les références académiques
de la "hiérarchie centralisée à rôles". Sans ce baseline, la taxo topologique
n'est pas complète.

### 5.2 Fix planner_executor (2026-04-22)

Les trois biais de design découverts lors de l'analyse du `20260409_233919` ont
été corrigés :

- Search payload plein (plus de rétrécissement 10→6, 8→4).
- Prompt planner explicite sur contraintes hard (budget, cuisine, room, house
  rule) et commonsense.
- Instruction "EXACTLY N days with all fields populated".
- Instruction executor rééquilibrée : "blueprint is a strong starting point,
  but fix any violation".

Avant le fix : 1,1 % final_pass. Après le fix : à mesurer sur la campagne
finale.

## 6. Fix 7-day collapse (bloquant)

**Problème** : sur la campagne `20260409_233919`, 35/35 queries 7-jours
retournent `plan=[]` sur **tous** les baselines (y compris `solo_direct`). Le
parser `PlanDayTool._parse_itinerary` retombait silencieusement sur `[]` sans
log ni retry, et `max_response_tokens` n'était pas ajusté à la longueur de la
réponse attendue.

**Correctifs appliqués** (2026-04-22) :

- `PlanDayTool._dynamic_max_response_tokens = 8000` — plafond uniforme.
  `max_tokens` est un plafond d'arrêt de la complétion, pas une cible : le
  modèle s'arrête de lui-même quand le JSON est complet. 8000 reste sous le
  hard-cap DeepSeek de 8192 (découvert lors du smoke 2026-04-22 : `400
  Invalid max_tokens value, the valid range is [1, 8192]`), tout en gardant
  de la marge sur un itinéraire 7-jours (~2500 tokens) plus un préambule de
  raisonnement. Le vrai filet anti-troncature est le retry de recovery
  ci-dessous.
- `PlanDayTool.execute` : retry automatique sur parse échoué avec prompt de
  recovery ("Return ONLY strict JSON, no preamble").
- `PlanDayTool` et `scientific_baselines._call_itinerary` : logging
  `parse_failure_reason` dans le step_trace (`none`, `schema_parse_failed`,
  `empty_llm_content`, `recovered_on_retry`, `llm_call_exception`).
- `LLMClient.call` et `.acall` : acceptent un `max_response_tokens` par appel
  (override de l'instance).

**Validation** : à confirmer par smoke test 5 queries 7-jours Gemma.

## 7. Limitations assumées

### 7.1 Une seule seed par modèle

**Choix** : 1 seed (42) par cellule de la matrice.

**Motivation** : budget temps + API insuffisant pour 3 seeds × N frameworks × 2
modèles. À citer en "Threats to validity" du mémoire.

**Impact** : pas d'intervalle de confiance inter-seed ni de test de
significativité inter-seed. Les comparaisons restent appariées par query_idx
(McNemar possible à modèle constant).

### 7.2 Pas de DeepSeek sur les baselines

**Impact** : on ne pourra pas distinguer l'effet modèle isolé sur les
baselines. Mitigé par le fait que la question de recherche porte sur
l'orchestration, pas sur les baselines individuellement.

## 8. Infrastructure Docker — campagne finale

Parallélisation par 3 clés distinctes (2 OpenRouter + 1 DeepSeek) :

```bash
# Terminal 1 — baselines Gemma (clé OPENROUTER_API_KEY_2 via .env.key2)
OPENROUTER_API_KEY_2=$(grep OPENROUTER_API_KEY .env.key2 | cut -d= -f2) \
  docker compose -f docker-compose.campaign.yml up gemma-baselines

# Terminal 2 — stigmergie C3 DeepSeek (clé DEEPSEEK_API_KEY via .env)
docker compose -f docker-compose.campaign.yml up deepseek-stigmergie

# Terminal 3 (peut tourner en parallèle ou séquentiel) — stigmergie C3 Gemma
#   (clé OPENROUTER_API_KEY via .env)
docker compose -f docker-compose.campaign.yml up gemma-stigmergie
```

Chaque service écrit dans son propre `campaign_results/{label}/` et
`pheromones/` isolés. Pas de collision entre les trois containers.

## 9. Agrégation et analyse

Script de référence : `scripts/aggregate_campaign_comparison.py` — produit :

- `output/final_campaign/per_query_summary.csv` (1 ligne par
  `(model, framework, query_idx)`).
- `output/final_campaign/matrix_A.csv` — effet orchestration (Gemma constant).
- `output/final_campaign/matrix_B.csv` — effet modèle (stigmergie C3
  constante).
- McNemar appariés Gemma-stigmergie vs chaque baseline Gemma.

Le point Qwen pré-calculé (23,88 %) est importé depuis
`v6c_retry_20260420_seed42/v6_C/seed42/benchmark_summary.json` dans la matrice
B.

---

## 10. Références à citer dans le mémoire

- **Qwen 3.5 9B underperformance** : le pilote à 9 queries est documenté dans
  les notes de session 2026-04-22 (mémoire auto agent).
- **Planner-executor fix** : commit `2026-04-22` sur
  `adapters/travelplanner/scientific_baselines.py`.
- **MetaGPT / ChatDev / AgentVerse** : Hong et al. 2023, Qian et al. 2023,
  Chen et al. 2023 — hierarchie centralisée à rôles SOPs.
- **DyLAN / GPTSwarm** : Zhang et al. 2024 — graphes d'agents optimisables.
- **Mixture-of-Agents** : Wang et al. 2024 — couches parallèles.
- **TravelPlanner** : Xie et al. 2024 — benchmark et métriques officielles
  (`final_pass_rate`, `commonsense_micro/macro`, `hard_constraint_micro/macro`).
