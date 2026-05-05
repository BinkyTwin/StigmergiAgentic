# 018 Pivot V10 — Refonte from-scratch après invalidation de l'hypothèse fondatrice V3

**Date** : 2026-05-03

**Statut** : Accepté

**Contexte** : Lotfi + Claude Code + Codex (revue contradictoire)

---

## Contexte

À l'issue des campagnes V6/V7/V7.1/V7.2 sur MigrationBench main_30 et des campagnes scientifiques sur TravelPlanner (Sprint 9 complet, 307 tests passés), trois constats convergents invalident l'hypothèse fondatrice du framework V3 :

1. **La stigmergie pure ne se traduit pas en performance.** `strict_success` reste à 0–1/30 sur MigrationBench quel que soit le bras V3/V7. La littérature 2025-2026 confirme indépendamment ce constat (arXiv 2506.14496, *« LLM-Powered Swarms: A New Frontier or a Conceptual Stretch? »*, overhead 300× sans gain de qualité).
2. **La télémétrie V3 ment.** Divergence mécanique de 73 points entre `patch_applies` (90 %) et `artifact_delivery` (16,7 %) sur V7.2 (`_synthesize_best_partial_payload` passif qui copie un payload sans déclencher la chaîne de finalisation officielle). Les timeouts subprocess produisent des stubs avec compteurs à zéro alors que `markers.db` contient des dizaines de patch_hypothesis.
3. **L'apprentissage cross-run du Sprint 9 ne s'est jamais déclenché.** 0 promotion de skill et 0 application de protocole sur >1000 runs cumulés.

Une revue contradictoire a confronté deux propositions de redesign (plan Claude initial = blackboard + verifier + bench harness ; plan Codex = nouveau noyau `core_v10/` avec EventLog/HypothesisGraph en amont du blackboard, ablations A0..A6 avec stigmergie au cœur avant MCTS). Le plan canonique retenu est `documentation/redisgn_v2/plan_v10_from_scratch_rebuild.md`.

Contraintes méthodologiques :
- Le mémoire EMLV doit pouvoir documenter scientifiquement le pivot et présenter les résultats V3 comme baseline historique reproductible.
- L'identité scientifique du mémoire repose sur la stigmergie : H2 doit être au centre du dispositif d'ablation, pas en bonus.
- Aucune comparaison architecturale n'est défendable sans télémétrie reconstructible depuis une source de vérité unique et replay déterministe.

Références bibliographiques nouvelles intégrées : arXiv 2510.01285 (Blackboard MAS), arXiv 2506.14496 (Swarms LLM critique), arXiv 2407.16741 (OpenHands), arXiv 2405.15793 (SWE-agent), arXiv 2407.01489 (Agentless), arXiv 2305.16291 (Voyager), arXiv 2406.03816 (ReST-MCTS), arXiv 2505.09569 (MigrationBench), Heylighen (Stigmergy as a universal coordination mechanism II).

## Alternatives Considérées

### Alternative 1 : Continuer V7.3 / V8 par patches successifs sur V3

**Description** : Corriger le contrat best_partial de V7.2 pour activement exporter le diff, lancer `git apply --check`, invoquer l'évaluateur Maven officiel ; puis itérer sur les autres bugs (télémétrie timeout, anti-loop signature, promotion skills) sans changer l'architecture.

**Avantages** :
- ✅ Investissement minimal (semaines, pas mois).
- ✅ Préserve les acquis tests (307 passés) et la familiarité du code.
- ✅ Reproductibilité immédiate des chiffres V3 publiés.

**Inconvénients** :
- ❌ Conserve le couplage fort avec les abstractions invalidées (markers comme primitive centrale, pressure-based selection sans dépendances explicites).
- ❌ Ne résout pas les problèmes de fond (télémétrie ad-hoc reconstruite à la main, contrats d'adapters dupliqués V6/V7).
- ❌ Aucune contribution scientifique nouvelle au mémoire au-delà de « V7.3 fixe les bugs de V7.2 ».
- ❌ Risque de continuer à publier des chiffres difficilement défendables.

---

### Alternative 2 : Plan Claude initial — blackboard + verifier + bench harness, conservation V3

**Description** : Refonte conceptuelle (blackboard typé + verifier loop obligatoire + skill library Voyager-style + bench harness unifié + comparaisons externes), mais en conservant `Marker`, `MarkerStore`, `Orchestrator`, `pressure`, `decay`, `agent.py` comme fondations de la nouvelle architecture.

**Avantages** :
- ✅ Pivot scientifique pertinent (hybride blackboard + stigmergie).
- ✅ Hypothèses H1/H2/H3 testables.
- ✅ Bench harness unifié et matrice comparative externe.

**Inconvénients** :
- ❌ Risque de produire « V3 renommée avec un blackboard » : la rupture conceptuelle ne se matérialise pas dans le code.
- ❌ EventLog et HypothesisGraph absents du plan : on rejouerait le bug de télémétrie ad-hoc.
- ❌ MCTS prématuré (Phase 3) : un éventuel gain pourrait être attribué soit à la stigmergie soit à la recherche guidée, sans pouvoir trancher.
- ❌ Stigmergie en couche opt-in « bonus » : périphérise l'identité scientifique du mémoire.

---

### Alternative 3 (RETENUE) : Plan V10 from-scratch — `core_v10/` indépendant, EventLog au centre, ablations A0..A6 avec stigmergie au cœur

**Description** : Création d'une nouvelle ligne de code `core_v10/` sans dépendance vers `core/` legacy. Architecture centrée sur EventLog append-only (source de vérité unique, replay déterministe) → HypothesisGraph (lineage et dedup natif des candidats) → Blackboard typé (projection avec capability-based auto-élection) → Verifier multi-statut obligatoire → StrategyRunner pluggable. Couche stigmergique opt-in mesurée explicitement contre branching simple (A4 vs A3 = test direct de H2). MCTS retardé en A5 après mesure de la contribution stigmergique. Memory verifier-gated en A6.

V3 archivée sur `archive/v3-sprint9` (reproductible indéfiniment), Sprint 9 isolé en legacy avant suppression différée. Bench harness unifié avec telemetry recovery built-in. Comparaisons externes obligatoires (LangGraph supervisor, OpenHands-like, solo_*, planner_executor).

**Avantages** :
- ✅ Rupture architecturale matérialisée dans le code (cloison étanche).
- ✅ EventLog résout structurellement le problème de télémétrie qui ment.
- ✅ Stigmergie comme test scientifique central (A4 vs A3), pas comme bonus.
- ✅ Ordre des ablations isole proprement chaque contribution (verifier, blackboard, branching, stigmergie, search, memory).
- ✅ Compatible avec un mémoire défendable : la possibilité d'infirmation de H2 est consignée a priori.
- ✅ Comparabilité externe via baselines implémentées dans le même harness.

**Inconvénients** :
- ⚠️ Investissement lourd (plusieurs mois, séquencé en 9 phases).
- ⚠️ Risque de duplication de code entre `core/` legacy et `core_v10/` (mitigé par cloison étanche assumée).
- ⚠️ Possibilité scientifique d'infirmation de H2 (acceptée comme résultat valide).

---

## Décision

**Choix retenu** : Alternative 3 — Plan V10 from-scratch (`documentation/redisgn_v2/plan_v10_from_scratch_rebuild.md` comme plan canonique).

**Justification** :

1. **Honnêteté scientifique** : seule l'Alternative 3 résout structurellement le problème de télémétrie qui ment via l'EventLog comme source de vérité unique. Les Alternatives 1 et 2 perpétuent la reconstruction ad-hoc.
2. **Contribution mémoire** : seule l'Alternative 3 place la stigmergie au centre du dispositif expérimental (A4 vs A3 = test direct de H2). Sans cela, le mémoire perd son identité scientifique propre.
3. **Reproductibilité** : la cloison étanche `core/` legacy ↔ `core_v10/` garantit que les résultats V3 publiés restent vérifiables sur `archive/v3-sprint9` et que les résultats V10 sont produits par un dispositif explicitement nommé et distinct.
4. **Délai libre** : le user a explicitement indiqué que le délai est libre. L'investissement lourd de l'Alternative 3 est donc compatible avec les contraintes projet.
5. **Revue contradictoire** : Codex a explicitement critiqué l'Alternative 2 sur les points 1, 2 et 3 ; sa proposition (Alternative 3) a été acceptée à 6 points sur 8, les 2 points nuancés (cloison étanche au lieu de Big Bang ; Marker comme projection plutôt que cœur) ayant été intégrés dans la version retenue.

**Citation académique principale** :

> « In the blackboard architecture, there is no task assignment; instead, requests are broadcast on the blackboard, and each agent retains full autonomy to decide whether to participate in solving the task. Results show that the blackboard architecture substantially outperforms strong baselines, achieving 13-57% relative improvements in end-to-end success. »
> — *LLM-based Multi-Agent Blackboard System for Information Discovery in Data Science*, arXiv 2510.01285

> « LLM-powered Boids simulation required roughly 300x more computation time than its classical counterpart [...] LLM-powered swarms can emulate swarm-like dynamics, but they are constrained by substantial computational overhead. »
> — *LLM-Powered Swarms: A New Frontier or a Conceptual Stretch?*, arXiv 2506.14496

---

## Conséquences

### Positives
- ✅ Le mémoire peut documenter scientifiquement le pivot avec un dispositif expérimental défendable (H1/H2/H3/H4 testables, ablation ladder A0..A6, comparaisons externes).
- ✅ La télémétrie devient mécaniquement honnête (EventLog source de vérité, replay déterministe, séparation `local_valid` / `official_valid` / `strict_success` / `partial_diagnostic`).
- ✅ La stigmergie est repromue au cœur identitaire de la contribution (test direct A4 vs A3).
- ✅ Comparabilité externe via LangGraph / OpenHands-like / solo_* / planner_executor implémentés dans le même harness.
- ✅ V3 reste reproductible indéfiniment sur `archive/v3-sprint9`.

### Négatives
- ⚠️ Investissement lourd : 9 phases, plusieurs mois (mitigation : chaque phase est livrable indépendamment, mémoire rédactible dès Phase 6).
- ⚠️ Risque scientifique d'infirmation de H2 (mitigation : trame de discussion préparée a priori, le résultat négatif reste une contribution valide).
- ⚠️ Duplication potentielle de code `core/` ↔ `core_v10/` (mitigation : cloison étanche assumée, recopie/adaptation explicite des maths de decay/pressure dans `stigmergic_layer.py`).
- ⚠️ Coût LLM cumulé sur 9 phases d'évaluation (mitigation : caps depth/width/budget USD strict, fallback sur best already-verified).

### Impacts sur le Code
- Nouveaux modules : `core_v10/{contracts,event_log,hypothesis_graph,blackboard,verifier,strategy_runner,signals,selectors,budgets,replay}.py`, `core_v10/feedback/`, `core_v10/strategies/`, `core_v10/memory/`, `core_v10/observability/`.
- Nouveaux harness : `scripts/bench/{harness,telemetry,artifacts,docker,aggregate,baselines}.py`.
- Nouveaux adapters : `adapters_v10/{base,fake,migrationbench,travelplanner,assistant}.py`.
- Suppressions différées (Phase 9) : `core/schemas.py:ProtocolSpec`, `llm/prompts.py:SYSTEM_PROTOCOL_COMPILER`, `pheromones/*_protocols.db`, `pheromones/*_skills.db`, configs Sprint 9, scripts dispersés.
- Préservation : `core/marker.py`, `core/marker_store.py`, `core/orchestrator.py`, `core/agent.py`, `core/environment.py`, `core/decay.py`, `core/pressure.py`, `core/reinforcement.py`, `core/guardrails.py`, `core/audit.py`, `llm/client.py` restent dans `core/` legacy intacts.

### Impacts sur la Méthodologie
- Influence sur les tests : nouveau corpus `tests/v10/`, indépendant de `tests/unit/` legacy. Tests determinisme replay obligatoires.
- Influence sur les métriques : statuts `local_valid` / `official_valid` / `strict_success` / `partial_diagnostic` séparés, tous reconstructibles depuis l'EventLog.
- Influence sur la thèse : pivot intellectuel formalisé (stigmergie pure → hybride mesurable), question de recherche reformulée, hypothèses H1/H2/H3/H4 documentées.

---

## Validation

**Critères de succès** :
1. [ ] `core_v10/` peut exécuter un fake adapter sans importer `core/` legacy.
2. [ ] Un run V10 est rejouable depuis l'EventLog avec le même `VerifierReport` final.
3. [ ] Toutes les métriques V10 sont reconstructibles depuis EventLog + artifacts.
4. [ ] Aucune divergence > 5pp inexplicable entre `patch_applies` et `strict_success`.
5. [ ] Comparaison A4 vs A3 sur MigrationBench main_30 documentée (apport stigmergique mesurable, ou résultat négatif analysé).
6. [ ] Matrice comparative externe complète (V10 A1..A6 + LangGraph + OpenHands-like + solo_* + planner_executor) sur MigrationBench main_30 et TravelPlanner C3.

**Tests à effectuer** :
```bash
# Phase 1 — déterminisme replay
uv run pytest tests/v10/test_event_log.py tests/v10/test_replay_determinism.py -q

# Phase 4 — verifier MigrationBench officiel
uv run python -m scripts.bench.harness \
  --adapter migrationbench \
  --strategy v10_a1_verifier_loop \
  --subset fixtures/migrationbench/subsets/smoke_5.jsonl \
  --model deepseek-v4-flash \
  --out-dir campaign_results/v10/smoke

# Phase 6 — H2 testée
uv run python -m scripts.bench.harness \
  --adapter migrationbench \
  --strategy v10_a4_stigmergic_blackboard \
  --subset fixtures/migrationbench/subsets/main_30.jsonl \
  --out-dir campaign_results/v10/main30_a4
```

**Résultat après implémentation** : *(à remplir après Phase 9)*

---

## Références

- Plan canonique V10 : `documentation/redisgn_v2/plan_v10_from_scratch_rebuild.md`
- Documentation mémoire : `documentation/redisgn_v2/pivot_v10_documentation_memoire.md`
- Diagnostic V7 : `documentation/redisgn_v2/v7_1_diagnostic_loop.md`
- ADR Sprint 9 : `documentation/decisions/20260421-sprint9-full-implementation-persistent-skills-protocols-and-cross-run-coordination.md` (déprécié par cet ADR-018)
- arXiv 2510.01285 — *LLM-based Multi-Agent Blackboard System for Information Discovery in Data Science*
- arXiv 2506.14496 — *LLM-Powered Swarms: A New Frontier or a Conceptual Stretch?*
- arXiv 2405.15793 — *SWE-agent: Agent-Computer Interfaces Enable Automated Software Engineering*
- arXiv 2407.01489 — *Agentless: Demystifying LLM-based Software Engineering Agents*
- arXiv 2407.16741 — *OpenHands: An Open Platform for AI Software Developers as Generalist Agents*
- arXiv 2305.16291 — *Voyager: An Open-Ended Embodied Agent with Large Language Models*
- arXiv 2406.03816 — *ReST-MCTS\*: LLM Self-Training via Process Reward Guided Tree Search*
- arXiv 2505.09569 — *MigrationBench: Repository-Level Code Migration Benchmark from Java 8*
- Heylighen, *Stigmergy as a universal coordination mechanism II: Varieties and evolution*, Cognitive Systems Research

---

## Métadonnées

- **ADR créé par** : Lotfi + Claude Code (avec revue contradictoire Codex)
- **ADR validé par** : Lotfi (2026-05-03)
- **Version** : 1.0
- **Dernière modification** : 2026-05-03
