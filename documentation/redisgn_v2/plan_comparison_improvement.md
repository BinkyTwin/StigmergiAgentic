# Plan d'amélioration des comparaisons inter-frameworks

Document de travail pour la campagne scientifique comparant le framework stigmergique à des baselines (solo, self-refine, planner-executor, langgraph supervisor).

## 1. État des lieux — ce qui ne va pas aujourd'hui

### 1.1 Bugs techniques confirmés

- **Collapse 7-jours silencieux** : 35/35 queries 7-jours retournent `plan=[]` sur **tous** les baselines (y compris `solo_direct`). Pas d'`error_type`, pas de log d'échec — juste un plan vide évalué à 0. Origine probable : troncation LLM sur Qwen 9B + `_parse_itinerary` qui retombe silencieusement sur `[]`.
- **Planner-executor handicapé par design** (corrigé le 2026-04-22) :
  - Search payload re-rétrécie (10→6 rests, 10→6 attractions, 8→4 hôtels).
  - Prompt planner sans contraintes hard explicites.
  - Instruction executor "blueprint is authoritative, minimal repair only" → empêche la correction.
  - Pas d'instruction "EXACTLY N jours" → 33/60 queries 3-jours avaient un jour vide.

### 1.2 Biais méthodologiques

- **Une seule seed** (42) sur la campagne `20260409_233919` → pas de variance.
- **Pas de run répétés sur le même modèle** → impossible de séparer variance LLM vs variance framework.
- **Coûts comparés sur échantillon non apparié** (stigmergique 12725s vs solo_direct 4196s, mais pas forcément sur les mêmes queries réussies).

## 2. Axes de comparaison à adopter

Inspiré de AgentVerse, MetaGPT, DyLAN, Mixture-of-Agents. Quatre dimensions :

### 2.1 Performance tâche (primaire)

- `final_pass_rate` (métrique officielle TravelPlanner).
- `commonsense_micro` / `hard_constraint_micro`.
- `delivery_rate` (plan non vide).
- Ventilation par **difficulté** (easy/medium/hard) × **durée** (3/5/7 jours).

### 2.2 Coût

- Tokens totaux (prompt + completion séparés si possible).
- USD (via pricing OpenRouter).
- **Tokens par query RÉUSSIE** (pas par query brute — plus fair).

### 2.3 Overhead de coordination

- Nombre d'appels LLM par query (`coordination_overhead`).
- Latence wall-clock par query.
- Overhead net = (latence framework − latence solo_direct).

### 2.4 Robustesse

- Variance inter-seed (min 3 seeds : 42, 43, 44).
- Taux de crash / parsing silencieux.
- Dégradation en fonction de la complexité (pente du final_pass_rate sur 3→5→7 jours).

## 3. Baselines à inclure (taxonomie topologique)

| Famille | Framework | Couvert aujourd'hui ? |
| --- | --- | --- |
| Single-agent | `solo_direct` | oui |
| Single-agent + CoT | `solo_cot` | oui |
| Single-agent + iteratif | `solo_self_refine` | oui |
| Hiérarchie centralisée, 2 niveaux | `planner_executor` | oui (fixé) |
| Hiérarchie centralisée, N niveaux | `langgraph_supervisor` | oui |
| Décentralisé / swarm | `stigmergiagentic` (ton framework) | oui |
| Pipeline séquentiel fixe (ChatDev/MetaGPT-like) | — | **à ajouter ?** |
| Debate / consensus | — | optionnel |

Ajouter un **pipeline séquentiel** (rôle CEO→Planner→Executor→Validator, sans supervisor dynamique) donnerait un point de comparaison "hiérarchie statique" vs "hiérarchie dynamique" (supervisor) vs "stigmergique".

## 4. Corrections à appliquer avant la prochaine campagne

### 4.1 Bug 7-jours (bloquant)

- Instrumenter `PlanDayTool._parse_itinerary` pour logger `parse_failure_reason` quand il retombe sur `[]`.
- Augmenter `max_tokens` côté LLMClient pour les queries longues (détection sur `query_data['days']`).
- Ajouter un retry avec prompt "return only JSON, no preamble" si le premier parse échoue.
- Mesurer le taux d'échec par modèle avant de relancer la campagne complète.

### 4.2 Évaluation appariée

- Exporter un `per_query_summary.csv` avec une ligne par (framework, seed, query_idx) — colonnes : final_pass, tokens, cost, runtime, delivered.
- Calculer les agrégats **en appariant** par query_idx : McNemar test, Wilcoxon sur les paires.

### 4.3 Protocole multi-seed

- 3 seeds minimum (42, 43, 44). Idéalement 5.
- Rapporter moyenne ± écart-type sur chaque métrique.
- Bootstrap intervals de confiance sur `final_pass_rate`.

### 4.4 Matching du contexte LLM

- Vérifier que tous les baselines reçoivent **le même search_payload** (même limites, mêmes champs).
- Vérifier que les prompts système sont de longueur comparable (pas de désavantage injecté).

## 5. Modèle(s) LLM pour la comparaison

### 5.1 Problèmes observés avec Qwen 3.5 9B

- Collapse 7-jours systématique.
- Évoqué par l'utilisateur : comportement capricieux sur un autre projet.
- Coût faible mais qualité bridée sur raisonnement long.

### 5.2 Alternatives à considérer

| Modèle | Pour | Contre |
| --- | --- | --- |
| **Qwen 2.5 72B Instruct** | meilleur reasoning, contexte long, OpenRouter $0.4/M | ~8× plus cher |
| **Llama 3.3 70B** | baseline académique reconnue | plus cher, parfois verbeux |
| **Gemma 2 27B** | déjà dans ta campagne, stable | qualité < 70B |
| **DeepSeek V3** | très bon reasoning, $0.3/M | moins connu en éval académique |
| **GPT-4o-mini** | référence connue, stable JSON | coût, dépendance OpenAI |
| **Claude Haiku 4.5** | excellent suivi d'instruction, JSON propre | coût plus élevé |

### 5.3 Recommandation

**Faire un pilote modèle-comparison sur 30 queries (10× 3-jours, 10× 5-jours, 10× 7-jours)** avec 3-4 candidats : Qwen 2.5 72B, Llama 3.3 70B, Gemma 2 27B, DeepSeek V3. Mesurer :

- delivery_rate (plan non vide) — éliminatoire.
- final_pass_rate.
- JSON parse failure rate.
- Coût par query réussie.

Garder **2 modèles** pour la campagne finale :

- Un modèle "léger et stable" pour la reproductibilité (Gemma 2 27B ou Qwen 2.5 14B).
- Un modèle "fort" pour le plafond de performance (Qwen 2.5 72B ou Llama 3.3 70B).

Garder Qwen 3.5 9B uniquement comme **stress-test** (montrer que la stigmergie aide DAVANTAGE sur un modèle faible — point scientifique intéressant pour le mémoire).

## 6. Planning indicatif

1. **Laisser la campagne actuelle Qwen/Gemma terminer** (test d'intégration, pas de valeur scientifique publiable).
2. **Analyser les résultats** : quantifier le collapse 7-jours sur les 4 variantes stigmergiques (adapt/c2/c3/baseline).
3. **Corriger le parser** (section 4.1) + valider sur 5 queries 7-jours.
4. **Pilote modèles** (section 5.3) sur 30 queries.
5. **Choisir 2 modèles finaux**.
6. **Relancer la campagne complète** : 6 frameworks × 2 modèles × 3 seeds × 180 queries = ~6500 runs. Budget à estimer.
7. **Analyse appariée + tests statistiques** (section 4.2).
8. **Rédaction section résultats du mémoire**.

## 7. Points de vigilance méthodologique

- **Ne PAS comparer stigmergique (plus cher) à solo_direct (moins cher) sur final_pass_rate seul** → toujours reporter le Pareto (perf × coût).
- **Toujours reporter les échecs silencieux** (delivery_rate < 100%) — c'est souvent là que les frameworks se distinguent.
- **Variance inter-seed** doit être reportée dès le premier tableau de résultats.
- **Pré-enregistrer** le protocole avant de relancer (éviter le cherry-picking).
