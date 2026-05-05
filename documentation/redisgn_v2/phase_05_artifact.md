# Phase 5 V10 — BranchingRepair A3 (artifact)

**Date de livraison** : 2026-05-04

**Statut** : Livrée. Suite V10 totale **136 passed** (était 126 avant Phase 5).

Ce document récapitule l'état de Phase 5 V10 : livrables, contrats publics
nouveaux, garde-fous, limites connues, et preuves de validation. Il complète
l'ADR-019 (`documentation/decisions/20260504-phase5-a3-branching-repair.md`)
et le plan canonique
`documentation/redisgn_v2/plan_v10_from_scratch_rebuild.md` §Phase 5.

---

## 1. Scope Phase 5

Plan canonique §Phase 5 — livrables exigés :

| Livrable | Statut | Référence |
|---|---|---|
| Strategy `branching_repair` | ✅ (déjà Phase 4, durci ici) | `core_v10/strategy_runner.py:run_branching_repair` |
| Branch isolation | ✅ (Phase 4) | `adapters_v10/migrationbench/workspace.py:branch_workspace` |
| Candidate signature dedup | ✅ Phase 5 | `_SignatureTracker` + events `candidate.deduped` |
| Repeated failure suppression | ✅ Phase 5 | `_SignatureTracker.failure_count` + events `candidate.repeat_failure_suppressed` |
| Best candidate selector | ✅ Phase 5 (durci) | `SelectionRationale` + event `selection.completed` |
| Comparaison A1/A2/A3 sur smoke | ✅ Phase 5 | `scripts/bench/compare_strategies.py` |
| Sélection explicable par preuves | ✅ Phase 5 | `SelectionRationale.competitors` (ordonné par score) |

Note A2 : Phase 3 (`typed_blackboard`) n'est pas finalisée (capability
auto-election, knowledge sources). Le bras A2 retenu pour la comparaison Phase 5
est un **placeholder linear-repair** (`branching_repair` avec
`max_candidates=1`, `max_repair_rounds=1`, `max_repairs_per_candidate=1`),
suffisant pour isoler la contribution combinatoire de A3 (branching + dedup +
suppression). La couche typed-blackboard reste un follow-up Phase 3.

---

## 2. Surface publique nouvelle

### 2.1 `core_v10.strategy_runner`

```python
@dataclass(frozen=True)
class SelectionRationale:
    selected_hypothesis_id: str | None
    reason: str  # "strict_success" | "fallback_validated_finalization"
                 # | "no_validated_candidate" | "repair_exhausted"
                 # | "no_candidate_generated" | "all_candidates_invalid"
    selected_score: float | None
    competitors: tuple[JsonDict, ...]   # par compétiteur : hypothesis_id, score, status, passed
```

`StrategyResult` gagne :

- `selection_rationale: SelectionRationale | None`
- `dedup_skipped: int` (compteur intra-run)
- `repeat_failure_suppressed: int` (compteur intra-run)

Nouveaux events EventLog (toujours par strategy_runner) :

- `candidate.deduped` — payload : `candidate_id, signature, duplicate_of, parent_id, origin`
- `candidate.repeat_failure_suppressed` — payload : `candidate_id, signature, parent_id, previous_failures, origin`
- `selection.completed` — payload : `rationale=<SelectionRationale.to_dict()>`,
  `hypothesis_id=<selected_id>`

`run.completed` payload étendu : `dedup_skipped`, `repeat_failure_suppressed`.

### 2.2 `scripts.bench.telemetry`

`InstanceSummary` gagne `dedup_skipped`, `repeat_failure_suppressed`,
`selection_rationale: dict | None`.

`Summary` gagne `dedup_skipped_total`, `repeat_failure_suppressed_total`.

`build_summary` reconstruit ces compteurs **soit** depuis `run.completed`
(production), **soit** en comptant les events `candidate.deduped` /
`candidate.repeat_failure_suppressed` (replay legacy) — fallback déterministe
qui préserve `live==replay` même sur des campagnes pré-Phase 5.

### 2.3 `scripts.bench.compare_strategies`

Nouveau module. CLI :

```bash
python -m scripts.bench.compare_strategies \
  --adapter migrationbench \
  --subset fixtures/migrationbench/subsets/smoke_5.jsonl \
  --out-dir campaign_results/v10/migrationbench_smoke_compare \
  --extras '{"out_dir": "campaign_results/v10/migrationbench_smoke_compare"}'
```

Sorties :

- `campaign_results/.../A1_agentless_basic/{manifest,events,hypotheses,artifacts,runs.jsonl,summary.json}`
- `campaign_results/.../A2_linear_repair/...`
- `campaign_results/.../A3_branching_repair/...`
- `campaign_results/.../comparison.json` — payloads par bras avec
  `strict_success_count`, `dedup_skipped_total`,
  `repeat_failure_suppressed_total`, `instances[*].selection_rationale`.

Bras par défaut (`DEFAULT_ARMS`) :

| arm_id | strategy | max_candidates | max_repair_rounds | max_repairs_per_candidate |
|---|---|---|---|---|
| `A1_agentless_basic` | `agentless_basic` | 1 | 0 | 1 |
| `A2_linear_repair` | `branching_repair` | 1 | 1 | 1 |
| `A3_branching_repair` | `branching_repair` | 2 | 1 | 2 |

L'utilisateur peut passer une liste `arms=[AblationArm(...)]` programmatique
(test `test_compare_strategies_accepts_custom_arm_list`).

---

## 3. Garde-fous (invariants Phase 5)

1. **EventLog seul source de vérité.** Les compteurs `dedup_skipped_total` et
   `repeat_failure_suppressed_total` sont **toujours** reconstructibles depuis
   les events `candidate.deduped` / `candidate.repeat_failure_suppressed`
   (test : `test_compare_strategies_each_arm_has_live_replay_parity`).

2. **`live==replay` préservé.** Tests Phase 4 toujours verts ; nouveau test
   d'intégration Phase 5 vérifie la parité par bras d'ablation.

3. **Signature stable.** `_SignatureTracker.signature` = sha256 (16 hex) de
   `{kind, payload}` canonicalisé via `to_jsonable + sort_keys + separators=(",", ":")`.
   Ignore explicitement `metadata` pour rester déterministe — un adaptateur qui
   doit différencier des candidats portant le même payload doit le faire via
   `payload`.

4. **Repeat failure ≠ dedup.** Un candidat de réparation dont la signature a
   **déjà échoué** (failure_count ≥ 1) est suppressé en priorité, même si
   l'événement de "première occurrence" n'est pas un strict duplicate. Cela
   couvre le cas où le LLM répare en re-proposant la même solution.

5. **Selector explicable.** `SelectionRationale.competitors` est triée par
   `(score.total desc, score.quality desc, hypothesis_id asc)` (même clé que
   `_validated_nodes_in_priority_order`). La justification "pourquoi X et pas
   Y" est lisible directement sans rejouer le run.

6. **Aucune fuite legacy.** Le test `test_import_boundaries.py` (déjà en place
   Phase 4) garantit qu'aucun module `core_v10/`, `adapters_v10/`,
   `scripts/bench/` ne réimporte `core/` ou `adapters/` legacy.

---

## 4. Validation

```bash
.venv/bin/python -m pytest tests/unit/v10/ tests/integration/v10/ -q
# 136 passed in ~8s
```

Détail des nouveaux tests Phase 5 :

- `tests/unit/v10/test_strategy_runner_phase5.py` (6 tests) :
  - signature tracker équivalence/distinction,
  - dedup intra-run sur candidats initiaux dupliqués,
  - suppression cross-rounds d'une réparation re-proposant la signature
    échouée,
  - rationale enrichi avec compétiteurs (low-quality vs high-quality),
  - rationale `no_validated_candidate` quand tous les candidats échouent.

- `tests/unit/v10/bench/test_compare_strategies.py` (4 tests) :
  - 3 bras exécutés, `comparison.json` écrit, par-bras campaign tree complet,
  - parité `live==replay` par bras,
  - bras A3 expose `dedup_skipped_total`, `selection_rationale` non nul,
  - liste de bras custom respectée.

Replay parity sur smoke réel pré-Phase 5
(`campaign_results/v10/migrationbench_smoke`) : `strict_success_count`,
`by_signal`, `instances` reconstructibles à l'identique ; nouveaux compteurs
à 0 (rien n'a été dédupé). C'est le comportement attendu pour les anciennes
campagnes.

---

## 5. Limites connues / follow-ups

- **A2 placeholder.** Voir §1. Phase 3 finalisation requise pour comparer
  l'effet typed-blackboard isolément.
- **Signature ignore `metadata`.** Si un futur besoin l'exige, exposer un
  hook `signature_fn` configurable côté `StrategyConfig`.
- **Sélection sur run.completed payload.** Les compteurs sont émis à la fois
  dans `run.completed` (rapide) et reconstructibles depuis les events
  individuels (replay). Le test telemetry vérifie que les deux chemins
  convergent.
- **Smoke réel post-Phase 5.** Le smoke réel de Phase 4
  (`campaign_results/v10/migrationbench_smoke`) a été exécuté avant Phase 5 ;
  les nouveaux compteurs y valent 0. Re-run en docker via
  `migrationbench-v10-smoke` recompose un summary qui inclut les nouveaux
  compteurs.
- **Comparaison MigrationBench main_30.** DoD du plan exige aussi main_30 ;
  c'est un travail de campagne (Docker + budget LLM) qui dépasse l'engineering
  Phase 5. Le harness `scripts/bench/compare_strategies.py` est prêt à être
  invoqué sur `fixtures/migrationbench/subsets/main_30.jsonl` via le service
  Docker.

---

## 6. Pointeurs

- ADR : `documentation/decisions/20260504-phase5-a3-branching-repair.md`
- Plan canonique : `documentation/redisgn_v2/plan_v10_from_scratch_rebuild.md`
- Phase 4 artifact : `documentation/redisgn_v2/sprint_09_artifact.md`
  (à compléter ultérieurement avec un `phase_04_artifact.md` dédié).
- Smoke réel Phase 4 : `campaign_results/v10/migrationbench_smoke/`
- Tests : `tests/unit/v10/test_strategy_runner_phase5.py`,
  `tests/unit/v10/bench/test_compare_strategies.py`.
