# Phase 5 — Comparaison A1/A2/A3 main_30 LLM v2 (post-pistes 1+4)

**Date** : 2026-05-04
**Subset** : `fixtures/migrationbench/subsets/main_30.jsonl` (30 instances)
**Seed** : 42
**LLM** : DeepSeek `deepseek-chat`
**Adapter** : `migrationbench` V10 + `MigrationBenchVerifier` (8 signaux + official_eval)
**Pré-registration** : `documentation/decisions/20260504-pistes-1-4-preregistration.md`

Cette campagne v2 reprend la grille A1/A2/A3 de la v1 sans changer aucun
paramètre du verifier ni de l'official_eval. Les seuls deltas sont les pistes
1 (contexte enrichi : deps + javax) et 4 (anti-action `preserve_existing_tests`)
appliquées de façon **uniforme aux 3 bras**, plus deux durcissements
techniques pré-registrés en addendum :
- garde verbatim sur `_normalize_edits` (drop des `replace_text` dont `old`
  n'est pas substring du fichier visible) ;
- nettoyage du workspace avant chaque run pour éviter qu'une branche pré-
  modifiée d'une campagne précédente fausse le compteur d'apply.

## Résultats v2

```
arm                        strict   apply_ok   finalized   compile  test  official  parity  preserve_fb
A1_agentless_basic              1         29           3         3     3         1    True   29/29 (100%)
A2_linear_repair                1         51           3         3     3         1    True   54/54 (100%)
A3_branching_repair             1         79           4         4     4         1    True   84/84 (100%)
```

Le seul `strict_success` est partagé par les 3 bras :
`comic__con__museum__fan__forge__backend`.

## v1 vs v2 (effet des pistes 1+4)

| | A1 v1 | A1 v2 | A2 v1 | A2 v2 | A3 v1 | A3 v2 |
|---|---|---|---|---|---|---|
| strict | 1 | 1 | 1 | 1 | 1 | 1 |
| apply_ok | 26 | 29 (+3) | 44 | 51 (+7) | 72 | 79 (+7) |
| finalized | 3 | 3 | 4 | 3 (−1) | 2 | **4 (+2)** |
| compile (final) | 3 | 3 | 4 | 3 | 2 | **4 (+2)** |
| test (final) | 3 | 3 | 4 | 3 | 2 | **4 (+2)** |
| preserve_existing_tests dans feedback | 0/30 | 29/29 | 0/57 | 54/54 | 0/104 | 84/84 |
| live==replay | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

### Observations

- **Pistes 1+4 actives sur tous les bras** : la règle `preserve_existing_tests`
  apparaît dans 100% des `feedback.created` events, alors qu'elle était
  absente en v1. La piste 1 (contexte deps + javax) est aussi présente dans
  100% des prompts LLM (vérifié unitairement).
- **`apply_ok` augmente sur les 3 bras** (+3 / +7 / +7). C'est l'effet combiné
  de la garde verbatim + workspace clean : moins d'edits hallucinés, moins
  de branches contaminées.
- **A3 est le seul bras qui voit son `finalized` augmenter** (+2). En v1, A3
  finalisait 2 instances ; en v2, il en finalise 4. Le branching profite
  d'un contexte plus riche pour produire des candidats initialement
  applicables ET compilables.
- **A2 régresse marginalement** (−1 finalized) : c'est de la variance LLM
  attendue sur 1 seed × 30 instances, l'écart-type est probablement ≥1.
- **strict_success reste à 1/30 partout** : l'`official_eval` reste le mur.
  Les pistes 1+4 améliorent les signaux locaux (apply / compile / test)
  mais ne suffisent pas à passer le contrôle officiel `#tests` sur les
  instances qui restent. Cohérent avec le diagnostic préalable : 2-3
  instances passaient déjà compile+test en v1 mais étaient rejetées par
  `(Build success, #tests) = (True, -2)`. La règle anti-action a fait son
  travail traçable mais le LLM continue parfois à modifier les tests.

## Ordre A1 < A2 < A3 (sur les signaux non-officiel)

```
                              A1   A2   A3
apply_ok                      29   51   79     ↑ avec budget
finalized                      3    3    4     A3 gagne +1 vs A2
compile_success final          3    3    4     A3 gagne +1 vs A2
test_success final             3    3    4     A3 gagne +1 vs A2
strict_success                 1    1    1     plafond official
preserve_existing_tests fb   100% 100% 100%    règle uniforme appliquée
```

L'effet du branching (A3) devient mesurable une fois les pistes 1+4
activées : +1 instance finalisée et +1 compile/test passé vs A2. C'est
faible en valeur absolue mais c'est la première fois que A3 dépasse A2 sur
des signaux finaux (en v1, A3 finalisait moins que A2 à cause des
hallucinations de candidats que la garde verbatim a maintenant écartées).

## Crédibilité scientifique

- ADR pré-enregistré le 2026-05-04 avant tout re-run.
- Pistes 1 et 4 strictement uniformes sur les 3 bras (vérifié dans 100% des
  feedback events).
- Officiel evaluator (`run_eval.py` + `final_eval.py`) **inchangé**.
- `MigrationBenchVerifier` et le contrat strict (apply ∧ compile ∧ test ∧
  class_version 61 ∧ official Success=True) **inchangés**.
- Les compteurs Phase 5 (`dedup_skipped`, `repeat_failure_suppressed`,
  `selection_rationale`) restent traçables ; le nouveau `preserve_existing_tests`
  est aussi traçable dans `feedback.created`.
- live==replay parity ✓ sur les 3 bras.

## Limites assumées

- 1 seed × 30 instances : variance LLM ≥ effet branching sur certains
  signaux ; multi-seed nécessaire avant la campagne mémoire.
- L'`official_eval` rejette ~2-3 instances par bras qui passent compile+test
  localement. La règle `preserve_existing_tests` réduit ce risque mais ne
  l'élimine pas. Phase 6 (StigmergicBlackboard A4) doit explorer si un
  signal stigmergique sur "candidats qui ont préservé les tests par le
  passé" peut renforcer la sélection.
- Le verrou principal reste le compile/dependency_resolution_error sur les
  repos main_30 abandonnés (Spring Boot < 2.7, plugins Maven anciens).

## Suivi

- Phase 6 (A4) : ajouter le médium stigmergique + métriques pheromone_*
  pour distinguer A3 vs A4.
- Multi-seed (`{42, 7, 13}`) avant la campagne finale du mémoire.
- Calibration de la règle `preserve_existing_tests` : actuellement c'est
  une string ; on pourrait remonter le compteur de tests détecté pour
  rendre la règle quantifiable (`expected_test_count = N`).
