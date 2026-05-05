# Phase 5 — Comparaison A1/A2/A3 réelle sur main_30 (LLM-driven)

**Date** : 2026-05-04
**Subset** : `fixtures/migrationbench/subsets/main_30.jsonl` (30 instances)
**Seed** : 42
**LLM** : DeepSeek `deepseek-chat` via `https://api.deepseek.com/v1`
**Adapter** : `migrationbench` V10 + `MigrationBenchVerifier` (8 signaux canoniques + official_eval)
**Stratégies** :
- A1 = `agentless_basic` (1 candidat LLM, 0 repair)
- A2 = `branching_repair` (1 candidat LLM init, 1 round repair, 1 repair/cand)
- A3 = `branching_repair` (2 candidats LLM init, 1 round repair, 2 repair/cand)

Ce document remplace la première campagne `campaign_results/v10/ablation_main30/`
qui utilisait des providers placeholders (`make_migrationbench_deterministic_provider`
+ `make_migrationbench_noop_repair_provider`) et ne mesurait donc pas la
contribution scientifique de A2/A3.

## Architecture des providers LLM

Module : `scripts/bench/providers_llm.py`

- `make_migrationbench_llm_initial_provider` : appelle `deepseek-chat` jusqu'à
  `llm_initial_candidates` fois avec température croissante (0.0 → 0.4 → 0.8 →
  1.0) pour produire des candidats distincts. Dédup par signature SHA-256 sur
  la liste d'edits canonicalisée.
- `make_migrationbench_llm_repair_provider` : prompt construit à partir de
  `FeedbackDigest` (failure_type, signals, recommended_actions, anti_actions,
  log tail tronqué). Appelle le LLM avec température croissante.
- `_normalize_edits` : clamp `expected_replacements=1`, force
  `allow_multiple=True` pour éviter les rejets `replacement_count_too_low`
  causés par les estimations LLM trop optimistes.
- Fallback déterministe (`deterministic_pom17_edits`) seulement si l'API
  reste silencieuse ou ne produit aucun edit valide ; metadata
  `source=deterministic_fallback` flaggue le cas pour audit post-hoc.

Wired dans `scripts/bench/harness.py` via `extras.use_llm_providers=true`.
Tests : `tests/unit/v10/bench/test_providers_llm.py` (16 tests, OpenAI mocké).

## Résultats par bras

```
arm                       strict  parity  avg_cand  max_cand  repair  compile  test  official  dedup  rep_supp
A1_agentless_basic            1    True      1.00         1       0        3     3         1      0        0
A2_linear_repair              1    True      1.90         2      27        4     4         1      0        0
A3_branching_repair           1    True      3.47         6      28        2     2         1      0        0
```

Légende :
- `strict` : `strict_success_count` final, qui exige toute la chaîne
  apply→compile→test→class_version 61→`official_eval Success=True`.
- `compile/test/official` : nombre d'instances dont **le candidat finalisé**
  passe ce signal.
- `repair` : nombre d'instances pour lesquelles au moins un candidat de
  reparation LLM a été créé.
- `dedup`, `rep_supp` : compteurs Phase 5 (`candidate.deduped`,
  `candidate.repeat_failure_suppressed`).

### A1 LLM vs A1 déterministe (campaign précédente)

| | A1 deterministic | A1 LLM |
|---|---|---|
| strict_success | 0/30 | **1/30** |
| compile_success (validation) | 4/30 | **9/30** (+125%) |
| test_success (validation) | 1/30 | **4/30** (+300%) |
| Origins | `builtin_deterministic_pom17` × 30 | `llm_deepseek-chat_t0` × 30 |

Le LLM apporte un saut quantitatif sur la première vague de candidats. Le
sur-coût budget LLM est borné à 1 appel par instance pour A1.

### A2 vs A1 (effet du repair linéaire)

- 27/30 instances ont déclenché un repair LLM (`feedback.created` →
  `propose_repair` → nouveau candidat).
- Compile pass : 9 → 10 (gain +1 sur `bjoernkw__oauth2__with__jira` et
  `mtuhide__cocotemp` ; perte sur `jodaorg__joda__beans` à cause de la
  variance LLM entre runs).
- Strict success inchangé (1/30) : l'`official_eval` reste le goulot.

### A3 vs A2 (effet du branching)

- avg `candidate.created` par instance : 1.90 → 3.47 (max 6) — branching
  effectif avec 4 origines distinctes (`llm_*_t0`, `llm_*_t4`, idem repair).
- 28/30 instances ont eu au moins un repair LLM.
- `dedup_skipped_total = 0` et `repeat_failure_suppressed_total = 0` : sur ce
  subset, le LLM produit suffisamment de diversité entre températures pour
  que la dédup ne se déclenche pas.
- Compile pass : 10 → 9 (variance, pas de gain net) ; strict success : 1.

### Instances qui passent compile par bras

```
A1 LLM : 9 / 30  → {ejserver, joda-beans, vaadin-helper, citymonstret, refactoring-bot, comic-con, easy-crypto, packtpublishing, heapdump}
A2 LLM : 10 / 30 → {ejserver, vaadin-helper, citymonstret, refactoring-bot, comic-con, mtuhide-cocotemp, easy-crypto, packtpublishing, heapdump, bjoernkw}
A3 LLM : 9 / 30  → {ejserver, joda-beans, vaadin-helper, refactoring-bot, comic-con, easy-crypto, packtpublishing, heapdump, bjoernkw}
```

Strict success unique partagé : `comic__con__museum__fan__forge__backend`.

## Validation infrastructure

| Check | Résultat |
|---|---|
| Live == replay (3 bras) | ✓ 3/3 |
| `selection.completed` émis | ✓ 30/30 par bras |
| `run.completed` avec compteurs Phase 5 | ✓ 30/30 par bras |
| `selection_rationale` populé | ✓ 30/30 par bras |
| Container exit code | ✓ 0 sur les 3 bras |
| Tests unitaires V10 | ✓ 148 passed (132 + 16 nouveaux) |

## Lecture scientifique

1. **Le LLM apporte le gros gain** : passer du provider déterministe au
   provider DeepSeek fait passer compile 4 → 9 (+125%) et débloque le
   premier `strict_success`.
2. **Le repair linéaire (A2)** ajoute marginalement +1 instance compile mais
   ne débloque pas de strict_success additionnel sur ce subset / cette seed.
3. **Le branching (A3) ne se distingue pas statistiquement de A2** sur
   1 seed × 30 instances : variance LLM > effet branching. Pour valider H2
   il faudra **multiplier les seeds** et/ou élargir le subset, ou bien
   intégrer le contexte stigmergique (Phase 6 A4) pour donner un avantage
   structurel au branching.
4. **Le verrou est l'`official_eval`** : 1 seule instance traverse la chaîne
   stricte (`comic__con`) sur les trois bras. Le verifier local est plus
   permissif que `run_eval.py` officiel. Cela laisse une marge nette pour
   les phases suivantes du ladder.

## Reproduction

```bash
# A1 (1 cand LLM, 0 repair)
DEEPSEEK_API_KEY=$(grep DEEPSEEK_API_KEY .env | cut -d= -f2) \
/tmp/launch_arm_llm.sh A1_agentless_basic agentless_basic 1 0 1 \
  fixtures/migrationbench/subsets/main_30.jsonl \
  campaign_results/v10/ablation_main30_llm

# A2 (1 cand + 1 repair)
/tmp/launch_arm_llm.sh A2_linear_repair branching_repair 1 1 1 \
  fixtures/migrationbench/subsets/main_30.jsonl \
  campaign_results/v10/ablation_main30_llm

# A3 (2 cand + branching repair)
/tmp/launch_arm_llm.sh A3_branching_repair branching_repair 2 1 2 \
  fixtures/migrationbench/subsets/main_30.jsonl \
  campaign_results/v10/ablation_main30_llm
```

## Suivis

- Phase 6 (StigmergicBlackboard A4) : ajouter le médium stigmergique +
  signaux pheromone_hit_rate / feedback_reuse_rate / repeated_failure_suppression
  pour mesurer le gain de A4 sur A3.
- **Multi-seed** : exécuter chaque bras avec `seed ∈ {42, 7, 13}` pour
  estimer la variance LLM avant la campagne finale.
- **Calibration verifier** : comprendre l'écart entre verifier local et
  `run_eval.py` officiel ; possiblement ajuster le contrat strict.
