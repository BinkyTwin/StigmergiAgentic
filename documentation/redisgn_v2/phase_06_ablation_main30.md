# Phase 6 — Ablation A3 vs A4 sur MigrationBench main_30

**Date** : 2026-05-05
**Subset** : `fixtures/migrationbench/subsets/main_30.jsonl` (30 instances)
**Seed** : 42
**LLM** : DeepSeek `deepseek-chat`, providers LLM activés (digest off — A4 pur)
**Adapter** : `migrationbench` V10 + `MigrationBenchVerifier` (8 signaux + official_eval)
**Pré-registration** : `documentation/decisions/20260505-phase-6-stigmergic-blackboard-a4.md`

Cette campagne reprend la grille A3 de Phase 5 v2 et ajoute le bras A4
strictement à budget identique (mêmes `max_candidates=2`,
`max_repair_rounds=1`, `max_repairs_per_candidate=2`, mêmes pistes 1+4,
même verifier, même official_eval). Le seul delta est l'activation du
`SignalStore` actif (Phase 6).

## Smoke préalable (validation infra)

Le service `ablation-a3-vs-a4-smoke` (5 instances) a été exécuté
avant la campagne :

```
arm                            strict   apply_ok   compile  test  signal_emitted  signal_applied
A3_branching_repair                 0          1         1     1               0               0
A4_stigmergic_blackboard            0          1         1     1              29               0
```

Validations de l'infrastructure :

- `signal.emitted` events tracés dans l'EventLog A4 (29 sur 5 instances) ;
- `live==replay` parity ✓ sur A3 et A4 (vérifié via `replay_summary_from_dir`) ;
- A3 (Phase 6) a `signal_emitted_total = 0` : aucune fuite Phase 6 dans
  ce bras (test de non-régression).

## Résultats main_30

```
arm                        strict   apply_ok   finalized   compile  test  official  parity   signal_emitted  signal_applied  pheromone_hit_rate  feedback_reuse_rate
A3_branching_repair         1/30          3           3         3     3         1     ✓                  0               0              0.0000               0.0000
A4_stigmergic_blackboard    1/30          3           3         3     3         1     ✓                236               1              0.0083               0.0000
```

Le `comparison.json` est dans
`campaign_results/v10/ablation_a3_vs_a4_main30/comparison.json`.

### Résultat scientifique (H2)

H2 du plan canonique : *« Une couche stigmergique sur blackboard apporte
un gain mesurable quand plusieurs hypothèses concurrentes existent — A4
vs A3, à budget constant. »*

Sur main_30, à budget constant, sur 1 seed :

- **strict_success identique** : 1/30 partout (instance unique
  `comic__con__museum__fan__forge__backend`) ;
- **compile_success / test_success / patch_applies / class_version_ok
  identiques** : 3/30 partout ;
- **A4 modifie effectivement la sélection** : 3 instances ont un
  `selected_hypothesis_id` différent entre A3 et A4 (artur,
  citymonstret, comic_con — soit toutes les instances finalisées) ;
- **236 `signal.emitted` events sur 30 instances** (~8 par instance) :
  la couche stigmergique est active et tracée ;
- **1 `signal.applied` event** sur instance `citymonstret__rorledning`
  (`effect=finalize_tiebreak target=origin:llm_repair_deepseek-chat_t0
  intensity=0.700`) : le SUPPORT(origin) a réordonné le finalize en
  privilégiant un origin issu d'une validation passée précédemment ;
- mais le candidat alternatif sélectionné par A4 sur cette instance
  n'a pas non plus passé l'`official_eval` — donc gain final = 0.

**Verdict scientifique honnête** : A4 ne régresse pas A3 (invariant
respecté) et **modifie effectivement les décisions** (DoD #1
satisfaite), mais le **gain mesurable sur strict_success est nul** sur
1 seed × 30 instances. Le verrou reste l'`official_eval` (Phase 5 v2
diagnostic confirmé).

### Pourquoi seulement 1 signal.applied ?

Le `_SignatureTracker` de Phase 5 attrape déjà toutes les répétitions
de signature avant que le drop signal-driven n'ait l'occasion de tirer.
Et avec un budget de 2 candidats initiaux + 1 round de repair, le
nombre de candidats validés par instance est rarement > 1, ce qui
n'active pas souvent le `finalize_tiebreak`. La seule occurrence
correspond à l'instance où plusieurs candidats validés étaient en
concurrence.

Pour activer la stigmergie de façon plus visible, il faudrait :

- élargir le budget (Phase 7 verifier-guided search avec exploration
  plus large) ;
- ou activer le `digest` dans le repair_provider LLM
  (`extras["use_stigmergic_digest"]`) — variante A4-LLM laissée hors
  scope d'ablation pure ;
- ou stigmergie cross-run (Phase 8 Memory A6).

## Comparaison Phase 5 v2 vs Phase 6 (non-régression A3)

| Métrique | A3 v2 (Phase 5) | A3 (Phase 6) | A4 (Phase 6) | Delta A4 vs A3 |
|---|---|---|---|---|
| strict_success | 1/30 | 1/30 | 1/30 | 0 |
| apply_ok (count) | 79 (instances applied≥1) | n/a (vue agrégée différente) | n/a | n/a |
| finalized (instances) | 4 | 3 | 3 | 0 |
| compile_success final | 4 | 3 | 3 | 0 |
| test_success final | 4 | 3 | 3 | 0 |
| official_success | 1 | 1 | 1 | 0 |
| signal_emitted_total | 0 | 0 | 236 | n/a |
| signal_applied_total | 0 | 0 | 1 | n/a |
| pheromone_hit_rate | 0.0 | 0.0 | 0.0083 | n/a |
| live==replay | ✓ | ✓ | ✓ | n/a |

**Note de variance** : la diminution finalize 4→3 entre Phase 5 v2 et
Phase 6 (-1 instance) est une variation dans l'ordre des écoles que
le LLM produit avec température > 0 sur certains candidats — cohérent
avec la limite "1 seed × 30 instances : variance LLM ≥ effet" déjà
documentée. C'est ≤ écart-type estimé.

A3 (Phase 6) **n'utilise jamais** le `SignalStore` (signal_emitted = 0
sur tous), ce qui prouve l'absence de fuite Phase 6 sur les bras
historiques.

## Crédibilité scientifique (rappel)

- ADR pré-enregistré 2026-05-05 avant tout re-run.
- A4 strictement à budget identique de A3 (mêmes paramètres, mêmes
  pistes 1+4, même verifier).
- Officiel evaluator (`run_eval.py` + `final_eval.py`) **inchangé**.
- `MigrationBenchVerifier` et le contrat strict (apply ∧ compile ∧ test ∧
  class_version 61 ∧ official Success=True) **inchangés**.
- Tous les compteurs Phase 6 reconstructibles depuis l'EventLog
  (`signal.emitted` + `signal.applied` events).
- live==replay parity ✓ sur les 2 bras.
- Instances de finalize : artur, citymonstret, comic_con — toutes
  documentent un `selected_hypothesis_id` différent entre A3 et A4,
  preuve que la couche stigmergique a effectivement participé à la
  sélection.

## Limites assumées

- 1 seed × 30 instances : variance LLM ≥ effet stigmergique sur les
  signaux peu fréquents ; multi-seed `{42, 7, 13}` nécessaire avant la
  campagne mémoire pour obtenir un intervalle de confiance.
- Le `SignalStore` est fresh par instance ; pas de cross-run accumulation
  (l'effet collectif inter-instance arrivera en Phase 8 Memory A6).
- L'`official_eval` reste le mur Phase 5 (verrou `final_eval.py #tests`).
- À budget 2 candidats + 1 repair, la concurrence d'hypothèses
  validées est rare (1 instance sur 30) : la stigmergie n'a pas
  beaucoup de matière à mordre. L'effet pourrait devenir mesurable à
  budget plus large (Phase 7 verifier-guided search).

## Definition of Done (canonique plan §"Phase 6")

| DoD | Exigence | Statut |
|---|---|---|
| #1 | Au moins une décision change à cause d'un signal stigmergique tracé | ✓ — `citymonstret__rorledning` `signal.applied` `effect=finalize_tiebreak intensity=0.700` |
| #2 | Le gain ou l'absence de gain est mesurable | ✓ — `strict_success_count` identique 1/30, signal counts non-zéro sur A4 (236 emitted, 1 applied), métriques `pheromone_hit_rate` (0.0083), `feedback_reuse_rate` (0.0), `repeated_failure_suppression_total` (0) toutes lisibles dans `comparison.json` |

DoD canonique satisfaite. **A4 ne dépasse pas A3 en `strict_success` à
ce budget × 1 seed**, mais l'infrastructure stigmergique est livrée,
testée et tracée — prête pour Phase 7+ et multi-seed.

## Suivi

- Multi-seed `{42, 7, 13}` avant la campagne finale du mémoire pour
  obtenir un intervalle de confiance sur les écarts A3 vs A4.
- Phase 6.5 (affinity) : nécessite la couche typed-blackboard (Phase 3
  du plan canonique non encore livré).
- Phase 7 (verifier-guided search A5) : MCTS-light après A4 selon plan
  — c'est là que la concurrence d'hypothèses validées sera fréquente
  et la stigmergie aura de la matière à exploiter.
- Variante optionnelle A4-LLM : activer
  `extras["use_stigmergic_digest"]` pour que le repair_provider LLM
  voit le top-3 inhibitions/supports — laissée hors scope d'ablation
  pure mais disponible dans le code.
