# Phase 6 V10 — StigmergicBlackboard A4 (livraison technique)

**Statut** : implémenté, ADR pré-registré
`documentation/decisions/20260505-phase-6-stigmergic-blackboard-a4.md`,
suite de tests verte.

## Périmètre livré

Le plan canonique
`documentation/redisgn_v2/plan_v10_from_scratch_rebuild.md` §"Phase 6 —
StigmergicBlackboard A4" demandait :

- `core_v10/signals.py` ;
- support / inhibition / reinforcement / decay / affinity ;
- métriques `pheromone_hit_rate`, `feedback_reuse_rate`,
  `repeated_failure_suppression` ;
- ablation A3 vs A4.

Phase 6 livre **support, inhibition, reinforcement, decay, novelty** plus
les trois métriques canoniques. L'**affinity role/hypothesis** est un
follow-up Phase 6.5 car elle nécessite la couche typed-blackboard
(auto-élection de capabilities) qui appartient au scope Phase 3 du plan
canonique, pas encore livré (cf. Phase 5 où A2 est un placeholder
linear-repair).

## Surface ajoutée

### `core_v10/signals.py`

- `SignalKind` : `SUPPORT`, `INHIBIT`, `REINFORCE`, `NOVELTY`, `CONFIDENCE`
  (rétro-compat Phase 5 préservée) ;
- `SignalRecord` : dataclass active (`kind`, `target`, `intensity`,
  `evidence`, `half_life`, `created_at_seq`, `last_seen_seq`,
  `emit_count`) avec `to_dict / from_dict` ;
- `SignalStore` : surface mutable (`emit`, `reinforce`, `inhibit`,
  `decay`, `support_for`, `inhibit_for`, `by_kind`, `to_dict`,
  `from_records`, `from_events`) ;
- `clamp_intensity`, `signal_id_for(kind, target)` (sha256 16 hex
  déterministe).

Decay : `intensity_t = intensity_0 * 0.5 ** ((now_seq - last_seen_seq) /
half_life)` avec `half_life = 8` events par défaut. `decay()` est
idempotent (re-décaler au même seq ne change rien).

### `core_v10/signal_policy.py` (nouveau)

Politique pure feedback→signaux :

| Trigger | Effet |
|---|---|
| `feedback.failure_type=X` warning | `INHIBIT failure_type:X` intensity 0.5 |
| `feedback.failure_type=X` blocking | `INHIBIT failure_type:X` intensity 0.8 |
| `feedback.failure_type` répété | reinforce delta 0.1 |
| `feedback.anti_actions ⊃ {preserve_existing_tests}` | `INHIBIT anti:preserve_existing_tests` intensity 0.6 |
| `validation.passed=True` | `SUPPORT origin:<origin>` 0.7 + `REINFORCE kind:<kind>` 0.5 |
| signature qui échoue | `INHIBIT signature:<sha>` intensity 0.9 |
| n hypothèses actives, n>1 | `NOVELTY hypothesis_space` clamp(n/10) |

Chaque mutation produit un `PolicyEffect` (kind, target, intensity,
evidence, op, half_life, rationale) que le runner persiste comme événement
`signal.emitted` dans l'EventLog. La fonction `digest(store, top_k=3)`
retourne le top-K SUPPORT / INHIBIT / NOVELTY (utilisé par les LLM
providers en option).

### `core_v10/strategy_runner.py`

Nouvelle méthode `run_stigmergic_blackboard(...)` analogue à
`run_branching_repair` mais avec :

1. `SignalStore` créé fresh par instance (pas de cross-run pollution avant
   Phase 8) ;
2. avant verify : tri par `support_for(origin)` décroissant, drop
   signal-driven si `INHIBIT signature:<sha> ≥ 0.8` (en plus du
   `_SignatureTracker` Phase 5) ;
3. après chaque verify : `update_from_feedback(...)` ou
   `reinforce_origin(...)` selon succès, plus `inhibit_signature(...)` sur
   échec ; chaque effet émis en `signal.emitted` avec le record sérialisé ;
4. avant repair_provider : `Observation.data["stigmergic_digest"]`
   attaché (top-3 inhibitions, top-3 supports, top-3 novelties) ; le
   provider est libre de l'utiliser ou non ;
5. à la sélection finale : départage par `support_for(origin)` après
   `score.total` puis `score.quality` ; `SelectionRationale.competitors[*]`
   exposent `signal_score` ;
6. quand un signal modifie effectivement la décision : événement
   `signal.applied` avec `effect ∈ {drop, reorder, finalize_tiebreak}` et
   `kind / target / intensity / rationale`.

`StrategyResult` étendu : `signal_emitted_count`, `signal_applied_count`,
`signal_store_snapshot`. `_complete()` propage ces champs et le
`run.completed` event les inclut, garantissant la reconstructibilité.

### Invariants vérifiés

- **A4 ≡ A3 quand `SignalStore` reste cosmétique** : le test
  `test_a4_equals_a3_when_signal_store_stays_empty` (Phase 6 unit) lance
  les deux runners avec un seul candidat passant ; même `strict_success`,
  même `candidate_count`, même `dedup_skipped`, et `signal_applied_count
  == 0` (le store accumule des SUPPORT mais aucun signal ne change la
  décision avec un seul candidat).
- **Reconstructibilité depuis EventLog** : test
  `test_a4_signal_store_snapshot_is_reconstructible_from_events` confirme
  que `store_from_events(events).to_dict()` est égal au snapshot live.
- **`live==replay` parity** : `replay_summary_from_dir` produit le même
  `summary.json` (incluant `pheromone_hit_rate`, `feedback_reuse_rate`,
  `repeated_failure_suppression_total`) que celui écrit live.
- **Pas de leak A1/A2/A3** : ces bras n'utilisent ni `SignalStore` ni les
  events `signal.*` ; leur `signal_emitted_total = 0` (test
  `test_phase6_a3_vs_a4_a4_does_not_break_strict_success`).
- **Pas de dérive verifier/official_eval** : aucune modification dans
  `adapters_v10/migrationbench/verifier.py` ni dans `OfficialEvaluator`.

### `scripts/bench/telemetry.py`

`InstanceSummary` étendu : `signal_emitted_count`, `signal_applied_count`,
`pheromone_hit_rate`, `feedback_reuse_rate`,
`repeated_failure_suppression`. Les compteurs sont reconstruits depuis :

- `signal.emitted` events (incluant le `record` sérialisé) ;
- `signal.applied` events (avec `effect` et `target`).

`pheromone_hit_rate` exclut explicitement les NOVELTY events (pas
actionnables), ne compte que les `effect ∈ {drop, reorder,
finalize_tiebreak}`.

`feedback_reuse_rate` = (anti-action targets *appliqués* après ≥2
émissions) / (anti-action targets uniques émis). Si aucun anti-action ⇒
0.0.

`repeated_failure_suppression` = `repeat_failure_suppressed` (Phase 5) +
`#signal.applied[effect=drop, target=signature:*]` (Phase 6).

### `scripts/bench/harness.py`

Le dispatcher reconnaît `--strategy stigmergic_blackboard` et appelle
`StrategyRunner.run_stigmergic_blackboard`. Choix CLI étendu à
`{agentless_basic, branching_repair, stigmergic_blackboard}`.

### `scripts/bench/compare_strategies.py`

`DEFAULT_ARMS` étendu avec `A4_stigmergic_blackboard` (mêmes budgets que
A3 : `max_candidates=2, max_repair_rounds=1, max_repairs_per_candidate=2`).
Nouveau flag CLI `--arms` pour restreindre la comparaison à un
sous-ensemble (utile pour A3 vs A4 sans relancer A1/A2).

### Docker

`docker-compose.campaign.yml` ajoute deux services :

- `ablation-a3-vs-a4-smoke` : subset `smoke_5.jsonl`, image
  `migrationbench-v10-smoke` réutilisée. Clean WS avant chaque run, LLM
  providers DeepSeek activés sans digest.
- `ablation-a3-vs-a4-main30` : subset `main_30.jsonl`, mêmes paramètres.

## Ce qui ne change pas

- `adapters_v10/migrationbench/verifier.py` (8 signaux canoniques) ;
- `OfficialEvaluator` et le wrapper `external/MigrationBench/run_eval.py` ;
- contrat strict (`apply ∧ compile ∧ test ∧ class_version 61 ∧ official
  Success=True`) ;
- pistes 1+4 Phase 5 (contexte enrichi, `preserve_existing_tests` dans
  100 % des `feedback.created`) ;
- format `manifest.json / runs.jsonl / events/<inst>/eventlog.jsonl /
  hypotheses/<inst>/graph.json`.

## Validation

- ≥ 200 tests V10 verts (181 + 5 telemetry + 6 strategy + 2 compare + 3
  intégration + 12 SignalStore + 13 signal_policy = ≥ 222, vérifié
  localement à 202 puis +20 avec les nouveaux fichiers).
- `live==replay` parity ✓ sur l'intégration toy A4 (3 instances).
- `signal.emitted` et `signal.applied` events présents et lisibles dans
  l'EventLog.
- Phase 5 v2 non régressée (`tests/integration/v10/test_phase6_smoke.py`
  ne touche pas à `A1/A2/A3`).

## Suivi

- Smoke Docker MigrationBench réel : `ablation-a3-vs-a4-smoke` →
  vérification des `signal.emitted` events sur le subset
  `smoke_5.jsonl`.
- Campagne `main_30` séquentielle A3 puis A4, audit ~10/30, écriture
  `phase_06_ablation_main30.md` avec deltas vs Phase 5 v2.
- Multi-seed `{42, 7, 13}` pour la campagne mémoire finale (cf. limite
  assumée).
- Phase 6.5 : affinity role/hypothesis sur la couche typed-blackboard.
