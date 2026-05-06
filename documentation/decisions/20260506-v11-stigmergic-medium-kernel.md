# 2026-05-06 — V11 Stigmergic Medium Kernel

**Statut** : accepté, incrément MVP implémenté.

## Contexte

La Phase 6 V10 a rendu les signaux visibles (`signal.emitted`) et parfois
appliqués (`signal.applied`), mais le résultat A3 vs A4 a montré que la couche
stigmergique restait encore trop faible causalement : les signaux existaient
plus souvent qu'ils ne changeaient les décisions.

Le plan V11 (`documentation/redisgn_v2/plan_v11_stigmergic_medium_kernel.md`)
reformule donc la contribution autour d'un médium actif :

```text
verified feedback -> signal -> affordance -> signal.read
-> worker activation -> decision.influenced -> trajectory.diverged
-> candidate/operator -> verifier
```

## Décision

Créer une couche V11 au-dessus de `core_v10/`, sans modifier le legacy `core/`,
et garder l'EventLog comme source de vérité unique.

Surface livrée :

- `core_v10/stigmergy/records.py`, `medium.py`, `affordances.py`,
  `scheduler.py`, `events.py` ;
- `core_v10/operators/text_operator.py` avec `ExactReplaceText` guardé ;
- `adapters_v10/migrationbench/operators/maven.py` avec operators Maven
  exact-match (`MavenSetCompilerRelease`, compiler/surefire plugin upgrades,
  JAXB dependency insertion) ;
- `StrategyRunner.run_stigmergic_scheduler()` pour B5 ;
- `StrategyRunner.run_operator_search()` pour B6 ;
- `scripts/bench/compare_strategies.py --ladder v11` avec B2/B5/B6 ;
- `scripts/v11/run_v11_smoke.py` et service Docker `v11-smoke` ;
- télémétrie causalement replayable : `signal_read_total`,
  `decision_influenced_total`, `trajectory_divergence_total`,
  `affordance_*`, `worker_*`, `operator_*`,
  `stigmergic_causality_rate`, `unused_signal_rate`,
  `unused_affordance_rate`, `cosmetic_signal_rate`.

## Règles retenues

1. `signal.emitted` seul ne prouve rien : la chaîne doit inclure au minimum
   `signal.read`, `worker.activated`, `decision.influenced` et
   `trajectory.diverged`.
2. Les affordances sont les actions possibles du médium. Elles sont créées à
   partir de `FeedbackDigest` + signaux actifs, puis consommées par le worker.
3. B5 active des workers via affordances + signaux. B6 tente d'abord des
   operators typés, puis retombe sur le repair provider si aucun operator
   applicable n'existe.
4. Les operators de remplacement textuel ne peuvent émettre un edit que si
   l'ancien span est prouvé présent dans le texte courant.
5. La mémoire V11/B7 reste explicitement hors scope de cet incrément : elle
   nécessite un protocole train/eval/snapshot/shuffle séparé.

## Alternatives rejetées

- Continuer à enrichir A4 uniquement avec plus de `signal.applied` : trop
  proche de la télémétrie, pas assez causal.
- Mettre MCTS/search avant affordances/workers/operators : le search pourrait
  masquer l'effet stigmergique central.
- Ajouter une mémoire cross-run immédiatement : sans B5/B6 causal, elle serait
  un cache de prompts difficile à attribuer.
- Générer des patchs libres comme voie principale de B6 : les échecs
  `replacement_count_too_low` exigent des operators exact-match guardés.

## Validation

Commandes exécutées :

```bash
uv run python -m py_compile core_v10/stigmergy/*.py core_v10/operators/*.py \
  adapters_v10/migrationbench/operators/*.py core_v10/strategy_runner.py \
  scripts/bench/harness.py scripts/bench/telemetry.py \
  scripts/bench/compare_strategies.py scripts/bench/providers.py scripts/v11/*.py

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
# status ok, live==replay checked

docker compose -f docker-compose.campaign.yml run --rm v11-smoke
# status ok, summary_path=campaign_results/v11/smoke/v11_smoke_summary.json
```

Toy V11 smoke result : B2 has no causal stigmergic events; B5/B6 have
positive `signal_read_total`, `decision_influenced_total`,
`trajectory_divergence_total`; B6 invokes and applies operators and preserves
strict success on the controlled toy repair.

## Conséquences

V11 can now be evaluated as a causal medium, not as signal logging. The next
work should run controlled MigrationBench smokes before any `main_30` claim,
then add B7 memory only with `memory_disabled`, `memory_correct`, and
`memory_shuffled` baselines.
