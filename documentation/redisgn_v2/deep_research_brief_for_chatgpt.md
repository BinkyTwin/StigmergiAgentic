# Deep Research Brief — StigmergiAgentic V7 / MigrationBench

**Date:** 2026-04-27  
**Purpose:** context packet for an external ChatGPT Deep Research run with GitHub repository access.  
**Repository:** `BinkyTwin/StigmergiAgentic`  
**Primary research goal:** improve the scientific plan and technical architecture for evaluating StigmergiAgentic on code migration, after TravelPlanner failed to justify the framework's added complexity.

---

## 1. What To Read First

Please inspect these repository files in this order:

1. `documentation/redisgn_v2/plan_migrationbench_scientific_campaign.md`
   - This is the current master plan.
   - It defines the move from TravelPlanner to MigrationBench, the V7 Elastic Colony proposal, the evaluation protocol, metrics, baselines, and roadmap.

2. `core/orchestrator.py`
   - Current tick loop.
   - Fixed `max_ticks`, idle stop, recovery controller, `dynamic_idle_limit`, parallel execution, lock resolution, feedback loop.

3. `core/agent.py`
   - Current homogeneous agent.
   - Local memory, local sensing, affinity profile, action selection, skill recall, productive-line stickiness.

4. `tools/decompose.py`
   - Current decomposition tool.
   - Uses `max_depth`, `max_subtasks`, optional LLM decomposition, fallback subtasks.

5. `core/emergence.py`
   - Current emergence metrics and adaptive feedback.
   - Includes specialization entropy, colony specialization, collaboration density, lock contention, parallel utilization, pressure entropy, and feedback adaptations.

6. `config/default.yaml`
   - Current global configuration contract.
   - Note fixed `agents.num_agents`, fixed `orchestrator.max_ticks`, and `decompose.max_depth`.

7. `adapters/travelplanner/`
   - Previous benchmark adapter. Useful as a cautionary example, not as the future main benchmark.

8. `scripts/run_travelplanner_framework_benchmark.py`
   - Existing campaign runner pattern and failure-handling style.

9. `scripts/aggregate_campaign_comparison.py`
   - Existing result aggregation pattern.

10. `documentation/redisgn_v2/case_study_codemigration_protocol.md`
    - Earlier migration-code protocol draft, less up to date than the master plan but still useful background.

If some files are not present on the remote branch, use the master plan as the source of truth and explicitly flag any missing repository context.

---

## 2. Current Honest Diagnosis

TravelPlanner is no longer considered the main scientific proof.

Observed lessons:

- The framework can run and deliver artifacts, but it did not clearly beat strong solo baselines on TravelPlanner.
- It consumed more tokens and time than solo baselines.
- TravelPlanner exposes limited coordination surface: much of the benchmark is won or lost by producing one final constrained itinerary.
- The C3 attempt mixed too many mechanisms at once: skills, protocols, compiler, scoring changes, namespace persistence, and cross-run behavior.
- Several C3 defects broke attribution: fragile scoring, empty-artifact false positives, poor skill injection, brittle namespace derivation, and weak compiler operationality.
- Conclusion: use TravelPlanner as a controlled limiting/negative case, not as the primary evidence of stigmergic orchestration value.

The next primary evaluation target is repository-level code migration, especially MigrationBench.

---

## 3. Current Architecture Summary

StigmergiAgentic currently has:

- SQLite marker store and audit log.
- Generic markers with state, target, payload, intensity, inhibition, locks, retries, history.
- Tick-based orchestrator.
- Multiple homogeneous agents created at startup.
- Tool registry.
- ACO-like pressure-based action selection.
- Lock arbitration.
- Marker decay and reinforcement.
- Local agent memory.
- Local sensing and affinity profiles.
- Recovery controller and targeted repair markers.
- Emergence metrics.
- YAML-driven runtime controls.

But the framework is still too rigid:

- `num_agents` is fixed before seeing the task graph.
- `max_ticks` is fixed before knowing the real effort required.
- `DecomposeTool` can create an initial DAG that risks looking like planner-executor with extra overhead.
- Agent specialization exists only as local affinity traces, not as visible, measurable, stable roles.
- C3 mechanisms were added before the core runtime could adapt population, time budget, and task granularity.

---

## 4. Proposed Direction

The current proposal is to create a new track:

```text
V6 static migration baseline
  -> reliable MigrationBench adapter
  -> strong baselines
  -> official execution-based scoring
  -> honest static result

V7 Elastic Colony
  -> dynamic tick budget
  -> elastic agent pool
  -> progressive/atomic decomposition
  -> visible emergent specialization
  -> isolated ablations before any full combination

Only later:
  -> reintroduce C3 mechanisms as isolated skills/protocol/compiler ablations
```

Integrated C3 is frozen for now. The ideas are not discarded, but they should not be the next primary architecture claim.

---

## 5. Core Research Questions

Please answer these critically:

1. Is MigrationBench the right primary benchmark for this framework?
2. What other benchmarks should be primary, secondary, or avoided?
3. What baselines are scientifically mandatory?
4. How should V7 Elastic Colony be designed so it is not just "planner-executor with extra overhead"?
5. How can dynamic ticks, elastic agents, progressive decomposition, and specialization be measured separately?
6. Under what conditions should skills/protocol/compiler return?
7. What would make this evaluation publishable or at least thesis-grade?
8. What methodological risks could invalidate the results?
9. What is the minimum viable implementation that is scientifically defensible?
10. What would a stronger post-memoir version look like?

---

## 6. Benchmark Candidates To Compare

Please compare at least:

- MigrationBench / JavaMigration.
- Poly-MigrationBench.
- SWE-bench.
- SWE-bench Verified.
- CODEMENV.
- Any newer or stronger code-migration or software-engineering-agent benchmark.

For each benchmark, report:

- Task definition.
- Dataset size.
- Language / ecosystem.
- Evaluation mechanism.
- Strengths.
- Weaknesses.
- Contamination risks.
- Suitability for stigmergic/multi-agent evaluation.
- Budget feasibility.
- Recommendation: primary, secondary, micro-benchmark, or avoid.

---

## 7. Frameworks And Papers To Learn From

Please include relevant lessons from:

- Agentless.
- SWE-agent.
- AutoCodeRover.
- OpenHands.
- MetaGPT.
- Magis / Moatless, if relevant.
- AutoGen / CAMEL, if relevant.
- Reflexion / Voyager, if relevant for self-improvement.
- Blackboard systems, actor systems, swarm intelligence, ACO, and stigmergic coordination literature where relevant.

For each relevant system:

- Architecture.
- Coordination style.
- Memory or self-improvement mechanism.
- Benchmarks used.
- Metrics used.
- What StigmergiAgentic should copy.
- What StigmergiAgentic should avoid.

---

## 8. Required Baseline Philosophy

The evaluation must not beat weak strawmen only.

Baselines under consideration:

- `no_change`.
- `dependency_only_script`.
- `solo_direct`.
- `solo_cot`.
- `planner_executor`.
- `agentless_self_debug` or SD-Feedback-like baseline.
- `langgraph_supervisor` or graph supervisor.
- `stigmergic_v6_static`.
- `v7_dynamic_ticks`.
- `v7_elastic_agents`.
- `v7_progressive_decompose`.
- `v7_specialization`.
- `v7_elastic_colony`.
- Later only: `skills_only`, `protocol_only`, `compiler_only`.

Please classify each baseline as:

- mandatory;
- recommended;
- optional;
- not worth the cost.

Also explain what each baseline controls scientifically.

---

## 9. V7 Elastic Colony Design Questions

### Dynamic Tick Budget

Please propose:

- YAML config.
- Algorithm.
- Stop/continue conditions.
- Safety hard cap.
- Budget pressure handling.
- How to avoid infinite loops.
- Metrics.
- Unit tests.

### Elastic Agent Pool

Please propose:

- YAML config.
- Spawn strategy.
- Retire strategy.
- Interaction with unblocked markers.
- Interaction with lock contention.
- Interaction with parallel utilization.
- Interaction with cost and token budget.
- How to preserve deterministic seeds.
- How to avoid over-spawning.
- Metrics.
- Unit tests.

### Progressive Decomposition

Please propose:

- Atomicity contract.
- When to decompose.
- When to redecompose.
- How to avoid full DAG at tick 1.
- How to measure emergent graph construction.
- How to prevent marker explosion.
- Unit tests.

### Emergent Specialization

Please propose:

- How to detect specialization.
- How to label it without imposing manual roles.
- How to use it in scheduling.
- How to distinguish real specialization from noise.
- How to measure success delta.
- How to test transfer across repositories.
- Unit tests.

---

## 10. Output Contract Requirements

Every run must produce strict comparable outputs:

```json
{
  "instance_id": "owner__repo-id",
  "framework": "v7_elastic_agents",
  "provider": "openrouter",
  "model": "google/gemma-4-31b-it",
  "seed": 42,
  "artifact_delivered": true,
  "patch_delivered": true,
  "patch_applies": true,
  "official_success": false,
  "strict_success": false,
  "failure_reason": "tests_failed",
  "migration_mode": "minimal",
  "target_java": 17,
  "build_success": true,
  "test_success": false,
  "compiled_major_version_ok": true,
  "test_count_non_decreasing": true,
  "tokens_total": 12345,
  "cost_total_usd": 0.0123,
  "runtime_seconds": 530.2,
  "repair_cycles": 2,
  "files_modified_count": 3,
  "patch_lines_added": 21,
  "patch_lines_deleted": 8,
  "markers_created": 44,
  "markers_created_after_tick_1": 21,
  "emergent_decomposition_ratio": 0.477,
  "coordination_overhead": 11,
  "active_agent_count_by_tick": [2, 2, 3, 4, 4],
  "agents_spawned": 2,
  "agents_retired": 0,
  "mean_active_agents": 3.0,
  "lock_conflicts": 4,
  "parallel_utilization": 0.71,
  "specialization_entropy": 0.42,
  "colony_specialization": 0.58,
  "protocol_compiler_used": false,
  "skills_loaded_count": 0,
  "skills_injected_count": 0
}
```

Strict success must require:

```text
artifact_delivered
AND patch_delivered
AND patch_applies
AND official_success
```

No missing, empty, inapplicable, or unevaluated patch can count as success.

---

## 11. Practical Constraints

- Docker campaign execution is mandatory.
- Start small: smoke 5 repos, pilot 10-20 repos, main 30 repos.
- Main model: Gemma via OpenRouter, seed 42.
- DeepSeek only confirmatory.
- 1 seed may be unavoidable for the memoir, but this must be listed as a threat to validity.
- Missing or invalid runs count as failures.
- Per-repo logs must be preserved.
- Pre-register selected repository subsets.
- Avoid cherry-picking.
- Avoid benchmark-specific prompt overfitting.
- Report cost and runtime even on failures.

---

## 12. Expected Deliverable

Please produce:

1. Executive summary.
2. Critical verdict on the direction.
3. Benchmark comparison table.
4. Framework / paper lessons.
5. Required baseline matrix.
6. V7 Elastic Colony architecture proposal.
7. Ablation matrix.
8. Output contract and metrics.
9. Statistical analysis plan.
10. Implementation roadmap by phase.
11. Methodological risks and mitigations.
12. Recommendation on freezing, abandoning, or rebuilding C3.
13. Sources with links.

Be explicit when evidence is weak or speculative. Do not overstate.

---

## 13. Suggested Final Judgment Format

Please conclude with one of these:

- "Proceed with MigrationBench + V6 static first; V7 later."
- "Proceed directly with V7 ablations after minimal adapter."
- "Do not attempt V7 before stronger baselines."
- "MigrationBench is not suitable; use another benchmark."
- "Freeze C3 permanently."
- "Freeze C3 temporarily; reintroduce mechanisms only after V7."

Explain why.
