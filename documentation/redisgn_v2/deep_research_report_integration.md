# Deep Research Report Integration

**Date:** 2026-04-27  
**Input report:** `/Users/lotfi/Downloads/deep-research-report.md`  
**Purpose:** convert the external Deep Research report into concrete decisions for the MigrationBench / V7 roadmap.

---

## 1. Executive Integration

The report confirms the current direction but raises the standard of proof.

The most important conclusion is:

```text
Proceed with MigrationBench + V6 static first; V7 later.
Freeze C3 temporarily; reintroduce mechanisms only after V7.
```

This is stricter than "build V7 immediately" and stricter than "repair C3". The next scientific move is not a more complex architecture. It is a clean, official, repository-level migration evaluation with strong baselines and a stable output contract.

---

## 2. Decisions Adopted

### Decision 1 — MigrationBench Is Primary, Not Universal

MigrationBench should be the primary benchmark for the **code migration** claim.

It should not be used as a standalone proof that the framework is generally superior across all agentic software engineering tasks.

Accepted claim:

```text
The framework is evaluated on repository-level Java migration under official execution-based scoring.
```

Rejected claim:

```text
The framework is generally superior to other agentic software engineering architectures.
```

### Decision 2 — V6 Static Migration Comes Before V7

The next valid sequence is:

1. official MigrationBench preflight;
2. minimal MigrationBench adapter;
3. strong baselines;
4. static stigmergic V6 on MigrationBench;
5. smoke 5;
6. pilot 10-20;
7. main 30;
8. only then V7 ablations.

No `v7_elastic_colony` run should be treated as publication-grade before V6 static is interpretable.

### Decision 3 — C3 Remains Frozen

C3 should not be deleted from the codebase, but it should be frozen as an integrated scientific claim.

The mechanisms may return later only as isolated arms:

- `skills_only`;
- `protocol_only`;
- `compiler_only`.

Conditions for reintroduction:

- V6 static is stable on MigrationBench;
- at least one V7 isolated mechanism has a credible signal;
- adaptation and evaluation splits are disjoint;
- cross-run persistence cannot learn from the evaluation subset.

### Decision 4 — Cross-Run Adaptation Must Be Disabled On Main Eval

For main evaluation, no cross-run adaptation should be active on the same split being evaluated.

This applies to:

- protocol persistence;
- skill promotion;
- compiler feedback;
- best-protocol selection;
- any config mutation derived from previous evaluation examples.

If cross-run mechanisms are tested, they require an explicit train/eval split:

```text
adaptation subset != evaluation subset
```

### Decision 5 — `compute_protocol_score` Is Not A Scientific Endpoint

The current scalar protocol score can remain as internal telemetry or dashboard support, but it must not decide the primary scientific result.

Reasons:

- arbitrary weights;
- domain-specific assumptions;
- risk of optimizing the evaluator;
- poor interpretability compared to official success and paired comparisons.

Primary endpoint remains:

```text
strict_success_rate = strict_success / requested_instances
```

with:

```text
strict_success =
artifact_delivered
AND patch_delivered
AND patch_applies
AND official_success
```

### Decision 6 — Agentless/Self-Debug Is Mandatory

The report strongly reinforces that `agentless_self_debug` is mandatory.

If the framework only beats weak solo baselines, the claim is fragile. The real rival is a simple, well-instrumented pipeline:

```text
localize -> patch -> build/test -> analyze failure -> repair -> validate
```

This baseline controls the possibility that orchestration overhead is unnecessary.

### Decision 7 — V7 Needs Hysteresis

Elastic agents must not spawn or retire on every tick.

The agent pool needs:

- cooldown;
- high/low thresholds;
- contention-aware reduction;
- budget pressure reduction;
- deterministic seed allocation;
- metrics for every spawn/retire reason.

Without hysteresis, V7 risks adding noise rather than intelligence.

---

## 3. Updated Benchmark Portfolio

| Benchmark | Role | Decision |
|---|---|---|
| MigrationBench selected minimal Java 8 -> 17 | Primary | Use for main thesis claim. |
| MigrationBench maximal / Java 21 | Extension | Only after minimal is stable. |
| Poly-MigrationBench | Secondary external validity | Use later, not in the first implementation wave. |
| SWE-bench | Transfer benchmark | Useful methodologically, not a migration benchmark. |
| SWE-bench Verified | Avoid as primary | Keep as literature reference only due to contamination and test-quality concerns. |
| CODEMENV | Micro-benchmark | Only for skill/API-migration micro-capabilities if source/evaluator is clear. |
| TravelPlanner | Controlled negative | Keep as limitation, not primary proof. |

---

## 4. Updated Baseline Gates

### Gate A — Before V7

Do not launch V7 ablations until all of the following are true:

- official MigrationBench eval works locally;
- `no_change` works;
- `dependency_only_script` works;
- `solo_direct` works;
- `planner_executor` works;
- `agentless_self_debug` works;
- `stigmergic_v6_static` emits valid patch artifacts;
- aggregator reports full-denominator results.

### Gate B — Before Full V7

Do not launch `v7_elastic_colony` unless at least one isolated V7 arm shows:

- higher `strict_success`; or
- better Pareto cost/success; or
- a clear reduction in failure class; or
- a mechanism-level signal tied to external outcomes.

### Gate C — Before Returning C3

Do not reintroduce skills/protocol/compiler unless:

- V7 is interpretable;
- train/eval split is explicit;
- cross-run state is isolated by subset namespace;
- success cannot be driven by evaluator-specific scalar scores.

---

## 5. V7 Design Adjustments

### Dynamic Ticks

Keep:

- `hard_max_ticks`;
- `min_ticks_before_stop`;
- full audit of stop reasons.

Add:

- `soft_tick_budget`;
- `progress_velocity`;
- `budget_pressure`;
- `critical_marker_pending`;
- `official_validation_pending`;
- `repair_recently_created`.

### Elastic Agents

Keep:

- min/max agents;
- deterministic seeds;
- active-agent telemetry.

Add:

- cooldown;
- hysteresis thresholds;
- spawn reason;
- retire reason;
- budget-aware retire;
- contention-aware reduction.

### Progressive Decomposition

The atomicity check must be the core rule:

```text
If a marker can be executed now by one bounded tool action, do not decompose it.
```

New metrics:

- `initial_dag_size`;
- `final_dag_size`;
- `markers_created_after_tick_1`;
- `emergent_decomposition_ratio`;
- `redecompose_count`;
- `marker_explosion_guard_triggered`.

### Specialization

Specialization is not proven by labels alone.

A specialist label is valid only if:

- it is stable across multiple ticks;
- the agent has repeated success on that marker/action class;
- scheduler assignments reflect the affinity;
- success or efficiency improves on compatible work.

---

## 6. Updated Threats To Validity

The final thesis write-up must explicitly include:

- single-seed limitation;
- Java/Maven ecosystem specificity;
- selected-subset bias;
- benchmark contamination risk;
- prompt overfitting risk;
- cross-run adaptation leakage;
- evaluator incompleteness;
- implementation-defined coordination metrics;
- cost comparability across models/providers;
- missing-run full-denominator handling.

---

## 7. Minimal Defensible Thesis Version

The minimal defensible version is not full V7.

It is:

```text
MigrationBench minimal Java 8 -> 17
+ official evaluator
+ strong baselines
+ V6 static stigmergic runtime
+ strict patch-centric output contract
+ paired analysis
+ failure taxonomy
+ honest negative/positive interpretation
```

This version is enough for a credible DSR evaluation even if the framework does not win.

V7 becomes the architectural improvement track, not the prerequisite for thesis validity.

---

## 8. Action Items

1. Update the master plan with the stricter claim boundary: MigrationBench proves code migration, not universal superiority.
2. Add `agentless_self_debug` as mandatory, not optional.
3. Add a no-cross-run-on-main-eval rule.
4. Demote `compute_protocol_score` to telemetry only.
5. Add hysteresis/cooldown to the elastic-agent design.
6. Add V6-before-V7 gates.
7. Keep C3 frozen until V7 has isolated evidence.
