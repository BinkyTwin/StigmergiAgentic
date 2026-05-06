# Phase 7 V11 — Stigmergic Medium Kernel MVP

**Statut** : implémenté sur la branche `codex/v11-stigmergic-medium-kernel`.

## Périmètre livré

Cette phase transforme la couche A4 V10 en un noyau V11 causal minimal. V10
reste le socle de vérification, d'audit et de replay ; V11 ajoute le médium
actif :

```text
feedback vérifié
-> signal.emitted
-> affordance.created
-> signal.read
-> worker.selected / worker.activated
-> decision.influenced
-> trajectory.diverged
-> worker.output
-> candidate.created
-> validation.completed
```

## Surface ajoutée

- `core_v10/stigmergy/records.py` : dataclasses V11 (`Affordance`,
  `SignalRead`, `DecisionInfluence`, `TrajectoryDivergence`,
  `WorkerSpec`, `WorkerActivation`, `OperatorInvocation`).
- `core_v10/stigmergy/medium.py` : `StigmergicMediumKernel`, projection live
  reconstruisible depuis EventLog.
- `core_v10/stigmergy/affordances.py` : policy `FeedbackDigest ->
  Affordance` pour `answer_mismatch`, `replacement_count_too_low`,
  `compile_error`, `dependency_resolution_error`, `official_eval_failed`,
  `preserve_existing_tests`.
- `core_v10/stigmergy/scheduler.py` : scheduler déterministe avec scoring
  capability/support/failure relevance/affinity/novelty/inhibition/cost/risk.
- `core_v10/operators/text_operator.py` : `ExactReplaceText` guardé.
- `adapters_v10/migrationbench/operators/maven.py` : operators Maven
  exact-match pour Java 17, compiler/surefire plugins et JAXB.
- `StrategyRunner.run_stigmergic_scheduler()` : bras B5.
- `StrategyRunner.run_operator_search()` : bras B6.
- `scripts/bench/compare_strategies.py --ladder v11` : ladder B2/B5/B6.
- `scripts/v11/run_v11_smoke.py` : automation no-LLM avec replay parity.
- `docker-compose.campaign.yml` : service `v11-smoke`.

## Télémétrie

`scripts/bench/telemetry.py` reconstruit désormais les métriques V11 depuis
les events, sans champ live non rejouable :

- `signal_read_total`, `unique_signal_read_total`, `signal_read_rate` ;
- `decision_influenced_total`, `decision_influence_rate` ;
- `trajectory_divergence_total`, `trajectory_divergence_rate` ;
- `affordance_created_total`, `affordance_consumed_total`,
  `unused_affordance_rate` ;
- `unused_signal_rate`, `cosmetic_signal_rate`,
  `stigmergic_causality_rate`, `signal_harm_rate` ;
- `worker_activated_total` ;
- `operator_invoked_total`, `operator_applied_total`,
  `operator_failed_total`.

## Validation

Tests et smokes exécutés :

```bash
uv run pytest tests/unit/v11 tests/integration/v11/test_toy_patch_repair.py -q
# 9 passed

uv run pytest tests/unit/v10/test_signal_store.py tests/unit/v10/test_signal_policy.py \
  tests/unit/v10/test_strategy_runner_phase6.py \
  tests/unit/v10/bench/test_telemetry_phase6.py \
  tests/unit/v10/bench/test_compare_strategies_phase6.py \
  tests/integration/v10/test_phase6_smoke.py -q
# 40 passed

uv run pytest tests/unit/v10/test_import_boundaries.py tests/unit/v10/test_strategy_runner.py \
  tests/unit/v10/bench/test_harness_toy.py \
  tests/unit/v10/bench/test_harness_migrationbench.py \
  tests/unit/v10/bench/test_compare_strategies.py \
  tests/unit/v10/migrationbench/test_adapter.py \
  tests/unit/v10/migrationbench/test_workspace.py -q
# 43 passed

uv run python -m scripts.v11.run_v11_smoke --out-dir /tmp/v11_smoke_script
# {"status": "ok", ...}

docker compose -f docker-compose.campaign.yml run --rm v11-smoke
# {"status": "ok", "summary_path": "campaign_results/v11/smoke/v11_smoke_summary.json"}
```

## Résultat contrôlé

Sur toy repair avec premier candidat forcé faux :

- B2 (`branching_repair`) réussit via repair provider mais n'émet aucun
  événement causal V11.
- B5 (`stigmergic_scheduler`) produit `signal.read`,
  `worker.activated`, `decision.influenced`, `trajectory.diverged`.
- B6 (`operator_search`) produit la même chaîne causale plus
  `operator.invoked` et `operator.applied`, et sélectionne le candidat
  operator (`*-exact-answer`).
- `summary.json == replay_summary_from_dir(...).to_dict()` pour chaque bras.

## Limites assumées

- B3/B4 passifs ne sont pas encore des bras dédiés ; le MVP compare B2/B5/B6.
- B7 memory verifier-gated est reporté pour garder un protocole train/eval
  propre avec baselines `memory_disabled`, `memory_correct`,
  `memory_shuffled`.
- Le smoke MigrationBench réel doit rester contrôlé avant tout `main_30` :
  la chaîne V11 est validée mécaniquement sur toy et les operators Maven sont
  unit-testés, mais le gain benchmark n'est pas encore revendiqué.

## Commandes utiles

```bash
uv run python -m scripts.v11.run_v11_smoke \
  --out-dir campaign_results/v11/smoke

docker compose -f docker-compose.campaign.yml run --rm v11-smoke

uv run python -m scripts.bench.compare_strategies \
  --adapter toy \
  --subset /path/to/subset.jsonl \
  --out-dir campaign_results/v11/toy_compare \
  --ladder v11 \
  --extras '{"out_dir":"campaign_results/v11/toy_compare","toy_initial_wrong":true}'
```
