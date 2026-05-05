# ADR-019 — Phase 5 V10 : BranchingRepair A3, signature dedup, repeated-failure suppression, explainable selector

**Date** : 2026-05-04

**Statut** : Accepté

**Contexte** : Lotfi + Claude Code

---

## Contexte

Le plan canonique `documentation/redisgn_v2/plan_v10_from_scratch_rebuild.md` exige
en Phase 5 le bras d'ablation **A3 `branching_repair`** avec :

- isolation par branche (livrée Phase 4 via `MigrationBenchWorkspace.branch_workspace`),
- déduplication par signature de candidats,
- suppression des échecs répétés,
- selector déterministe **explicable par preuves**,
- comparaison A1/A2/A3 sur la fixture smoke.

Avant Phase 5, `core_v10/strategy_runner.py` exposait déjà
`run_branching_repair`, mais sans dedup, sans suppression, et sans rationale
visible côté EventLog ou summary. Le DoD de Phase 5 ("sélection explicable par
preuves") n'était donc pas atteint, et un comparatif A1↔A3 manquait.

## Alternatives Considérées

### Alternative 1 : retro-fitter dedup et rationale dans le runner V10 (retenu)

**Description** :  
Étendre `core_v10/strategy_runner.py` pour :

- introduire un `_SignatureTracker` interne (sha256 du couple `kind+payload`) ;
- skipper toute frontier de réparation dont la signature a déjà été vue dans le
  run, en émettant un event `candidate.deduped` ;
- comptabiliser les échecs par signature et supprimer toute proposition de
  réparation ré-introduisant une signature ayant déjà échoué, en émettant
  `candidate.repeat_failure_suppressed` ;
- produire un `SelectionRationale` (id sélectionné, raison, score, compétiteurs
  ordonnés par score), persisté dans `StrategyResult` et émis comme event
  `selection.completed` ;
- ajouter un script `scripts/bench/compare_strategies.py` qui exécute A1, A2,
  A3 sur la même fixture et écrit `comparison.json`.

**Avantages** :

- ✅ Aucun nouveau module, surface API V10 stable.
- ✅ Tous les nouveaux signaux passent par l'EventLog donc l'invariant
  `live==replay` est préservé (les compteurs sont reconstructibles depuis les
  events).
- ✅ Le rationale est traçable bout en bout (StrategyResult, EventLog,
  summary, comparison).

**Inconvénients** :

- ❌ A2 dans le plan = "typed_blackboard" avec auto-élection de capability.
  Cette surface complète relève de Phase 3 et n'est pas livrée en Phase 5.
  L'ADR documente A2 comme "linear_repair" placeholder (single-track repair
  sans fan-out), suffisant pour isoler la contribution de A3 (branching) sur
  la fixture smoke.

### Alternative 2 : extension externe du runner via décorateur ou wrapper

**Description** :  
Garder `core_v10/strategy_runner.py` intact et placer la logique dedup +
rationale dans un wrapper côté `scripts/bench/`.

**Avantages** :

- ✅ Surface V10 plus pure.

**Inconvénients** :

- ❌ Le wrapper aurait besoin de réémettre des events dans l'EventLog avec une
  identité douteuse (qui est l'actor ? le runner ou le wrapper ?). Risque de
  divergence `live!=replay`.
- ❌ Les autres adaptateurs futurs ne bénéficieraient pas du dedup sans
  importer le wrapper. Le bras A3 doit être un attribut du runner, pas du
  bench harness.

---

## Décision

**Choix retenu** : Alternative 1.

**Justification** :  
Le runner reste le seul propriétaire de la logique de coordination dedup +
rationale, ce qui garantit que tout adaptateur (toy, MigrationBench, futurs)
hérite gratuitement de Phase 5 sans changement. L'EventLog reste la
source-de-vérité unique : `dedup_skipped_total` et
`repeat_failure_suppressed_total` sont reconstruits par
`scripts.bench.telemetry.replay_summary_from_dir` en comptant les events
`candidate.deduped` / `candidate.repeat_failure_suppressed`. L'invariant
`live==replay` de Phase 4 reste protégé.

A2 minimal "linear_repair" suffit pour le DoD : il instancie
`branching_repair` avec `max_candidates=1` et un round de repair sans fan-out,
ce qui isole correctement la contribution combinatoire de A3 (branching +
dedup + suppression) sur la fixture smoke. Le DoD complet de Phase 3 (typed
blackboard, capability auto-election) reste à finaliser ultérieurement.

---

## Conséquences

### Positives

- ✅ Phase 5 livrée : A3 dispose maintenant de dedup, suppression,
  selection_rationale.
- ✅ `scripts/bench/compare_strategies.py` standardise les comparaisons A1/A2/A3
  sur n'importe quel adaptateur enregistré.
- ✅ Le rationale est sérialisé dans summary et dans `comparison.json` →
  reproductibilité scientifique : on peut justifier pourquoi un hypothesis a
  été retenu sans rejouer le run.

### Négatives

- ⚠️ A2 placeholder n'inclut pas la couche "typed blackboard" du plan ; cela
  doit être levé lors de la finalisation de Phase 3 (auto-élection de
  capabilities, knowledge sources). Sans cela, la comparaison A2↔A3 capture
  uniquement l'effet du fan-out, pas l'effet du blackboard typé.
- ⚠️ La signature `kind+payload` est volontairement minimale et ignore
  `metadata`. Si un adaptateur encode des infos différenciantes dans
  `metadata`, le dedup peut être trop agressif. Un override
  `signature_fn(candidate)` est un point d'extension futur.

### Impacts sur le Code

- Fichiers modifiés :
  - `core_v10/strategy_runner.py` (SelectionRationale, dedup, suppression,
    rationale events, _SignatureTracker)
  - `scripts/bench/telemetry.py` (constantes events, champs Summary +
    InstanceSummary, reconstruction depuis EventLog)
- Nouveaux modules :
  - `scripts/bench/compare_strategies.py` (ablation harness A1/A2/A3)
  - `tests/unit/v10/test_strategy_runner_phase5.py`
  - `tests/unit/v10/bench/test_compare_strategies.py`

### Impacts sur la Méthodologie

- Métriques nouvelles : `dedup_skipped_total`, `repeat_failure_suppressed_total`,
  `selection_rationale` (par instance) — toutes reconstructibles depuis l'EventLog.
- Comparaisons d'ablation : la fixture smoke est désormais exécutable en trois
  bras isolés via `python -m scripts.bench.compare_strategies --adapter
  migrationbench --subset fixtures/migrationbench/subsets/smoke_5.jsonl
  --out-dir campaign_results/v10/migrationbench_smoke_compare`.

---

## Validation

**Critères de succès** :

1. ✅ 6 nouveaux tests unitaires Phase 5 (`tests/unit/v10/test_strategy_runner_phase5.py`)
   verts : signature tracker, dedup initial, suppression cross-rounds,
   rationale avec compétiteurs, no_validated rationale.
2. ✅ 4 tests intégration ablation harness
   (`tests/unit/v10/bench/test_compare_strategies.py`) verts : 3-arms run,
   live==replay parity per arm, payload A3 expose dedup et rationale, custom
   arm list.
3. ✅ Suite V10 totale : **136 passed** (était 126, +10 Phase 5).
4. ✅ Replay du smoke réel pré-Phase 5 reste compatible : nouveaux compteurs à 0,
   strict_count, by_signal, instances inchangés.

**Tests à effectuer** :

```bash
.venv/bin/python -m pytest tests/unit/v10/ tests/integration/v10/ -q
```

**Résultat après implémentation** :

- [x] Tous les critères validés
- [x] Décision confirmée

---

## Références

- Plan canonique : `documentation/redisgn_v2/plan_v10_from_scratch_rebuild.md`
  §13 (ablation ladder) et §Phase 5.
- Phase 4 (livrée 2026-05-04) : ADR-018 + smoke réel
  `campaign_results/v10/migrationbench_smoke` (live==replay vérifié).
- Sprint 9 legacy `core/` (V3) : preuve qu'un système dépourvu de selector
  explicable rend les retours d'expérience non auditables.

---

## Métadonnées

- **ADR créé par** : Claude Code
- **ADR validé par** : Auto-validé par IA (tests verts, replay parity OK)
- **Version** : 1.0
- **Dernière modification** : 2026-05-04
