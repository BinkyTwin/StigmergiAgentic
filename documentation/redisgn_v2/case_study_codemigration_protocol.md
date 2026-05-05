# Étude de cas OC4 — Protocole scientifique d'évaluation sur la migration de code

**Date :** 2026-04-23
**Portée :** étude de cas post-campagne TravelPlanner, validation de l'**Objectif de Conception 4 (OC4 — Spécialisation à la transformation de code)** au sens du mémoire DSR (cf. `consigne/revue_litterature_v2_DSR.tex`, l. 213-218).
**Statut pré-requis :** campagne finale V10 TravelPlanner (Matrices A/B) lancée, artefact gelé, doc à jour.

---

## 1. Contexte et motivation

La revue de littérature positionne l'artefact sur **deux terrains empiriques complémentaires** :

- **TravelPlanner** (Xie et al., 2024) — planification sous contraintes, benchmark « neutre » pour OC3.
- **Migration / transformation de code** — terrain industriel critique (Ziftci et al., 2025 au FSE 2025 ; IBM Watsonx ; Amazon Q Developer ; PolyMigration) et objectif OC4 du mémoire.

Le gap identifié dans la revue (l. 1741-1778) est explicite : *aucune étude ne propose un framework d'orchestration multi-agents LLM stigmergique validé sur la migration de code avec des métriques intégrant performance, coût, gouvernabilité et conformité*. Le plan V3 prévoyait un Sprint 8 « CodeMigration adapter » (`consigne/V3_improvement_plan.md`, l. 758-797) **qui n'a jamais été réalisé**. Ce protocole le relance en format **étude de cas scientifique**, calibré pour :

1. Être **crédible** pour le jury et pour une soumission en article (ECIS / HICSS / ICSE-NIER).
2. Tenir dans le **budget temps restant avant soutenance** (~2 semaines post-campagne TP).
3. **Réutiliser l'artefact gelé** (`core/*` + `scientific_baselines.py`) sans redesign.
4. **Éviter la contamination** : le même core Sprint 9 tourne sur un nouveau domaine, preuve de généralité (OC1).

---

## 2. Positionnement scientifique (ancrage revue)

### 2.1 Travaux de référence (à citer explicitement dans le mémoire)

| Référence | Rôle dans le design | Section revue |
|---|---|---|
| Ziftci et al. (FSE 2025) | Validation industrielle Google — 39 migrations, 74,45 % patches sans retouche humaine, triptyque *static analysis + LLM + tests* | l. 984-1015 |
| Cursor (2025) | Leçons coordination décentralisée : goulots locks, aversion au risque, passage à planificateurs-travailleurs | l. 1017-1040 |
| Rozière et al. (NeurIPS 2020) — TransCoder | Traduction cross-language non supervisée, BLEU 68,7 C++→Java | l. 1045-1056 |
| CodeRosetta (NeurIPS 2024) | Extension traduction parallèle | l. 1052 |
| Sneed (2010) + IBM (2023) + Diggs et al. (LLM4Code@ICSE 2025) | Modernisation COBOL, documentation legacy | l. 1058-1070 |
| Lamothe, Guéhéneuc & Shang (ACM CSUR 2021) | Revue 110 études refactoring / évolution API | l. 1074-1085 |
| Jimenez et al. (2024) — SWE-bench | Référence évaluation agents GL | l. 1675-1681 |
| Ghosh Paul et al. (2024) | Taxonomie métriques 4 catégories (textuelle, correction, qualité, sémantique) | l. 1662-1674 |
| Kapoor et al. (2024) | Frontière Pareto coût-précision comme méthodologie | l. 1700-1710 |
| Xia et al. (Agentless, 2024) | Baseline *sans* agent (pipeline scripté) à battre | § contre-arguments |
| Zhu et al. (MultiAgentBench 2025) | Topologies (étoile / chaîne / graphe) et leur impact | l. 1628-1646 |

### 2.2 Papiers récents à rechercher / intégrer avant rédaction

À compléter en phase préparatoire (veille 2026-Q1/Q2) :

- **SWE-bench Verified** (OpenAI 2024) + **SWE-bench Multimodal** / **SWE-Gym** (2025).
- **Agentless 1.5 / Magis / Moatless** — pipelines sans orchestration apparente, très compétitifs en 2025.
- **Ziftci FSE 2025** — lire en détail pour reprendre leurs *métriques exactes* (*applied-without-modification rate*, *developer-time saved*, *rollback rate*).
- **Amazon Q Developer Agent** (transformation Java 8 → 17/21, papier SEIP 2025 si paru).
- **CodeRosetta** (NeurIPS 2024) : métriques CodeBLEU / CrystalBLEU.
- **RACE benchmark** (*Readability / Efficiency / Maintainability*) — Zheng et al. 2024.
- **MAST** (Cemri et al. 2025) et **Gao et al. 2025** sur limites orchestrations hiérarchiques — déjà cités revue, à recroiser côté code.

Livrable préparatoire : une **section « Related work — code transformation »** de ~2 pages autonome, réutilisable pour l'article.

---

## 3. Questions de recherche et hypothèses

### 3.1 RQ principale

**RQ-OC4 :** Un framework d'orchestration multi-agents LLM à coordination stigmergique fournit-il un avantage mesurable sur la migration de code par rapport aux baselines centralisées (*single-agent*, pipeline séquentiel MetaGPT-like, *planner-executor*, LangGraph supervisor) et aux pipelines *agentless* (Xia et al., 2024) à modèle et budget équivalents ?

### 3.2 Sous-questions et hypothèses testables

| ID | Énoncé | Métrique de test |
|---|---|---|
| H1 — efficacité | `pass@1(stigmergie C3, Gemma) > max(pass@1(baselines, Gemma))` sur le corpus de migration | Pass@1 par fichier migré, McNemar apparié |
| H2 — capacité modèle | `pass@1(stigmergie C3, DeepSeek) > pass@1(stigmergie C3, Gemma) > pass@1(stigmergie C3, Qwen)` | Même métrique, par cellule |
| H3 — Pareto coût/qualité | La stigmergie C3 Gemma domine les baselines Gemma sur le front `(pass@1, tokens_par_fichier_réussi)` (Kapoor et al., 2024) | Front Pareto 2D |
| H4 — spécialisation émergente (OC2) | En présence de patterns récurrents, les agents qui ont *déjà* migré un fichier d'un type donné traitent les fichiers suivants du même type avec moins de ticks et un meilleur pass rate (preuve de la mémoire cognitive cross-fichier) | `ticks_per_file`, `pass@1` stratifié par ordre de visite |
| H5 — gouvernance (OC5) | *Audit completeness* ≥ 99,5 %, 100 % des transitions avec *before/after*, 0 dépassement budget, tous cas ambigus escaladés | Audit JSONL vs `markers.db` diff, compteurs |
| H6 — robustesse aux *flaky tests* | La stigmergie résiste mieux aux tests instables qu'un pipeline scripté (retry + reinforcement) | Taux de faux négatifs sur tests marqués flaky |

H4 et H5 sont **les deux contributions distinctives** vs Ziftci et al. (2025), qui n'examinent pas l'émergence ni la gouvernance au niveau de la coordination.

---

## 4. Design expérimental

### 4.1 Choix du corpus (décision structurante)

| Option | Corpus | Avantages | Risques | Charge |
|---|---|---|---|---|
| **A — Python 2 → 3 micro-corpus** | 30-50 fichiers extraits de 3-4 repos OSS réels (ex. `docopt`, `whoosh`, `pyjwt` anciennes versions) avec test suite existante | Reproductible, 100 % automatisable, tests préexistants, charge légère | Tâche « simple », jury peut objecter que `2to3` existe déjà | Faible (3-5 jours) |
| **B — SWE-bench Lite (subset)** | 50-100 instances de SWE-bench Lite (Jimenez et al., 2024) | Référence académique majeure, comparabilité directe avec Agentless / SWE-agent / Devin-like | Coût tokens élevé, instances complexes, pas strictement « migration » mais « bug-fix/feature » | Moyen (7-10 jours) |
| **C — PolyMigration / COBOL** | Corpus industriel | Plus proche de l'OC4 stricto sensu | **Non accessible publiquement** (Amazon), COBOL → toolchain lourde | Hors portée |

**Décision recommandée :** **combinaison A + B**.

- A sert d'étude de cas « migration pure » (OC4 au sens strict du plan V3) ; la critique « `2to3` existe » est absorbée par le fait qu'on évalue des *pipelines agentiques* et non un outil déterministe.
- B sert d'ancrage sur un benchmark reconnu (réponse à l'exigence revue l. 1675-1681).
- Fallback : si le temps manque, conserver uniquement **A** en assumant la limitation.

### 4.2 Matrices expérimentales

Reprise de la structure TravelPlanner (cohérence méthodologique mémoire).

**Matrice C — effet orchestration (modèle constant = Gemma)**

| Framework | Corpus A (Py2→3) | Corpus B (SWE-bench Lite) |
|---|---|---|
| `solo_direct` | ✓ | ✓ |
| `solo_cot` | ✓ | ✓ |
| `planner_executor` | ✓ | ✓ |
| `metagpt_sequential` | ✓ | ✓ |
| `langgraph_supervisor` | ✓ | ✓ |
| `agentless_pipeline` (baseline anti-MAS, Xia et al. 2024) | ✓ | ✓ |
| **`stigmergiagentic C3`** | ✓ | ✓ |

**Matrice D — effet modèle (stigmergie C3 constante)**

| Modèle | Corpus A | Corpus B |
|---|---|---|
| Qwen 3.5 9B | ✓ | (optionnel) |
| Gemma (principal) | ✓ | ✓ |
| DeepSeek V3 | ✓ | ✓ |

1 seed par cellule (limitation assumée, *Threats to validity* — cohérent avec TP).

### 4.3 Métriques (ancrage Ghosh Paul et al. 2024)

Taxonomie à 4 catégories + extensions gouvernance.

| Catégorie | Métrique | Unité | Outil |
|---|---|---|---|
| **Correction fonctionnelle** (primaire) | `pass@1` test suite | % | `pytest` / `unittest` |
| Correction fonctionnelle | `patch_applied_rate` | % | `git apply --check` |
| Correction fonctionnelle | `resolved_instances` (SWE-bench) | count | harnais officiel `swebench.harness` |
| **Similarité** | CodeBLEU (Ren et al., 2020) | [0,1] | `codebleu` PyPI |
| Similarité | CrystalBLEU | [0,1] | `crystalbleu` |
| **Sémantique** | AST-edit distance | int | `ast` + `zss` |
| Sémantique | Test-behavior preservation | % | régression sur tests héritage |
| **Qualité** (RACE) | Readability / Maintainability | score auto | `radon`, `pylint`, RACE scripts |
| **Coût** (Pareto, Kapoor et al. 2024) | `tokens_per_file` | int | `LLMClient` usage |
| Coût | `USD_per_file` | $ | Pricing dict (DeepSeek cache-aware) |
| Coût | `time_per_file_seconds` | s | horloge wall-clock |
| Coût | `rollback_rate` (Ziftci) | % | compteur d'abandons |
| **Gouvernance (OC5)** | `audit_completeness` | % | diff `audit_log.jsonl` ↔ `markers.db` |
| Gouvernance | `decision_traceability` | % | % transitions avec `before/after` |
| Gouvernance | `human_escalations` | count | état `escalated` |
| Gouvernance | `budget_compliance` | bool | `BudgetExceededError` count |
| **Émergence (OC2)** | `specialization_index` | float | entropie distribution agent × pattern |
| Émergence | `cross_file_transfer_ratio` | float | `ticks_per_file[i] / ticks_per_file[0]` par pattern |

### 4.4 Tests statistiques

- **McNemar apparié** sur `pass@1` : stigmergie vs chaque baseline, par corpus et par modèle (cohérent avec `aggregate_campaign_comparison.py` TP).
- **Test de Wilcoxon** sur `tokens_per_file` (distribution non normale).
- **Bootstrap 95 % CI** pour tous les taux agrégés (Desai et al., 2025, sur reproductibilité).
- **Front de Pareto** `(pass@1, USD_per_file_réussi)` — visualisation Matplotlib + test de dominance.

---

## 5. Implémentation — fichiers à créer

### 5.1 Adaptateur `adapters/codemigration/` (nouveau, ~600-800 LoC)

Calqué sur `adapters/travelplanner/` (pattern validé Sprint 9).

| Fichier | Rôle | Réutilise |
|---|---|---|
| `adapters/codemigration/__init__.py` | Exports | — |
| `adapters/codemigration/adapter.py` | `CodeMigrationAdapter(BaseAdapter)` : `seed_markers`, `step_hooks`, `extract_artifact`, `compile_protocol` optionnel | `adapters/base.py`, `adapters/travelplanner/adapter.py` comme squelette |
| `adapters/codemigration/workspace.py` | `GitWorkspace` : clone, branch, list_files, read, write, commit, rollback, apply_patch, run_tests | `adapters/travelplanner/workspace.py` pour l'API |
| `adapters/codemigration/tools.py` | 4 outils LLM-driven : `DiscoverTool`, `TransformTool`, `TestTool`, `ValidateTool` | `adapters/travelplanner/tools.py` (`PlanDayTool` pour pattern *call + parse retry*) |
| `adapters/codemigration/evaluator.py` | `CodeMigrationEvaluator` : pass@1, rollback_rate, tokens, cost, AST-edit, CodeBLEU | `adapters/travelplanner/evaluator.py` |
| `adapters/codemigration/scientific_baselines.py` | 6 runners baselines alignés TP (`solo_direct`, `solo_cot`, `planner_executor`, `metagpt_sequential`, `langgraph_supervisor`, **`agentless_pipeline`** nouveau) | `adapters/travelplanner/scientific_baselines.py` |
| `adapters/codemigration/agentless_baseline.py` | Pipeline scripté Xia et al. 2024 : *localize → repair → validate*, sans rôles ni coordination | code externe à réécrire |

**Contrat DAG initial (seed markers)** :

```
pour chaque fichier cible :
    discover_file_N (pending) → transform_file_N (gated) → test_file_N (gated) → validate_file_N (gated)
après tous les fichiers :
    integration_test (depends on all validate_file_*)
```

Chaque transition produit un marker ; la boucle `compute_pressures → select_action → execute → deposit` du cœur Sprint 9 reste inchangée.

### 5.2 Configs (nouvelles)

| Fichier | Corpus | Modèle |
|---|---|---|
| `config/codemigration_adapt_scientific.yaml` | A (train subset) | Gemma |
| `config/codemigration_adapt_scientific_deepseek.yaml` | A (train subset) | DeepSeek |
| `config/codemigration_eval_c3_gemma.yaml` | A + B | Gemma (stigmergie C3 read-only) |
| `config/codemigration_eval_c3_deepseek.yaml` | A + B | DeepSeek |
| `config/codemigration_eval_baseline_gemma.yaml` | A + B | Gemma (baselines) |

Reprendre la structure V6_C de `config/travelplanner_eval_c3_gemma.yaml` (`recovery_controller`, `dynamic_idle`, `targeted_repair`, `frequentation`) — l'artefact est gelé.

### 5.3 Corpus et fixtures

| Fichier | Rôle |
|---|---|
| `fixtures/codemigration/py2to3/` | 30-50 fichiers + test suite, extraits de repos OSS historiques (états pre-Py3 de `whoosh`, `docopt`, `chardet`…). Un `queries.jsonl` par fichier (`id`, `path`, `test_cmd`, `expected`). |
| `fixtures/codemigration/swebench_lite_subset.jsonl` | 50-100 instances SWE-bench Lite (ids stables), téléchargées via `datasets` HF. |
| `fixtures/codemigration/train_split.jsonl` (10-15 fichiers) | Corpus d'adaptation, **strictement disjoint** du test (cohérent protocole V10 TP). |
| `fixtures/codemigration/eval_split.jsonl` (30-50 + 50-100) | Corpus d'évaluation. |

Document `fixtures/codemigration/CORPUS.md` : provenance exacte, licences, commit SHA de référence, instructions de re-téléchargement.

### 5.4 Scripts de campagne et d'export

| Fichier | Rôle | Calqué sur |
|---|---|---|
| `scripts/run_codemigration_solo_query_export.py` | CLI single-baseline (`solo_direct` / `solo_cot`) | `run_travelplanner_solo_query_export.py` |
| `scripts/run_codemigration_planner_executor_query_export.py` | CLI `planner_executor` | équivalent TP |
| `scripts/run_codemigration_metagpt_query_export.py` | CLI MetaGPT | équivalent TP |
| `scripts/run_codemigration_langgraph_query_export.py` | CLI LangGraph | équivalent TP |
| `scripts/run_codemigration_agentless_query_export.py` | CLI Agentless (nouveau) | — |
| `scripts/run_gemma_codemigration_c3_docker.sh` | Campagne adapt + eval Gemma stigmergie | `run_gemma_stigmergie_c3_docker.sh` |
| `scripts/run_deepseek_codemigration_c3_docker.sh` | Campagne DeepSeek stigmergie | équivalent TP |
| `scripts/run_gemma_codemigration_baselines_docker.sh` | 6 baselines Gemma séquentiel | `run_gemma_baselines_docker.sh` |
| `scripts/aggregate_codemigration_comparison.py` | Agrégation inter-modèles, Matrices C/D, McNemar, Pareto | `aggregate_campaign_comparison.py` |

### 5.5 Docker

Étendre `docker-compose.campaign.yml` avec 3 services :

- `gemma-codemigration-stigmergie` (clé `OPENROUTER_API_KEY`)
- `deepseek-codemigration-stigmergie` (clé `DEEPSEEK_API_KEY`)
- `gemma-codemigration-baselines` (clé `OPENROUTER_API_KEY_2`)

Volumes distincts : `campaign_results/gemma-codemigration/`, `campaign_results/deepseek-codemigration/`, `campaign_results/gemma-codemigration-baselines/`.

Le harnais SWE-bench (`swebench.harness`) requiert Docker-in-Docker ou lancement hôte → **préférer un exécuteur hôte post-run** qui évalue les patches produits par les containers de campagne (évite l'imbrication).

### 5.6 Tests (cible ≥ 15 nouveaux tests)

| Fichier | Cible |
|---|---|
| `tests/unit/test_codemigration_tools.py` | ≥ 5 tests (parse retry, AST normalization) |
| `tests/unit/test_codemigration_evaluator.py` | ≥ 3 tests (pass@1, CodeBLEU, rollback) |
| `tests/unit/test_codemigration_baselines.py` | ≥ 5 tests (1 par baseline) |
| `tests/integration/test_codemigration_end_to_end.py` | ≥ 2 tests (1 fichier Py2→3 synthétique, 1 SWE-bench toy) |

Non-régression : la suite existante Sprint 9 doit rester 307/307 après ajout.

### 5.7 Documentation thèse / article

| Fichier | Rôle |
|---|---|
| `documentation/redisgn_v2/case_study_codemigration_protocol.md` | **Ce document** — protocole scientifique complet |
| `documentation/redisgn_v2/case_study_codemigration_results.md` | Résultats agrégés post-campagne (Matrices C/D, Pareto, stats) |
| `documentation/redisgn_v2/threats_to_validity.md` | Mise à jour : 1 seed, corpus taille réduite, flaky tests, contamination modèle-corpus |
| `documentation/construction_log.md` | Append entrée « Étude de cas OC4 » |
| `documentation/decisions/adr_codemigration_scope.md` | ADR : scope (A+B vs A seul), choix baselines, seed count |
| `AGENTS.md` / `CLAUDE.md` | Section « Campagne OC4 — migration de code » |

---

## 6. Protocole expérimental détaillé

### 6.1 Phases

1. **Adapt (Gemma + DeepSeek)** sur `train_split.jsonl` (10-15 fichiers) :
   - `skills.db` et `protocols.db` en écriture (`read_only: false`).
   - `cross_run.enabled: true, read_only: false`.
   - Produit `pheromones/*.db` gelés pour l'éval.
2. **Checkpoint SQLite** entre phases (`PRAGMA wal_checkpoint`) — reprise du fix V10 TP.
3. **Eval C3 (Gemma + DeepSeek)** sur `eval_split.jsonl` :
   - `skills.db` et `protocols.db` en `read_only: true`.
   - 1 seed par cellule.
4. **Eval baselines (Gemma)** : 6 frameworks séquentiels sur `eval_split.jsonl`.
5. **Eval Qwen stigmergie C3** (uniquement corpus A, budget léger) — cellule stress-test modèle faible.
6. **Post-run** : exécution locale du harnais SWE-bench sur les patches produits (corpus B).
7. **Agrégation** : `aggregate_codemigration_comparison.py`.

### 6.2 Budget estimé

| Cellule | Fichiers/instances | Tokens | Coût |
|---|---|---|---|
| Gemma stigmergie (adapt 15 + eval A 40 + eval B 80) | 135 | ~12-18 M | ~$3-6 |
| DeepSeek stigmergie (adapt 15 + eval A 40 + eval B 80, cache ~50 %) | 135 | ~12-18 M | ~$2-4 |
| Gemma × 6 baselines × (40 + 80) = 720 runs | 720 | ~25-35 M | ~$8-12 |
| Qwen stigmergie (eval A 40) | 40 | ~3 M | ~$0,30 |
| SWE-bench harness (local) | — | — | CPU / Docker hôte |
| **Total** | — | — | **~$15-25** |

Durée parallèle sur 3 containers : **15-22 h** (contrainte = baselines séquentielles).

### 6.3 Ordre d'exécution

1. **Semaine 1** : préparer corpus A + B, scaffold `adapters/codemigration/`, tests unitaires, smoke tests 3 fichiers.
2. **Semaine 1 (fin)** : Docker + configs + scripts d'export.
3. **Semaine 2 (jours 1-3)** : lancer la campagne (parallèle).
4. **Semaine 2 (jours 4-5)** : agrégation, plots, rédaction section mémoire, ADR.

---

## 7. *Threats to validity* (à documenter explicitement, cf. revue l. 1700-1710)

| Menace | Type | Mitigation |
|---|---|---|
| 1 seed par cellule | Conclusion validity | Assumée, documentée ; bootstrap CI pour atténuer |
| Corpus A petite taille (30-50 fichiers) | External validity | Complémenter par SWE-bench Lite (B) ; ne pas généraliser au-delà du corpus |
| Contamination modèle / corpus (repos OSS publics dans training set LLM) | Construct validity | Préférer des *versions anciennes* de repos moins représentées ; rapporter la date de freeze LLM |
| *Flaky tests* (Ziftci et al. 2025, p. 12) | Conclusion validity | Marquer fichiers à tests instables, analyse séparée |
| Tests pré-existants incomplets | Internal validity | Report du taux de couverture par fichier ; compléter par AST-edit et CodeBLEU |
| Différence de coût LLM (cache DeepSeek) | Construct validity | Rapporter `USD_per_file` séparément `cache_hit` vs `cache_miss` |
| Absence de COBOL / PolyMigration | External validity | Positionner le cas comme *preuve de concept OC4 sur Python*, transférabilité discutée en qualitatif |

---

## 8. Livrables scientifiques

- **Section mémoire** « Étude de cas — migration de code » (~10-15 pages) : contexte, méthode, résultats, discussion, limites.
- **Matrices C et D** (CSV + plots Pareto).
- **Tableau McNemar** (stigmergie vs chaque baseline).
- **Section « Principes de conception généralisables »** (Gregor & Hevner 2013, *Design Theory for Predictability* Grisold et al. 2025) — dérivés de la comparaison TravelPlanner + migration.
- **Article court** (6-8 pages, format ECIS-RIP / HICSS-short / ICSE-NIER) : « *Stigmergic orchestration of LLM agents for code migration: evidence from Python 2→3 and SWE-bench Lite* ».
- **Artefact rejouable** : `docker compose -f docker-compose.campaign.yml up gemma-codemigration-stigmergie` reproductible.

---

## 9. Fichiers critiques à modifier / créer (résumé)

**Nouveaux :**

- `adapters/codemigration/{__init__.py,adapter.py,workspace.py,tools.py,evaluator.py,scientific_baselines.py,agentless_baseline.py}`
- `config/codemigration_{adapt_scientific,adapt_scientific_deepseek,eval_c3_gemma,eval_c3_deepseek,eval_baseline_gemma}.yaml`
- `fixtures/codemigration/{CORPUS.md,py2to3/,swebench_lite_subset.jsonl,train_split.jsonl,eval_split.jsonl}`
- `scripts/run_codemigration_{solo,planner_executor,metagpt,langgraph,agentless}_query_export.py`
- `scripts/run_{gemma,deepseek}_codemigration_c3_docker.sh`
- `scripts/run_gemma_codemigration_baselines_docker.sh`
- `scripts/aggregate_codemigration_comparison.py`
- `tests/unit/test_codemigration_{tools,evaluator,baselines}.py`
- `tests/integration/test_codemigration_end_to_end.py`
- `documentation/redisgn_v2/case_study_codemigration_results.md`
- `documentation/decisions/adr_codemigration_scope.md`

**À modifier :**

- `docker-compose.campaign.yml` (3 services supplémentaires)
- `AGENTS.md`, `CLAUDE.md` (section OC4)

**À réutiliser tel quel (core gelé) :**

- `core/*` (`marker`, `marker_store`, `decay`, `dependency`, `reinforcement`, `emergence`, `guardrails`, `audit`, `environment`, `agent`, `orchestrator`, `pressure`, `tool_registry`, `config`, `schemas`)
- `llm/client.py` (DeepSeek, cache tokens, pricing — déjà intégré V10)
- `adapters/base.py`
- `scripts/aggregate_campaign_comparison.py` comme squelette

---

## 10. Vérification end-to-end

1. `uv run pytest tests/unit/test_codemigration_* tests/integration/test_codemigration_* -q` → nouveaux tests verts.
2. `uv run pytest tests/ -q --ignore=tests/integration/test_langgraph_supervisor.py` → suite existante non régressée (307+ passed).
3. Smoke 1 fichier Py2→3 stigmergie Gemma : patch appliqué, tests verts, `skills.db` non vide.
4. Smoke 1 instance SWE-bench Lite stigmergie Gemma : harnais SWE-bench répond *resolved*.
5. Smoke Agentless sur 1 fichier Py2→3 : pipeline scripté termine sans erreur.
6. Campagne Docker (utilisateur) : 3 services `Up`, progression monitorable par `ls campaign_results/*/eval/*.json | wc -l`.
7. Agrégation : `output/final_campaign_codemigration/` contient `per_file_summary.csv`, `matrix_C.csv`, `matrix_D.csv`, `pareto.png`, `aggregates.json`.
8. Sanity check : pour la cellule `(stigmergie, Gemma, corpus A)`, `pass@1 ∈ [0,1]`, `audit_completeness ≥ 0.99`, McNemar p-value calculée contre chaque baseline.

---

## 11. Décisions à prendre avant lancement

1. **Scope** : A seul (défensif, ~1 semaine) **ou** A+B (ambitieux, ~2 semaines) ?
2. **Corpus A — repos sources exacts** (à figer avant scaffold) : liste proposée `docopt`, `whoosh`, `chardet`, `pyjwt` (versions pré-Py3) — à valider.
3. **SWE-bench subset** : 50 ou 100 instances ? (50 ≈ $6 Gemma, 100 ≈ $12).
4. **Baselines** : garder les 6 de TP, ou retirer `langgraph_supervisor` (coûteuse, peu différenciante sur TP) ?
5. **Qwen stigmergie** : lancer sur corpus A uniquement (stress-test léger) ou le retirer ?
6. **Calendrier** : démarrer dès la fin de la campagne TP V10, ou après la soutenance pour l'article ?
