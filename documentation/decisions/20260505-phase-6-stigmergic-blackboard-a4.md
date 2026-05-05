# 2026-05-05 — Phase 6 V10 : StigmergicBlackboard A4 (pré-registration)

**Statut** : pré-registré, code en cours d'implémentation. Cet ADR fixe la
forme du bras A4 et les métriques de comparaison **avant** toute exécution sur
`main_30`, afin d'éviter le *garden of forking paths* / p-hacking. Toute
déviation ultérieure nécessitera un nouvel ADR ou un addendum daté.

## Contexte

La campagne Phase 5 v2 (2026-05-04, ADR `20260504-pistes-1-4-preregistration.md`)
a livré :

- A1 strict 1/30, finalize 3/30 (apply_ok 29) ;
- A2 strict 1/30, finalize 3/30 (apply_ok 51) ;
- A3 strict 1/30, finalize **4/30** (apply_ok 79) ;
- les pistes 1+4 (contexte enrichi + `preserve_existing_tests`) tracées dans
  100 % des `feedback.created` events ;
- live==replay parity ✓ sur les 3 bras.

L'effet du branching A3 devient mesurable sur les signaux finaux (+1 finalize
vs A2) mais le `strict_success` reste plafonné par l'`official_eval`. Aucune
des couches actuelles n'utilise ces feedbacks répétés pour modifier les
décisions futures dans le run : le `feedback.created` est jeté dès qu'il a
servi à formuler le repair_provider du candidat suivant.

H2 (plan canonique §H1-H4) : *« Une couche stigmergique sur blackboard apporte
un gain mesurable quand plusieurs hypothèses concurrentes existent — A4 vs A3,
à budget constant. »* Phase 6 vise à confirmer ou infirmer H2 proprement.

## Décisions pré-registrées

### A4 = A3 + couche signal active (à budget identique)

A4 réutilise `branching_repair` avec exactement les mêmes budgets que A3 sur
`main_30` :

| Aspect | A3 | A4 |
|---|---|---|
| `max_candidates` | 2 | 2 |
| `max_repair_rounds` | 1 | 1 |
| `max_repairs_per_candidate` | 2 | 2 |
| Modèle | deepseek-chat | deepseek-chat |
| Seed | 42 | 42 |
| Subset | main_30 | main_30 |
| Pistes 1+4 | ✓ | ✓ |
| `official_eval` | inchangé | inchangé |
| Verifier MigrationBench | inchangé | inchangé |
| Couche signal | ✗ | ✓ |

**Le seul delta entre A3 et A4 est la couche stigmergique.** A budget
constant, par construction.

### Couche stigmergique (pré-registrée)

`core_v10/signals.py` étendu :

- `SignalRecord(signal_id, kind, target, intensity, evidence, half_life,
  created_at_seq, last_seen_seq)` ;
- `SignalStore` avec `emit / reinforce / inhibit / decay / support_for /
  by_kind / from_events`.

Decay : `intensity_t = intensity_0 * 0.5 ** ((now_seq - last_seen_seq) / half_life)`
avec `half_life = 8` events par défaut (cohérent avec plan canonique §12.2).

`core_v10/signal_policy.py` (politique pure, sans état latéral) :

- `feedback.failure_type=X` + `severity ∈ {blocking, warning}` → `INHIBIT
  target="failure_type:X" intensity=0.5..0.8` ; renforcé +0.1 par répétition ;
- `feedback.anti_actions ⊃ {"preserve_existing_tests"}` → `INHIBIT
  target="anti:preserve_existing_tests" intensity=0.6` ; renforcé +0.05 par
  répétition ;
- `validation.passed=True` → `SUPPORT target="origin:<candidate.origin>"
  intensity=0.7` + `REINFORCE target="kind:<candidate.kind>" intensity=0.5` ;
- `repeat_failure` → `INHIBIT target="signature:<sha>" intensity=0.9` ;
- nœuds multiples → `NOVELTY target="hypothesis_space" intensity=clamp(n/10)`.

Les intensités initiales sont **conservatrices** (≤ 0.8 sauf signature 0.9)
pour limiter le risque de régression A4 < A3 par signal trop agressif.

### Effet sur la décision (où la stigmergie agit)

A4 lit le `SignalStore` à trois points :

1. **Avant verify** : trie les candidats du frontier par `support_for(origin)`
   décroissant. Drop déterministe d'un candidat si `INHIBIT(target="signature:
   <sha>") ≥ 0.8` (équivalent dedup signature renforcé).
2. **Avant repair** : `repair_provider` reçoit `Observation.metadata
   ["stigmergic_digest"]` (top-3 inhibitions, top-3 supports). Lecture pure ;
   le provider est libre d'ignorer.
3. **Sélection finale** : si plusieurs candidats validés, départage par
   `support_for(origin)` (puis fallback `HypothesisGraph.score`). Tracé dans
   `SelectionRationale.competitors[*].signal_score`.

Émission systématique d'un événement `signal.emitted` à chaque `emit /
reinforce / inhibit`, et d'un événement `signal.applied` à chaque fois que
*la décision change* à cause d'un signal (avec `effect ∈ {drop, reorder,
finalize_tiebreak}`).

### Invariants vérifiés par tests

- **A4 ≡ A3 quand `SignalStore` reste vide** : test d'intégration avec une
  politique noop, comparaison candidat par candidat, score par score.
- **`live==replay` parity** sur A4 (et A3) : le `SignalStore` est
  reconstructible depuis les events `signal.emitted`, et la métrique de
  télémétrie est rejouable bit-pour-bit.
- **A1, A2, A3 inchangés** : test de non-régression bit-pour-bit sur les
  `summary.json` Phase 5 v2 (les bras A1/A2/A3 ne touchent jamais le
  `SignalStore`, ils ne lisent ni n'émettent de signal).

### Ce qui ne change pas

- `adapters_v10/migrationbench/verifier.py` (8 signaux canoniques inchangés) ;
- `OfficialEvaluator` et `external/MigrationBench/run_eval.py` (inchangés) ;
- les seuils du contrat strict (`apply ∧ compile ∧ test ∧ class_version 61 ∧
  official Success=True`) ;
- les pistes 1+4 (contexte enrichi + `preserve_existing_tests`) ;
- le format `manifest.json` / `runs.jsonl` / `events/<inst>/eventlog.jsonl`.

## Métriques canoniques pré-registrées

Trois compteurs ajoutés au `Summary` (rétro-compat : 0 sur A1/A2/A3) :

| Métrique | Définition reconstructible | Question scientifique |
|---|---|---|
| `pheromone_hit_rate` | (#`signal.applied` events avec `effect ∈ {drop, reorder, finalize_tiebreak}` et `kind ≠ NOVELTY`) / `candidate_count` | À quelle fréquence la stigmergie modifie-t-elle effectivement une décision ? |
| `feedback_reuse_rate` | (#anti-action signaux `signal.applied` *au-delà de la première émission*) / total anti-action signaux émis | La stigmergie réutilise-t-elle un feedback ancien ? |
| `repeated_failure_suppression` | `repeat_failure_suppressed_total + #signal.applied[effect=drop, target=signature:*]` | Combien d'erreurs répétées ont été coupées court ? |

## Critères d'acceptation (DoD pré-registrée)

1. Définition canonique Phase 6 du plan §"Phase 6 — StigmergicBlackboard A4"
   satisfaite : *au moins une décision change à cause d'un signal stigmergique
   tracé* ⇒ ≥ 1 `signal.applied` event sur le smoke A4 et sur main_30 A4.
2. *Le gain ou l'absence de gain est mesurable* ⇒ `comparison.json` Phase 6
   contient `pheromone_hit_rate`, `feedback_reuse_rate`,
   `repeated_failure_suppression`, plus tous les signaux canoniques (apply_ok,
   compile, test, strict, finalized) pour A3 et A4 sur main_30. **Si A4 ≤ A3
   en strict_success, c'est un résultat scientifique négatif documenté, pas
   un échec d'implémentation.**
3. A1, A2, A3 inchangés (test de non-régression).
4. `live==replay` parity ✓ sur A3 et A4 (smoke + main_30).
5. ≥ 187 tests V10 verts (162 + ≥ 25 nouveaux : signal store, signal policy,
   A4 strategy, telemetry, compare arms, intégration).
6. Service Docker `ablation-a3-vs-a4-smoke` exit 0 + `ablation-a3-vs-a4-main30`
   exit 0.
7. ADR signé daté **avant** la campagne main_30.

## Justification scientifique

- A4 ≡ A3 quand `SignalStore` vide : la couche stigmergique est strictement
  additive et désactivable. Pas d'ambiguïté sur l'origine d'un éventuel gain.
- À budget constant (mêmes `max_candidates`, `max_repair_rounds`,
  `max_repairs_per_candidate`, mêmes pistes 1+4) : la seule variable
  manipulée est la présence/absence du `SignalStore`.
- Pré-enregistré avant toute campagne main_30 : empêche un choix opportuniste
  post-résultats (intensités, half-life, règles de policy).
- Compteurs `pheromone_hit_rate` / `feedback_reuse_rate` /
  `repeated_failure_suppression` reconstructibles depuis l'EventLog : un
  reviewer peut vérifier indépendamment chaque chiffre.
- Verifier et `official_eval` inchangés : aucun risque de gonfler le
  `strict_success` par modification de l'oracle.

## Suivi

- Implémentation 6.1 → 6.10 (cf. plan d'exécution
  `/Users/lotfi/.claude/plans/reactive-wibbling-peach.md`) ;
- smoke Docker `ablation-a3-vs-a4-smoke` ;
- main_30 séquentiel A3 puis A4, audit toutes ~10 instances ;
- `phase_06_artifact.md` (livraison) + `phase_06_ablation_main30.md`
  (résultats) ;
- mise à jour `CLAUDE.md` (section Phase 6) et `MEMORY.md`.
