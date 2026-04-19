# TravelPlanner V6 Benchmark Analysis Report

Date: 2026-04-19

## 1. Scope and Method

This report analyzes the paired-seed benchmark campaign stored under:

- `output/travelplanner_framework_compare/v6_overnight_20260418/v5_full/seed42`
- `output/travelplanner_framework_compare/v6_overnight_20260418/v5_full/seed43`
- `output/travelplanner_framework_compare/v6_overnight_20260418/v6_base/seed42`
- `output/travelplanner_framework_compare/v6_overnight_20260418/v6_base/seed43`
- `output/travelplanner_framework_compare/v6_overnight_20260418/v6_A/seed42`
- `output/travelplanner_framework_compare/v6_overnight_20260418/v6_A/seed43`

Artifacts used:

- `benchmark_summary.json`
- `official_eval.json`
- `runs.json`

Methodological choices:

- same benchmark contract across all compared runs
- same validation subset size: `180` queries per seed
- same official TravelPlanner scorer semantics
- same paired seeds: `42` and `43`
- analysis performed at three levels:
  - seed-level aggregate metrics
  - query-seed transitions
  - emergence / runtime-behavior readout from `runs.json`

Important methodological note:

- this report deliberately uses the `v6_overnight_20260418` campaign root for all three presets, including `v5_full`, to keep the comparison intra-campaign and avoid mixing with older standalone `v5_full` artifacts from a different run folder
- because only `2` seeds are available, the conclusions below are strong directional findings, not formal significance claims

## 2. Executive Summary

The short version is:

1. `v6_base` validates the anti-stagnation hypothesis.
   It increases `final_pass_rate`, `delivery_rate`, and `hard_constraint_micro` versus `v5_full`, mainly by reducing premature `idle_cycles` stops.

2. `v6_A` is the best current compromise.
   It achieves the best overall `final_pass_rate` while also being the fastest preset and reducing coordination overhead relative to `v6_base`.

3. The colony is currently coordination-heavy, not specialization-heavy.
   The framework clearly exhibits emergent collective behavior, but the dominant emergent regime is still high contention and frequent action switching rather than clean role specialization.

4. The main residual failure mode is no longer only stagnation.
   V6 reduces early stopping, but many failures now end as "completed but invalid plans". This is the strongest argument for running `v6_C` next.

5. The results are defendable, but the claim must be framed correctly.
   You can defend that the framework improves distributed control, delivery, and constraint adherence under a frozen benchmark contract. You should not yet claim robust general multi-city planning.

## 3. What the Framework Really Is

### Non-technical explanation

At a high level, the framework is not "six agents chatting in parallel". It is a stigmergic control system:

- agents do not coordinate primarily by direct dialogue
- they coordinate by writing and reading shared markers in a common environment
- those markers carry urgency, state, inhibition, history, and dependency information
- the global behavior emerges from repeated local decisions over this shared memory

In plain terms, the framework behaves more like a colony working on a shared board than like a single monolithic planner.

### Technical explanation

The core loop is:

1. build a snapshot of the environment
2. let each agent perceive candidate markers
3. compute action pressures and select a target
4. arbitrate conflicts through lock acquisition
5. execute actions in parallel
6. deposit new markers or updates
7. compute emergence signals and optional control adaptations
8. stop when the system reaches terminality, idle exhaustion, or budget/tick limits

The main runtime surfaces relevant to this campaign are:

- marker-centric state model in `core/marker.py`
- transactional marker store and lock telemetry in `core/marker_store.py`
- pressure-based action selection in `core/pressure.py`
- local sensing and target selection in `core/agent.py`
- recovery controller and dynamic idle in `core/orchestrator.py`
- snapshot overlays and repair-marker deposition in `core/environment.py`
- emergence metrics in `core/emergence.py`

In Sprint 8, the important V6 additions are:

- `v6_base`: same frozen V5 reference behavior but with `idle_cycles_to_stop=16`
- `v6_A`: `v6_base` plus the recovery controller
- `v6_B`: `v6_A` plus short-horizon stickiness
- `v6_C`: `v6_A` plus targeted repair markers

## 4. Headline Results

### Aggregate seed averages

| Metric | v5_full | v6_base | v6_A | Delta v6_A vs v5_full |
|---|---:|---:|---:|---:|
| Final pass rate | 20.83% +- 0.39 pts | 22.22% +- 0.79 pts | 23.61% +- 0.39 pts | +2.78 pts |
| Delivery rate | 50.56% +- 1.57 pts | 59.44% +- 1.57 pts | 57.50% +- 1.96 pts | +6.94 pts |
| Commonsense micro | 50.42% +- 1.47 pts | 58.61% +- 1.37 pts | 56.94% +- 1.77 pts | +6.53 pts |
| Hard constraint micro | 40.12% +- 0.17 pts | 46.79% +- 0.17 pts | 46.43% +- 0.00 pts | +6.31 pts |
| Avg tokens/query | 20064.78 +- 484.18 | 25246.79 +- 146.55 | 24960.96 +- 285.79 | +4896.18 |
| Avg runtime/query (s) | 93.95 +- 0.56 | 70.31 +- 0.25 | 62.51 +- 0.80 | -31.44 |
| Avg coordination overhead | 21.33 +- 2.64 | 33.62 +- 2.34 | 27.69 +- 2.40 | +6.36 |
| Avg cost/query (USD) | $0.002079 +- $0.000050 | $0.002615 +- $0.000015 | $0.002586 +- $0.000030 | +0.000507 |

### Interpretation

#### `v5_full -> v6_base`

`v6_base` improves:

- `final_pass_rate`: `+1.39` points
- `delivery_rate`: `+8.89` points
- `commonsense_micro`: `+8.19` points
- `hard_constraint_micro`: `+6.67` points

But it also increases:

- tokens
- cost
- coordination overhead

This means `v6_base` buys extra coverage and extra constraint satisfaction partly by allowing more execution to continue instead of dying early.

#### `v6_base -> v6_A`

`v6_A` improves:

- `final_pass_rate`: `+1.39` points
- runtime/query: `-7.80` seconds
- coordination overhead: `-5.93`
- tokens/query: `-285.84`

But it slightly decreases:

- `delivery_rate`: `-1.94` points
- `commonsense_micro`: `-1.67` points
- `hard_constraint_micro`: `-0.36` points

This is an important nuance:

- `v6_base` expands coverage
- `v6_A` improves the efficiency-quality balance of that expanded regime

In other words, the recovery controller does not simply make the system "do more". It appears to make the colony stop wasting some coordination effort.

### Quality conditional on delivery

If we compute `final_pass_rate / delivery_rate`, we get a useful quality readout among delivered plans:

- `v5_full`: `0.412`
- `v6_base`: `0.374`
- `v6_A`: `0.411`

Interpretation:

- `v6_base` delivers much more often, but a smaller share of those delivered plans fully pass
- `v6_A` restores delivered-plan quality almost exactly to the `v5_full` level, while still keeping more delivery than `v5_full`

This is one of the strongest arguments in favor of `v6_A`.

## 5. What the Emergent Behavior Says

### Colony-wide signature

Across the full query-seed population, the colony shows:

- very high `collaboration_density`: around `0.92` to `0.95`
- very low `colony_specialization`: around `0.11` to `0.13`
- very high `lock_contention_rate`: around `0.75`
- relatively low `parallel_utilization`: around `0.18` to `0.23`
- high `action_switching_rate`: around `0.70` to `0.71`

This means the current emergence profile is:

- agents read and touch the same coordination space a lot
- agents are not yet strongly specialized into stable functional roles
- a large fraction of action attempts collide
- only a modest fraction of the 6-agent capacity is productively used in parallel

So yes, the framework exhibits emergence, but the dominant emergent regime is still conflict-heavy and somewhat thrashy.

### Success signature inside `v6_A`

For `v6_A`, successful and failed runs differ in a very coherent way:

| Metric in `v6_A` | Final pass | Final fail | Reading |
|---|---:|---:|---|
| `total_ticks` | 16.92 | 31.02 | success arrives much earlier |
| `runtime_seconds` | 52.77 | 65.51 | success is faster |
| `coordination_overhead` | 16.92 | 31.02 | success wastes less coordination |
| `tokens_used` | 16597.75 | 27545.95 | success is more token-efficient |
| `action_switching_rate` | 0.6722 | 0.7237 | less role thrashing is better |
| `collaboration_density` | 0.9155 | 0.9544 | more collaboration is not automatically better |
| `lock_contention_rate` | 0.7418 | 0.7552 | slightly less contention helps |
| `parallel_utilization` | 0.2575 | 0.1858 | useful parallel work matters |
| `pressure_entropy` | 0.8209 | 0.8124 | slightly more balanced pressure helps |

Main interpretation:

- successful runs are not the runs where the colony "works harder"
- they are the runs where the colony commits earlier, switches less, collides less, and makes better use of actual parallel work

This is a mature and defensible thesis point:

> In this framework, better emergence is not maximal interaction. It is disciplined distributed coordination.

### Important caution about `convergence_tick`

`convergence_tick` is useful, but it must be interpreted carefully.

In this codebase, it reflects operational progress toward terminal markers, not semantic correctness of the final plan. That means a run can "converge" operationally and still fail the official scorer.

So for defense purposes:

- use `convergence_tick` as a runtime-control indicator
- do not present it as a direct proxy for benchmark correctness

That distinction is scientifically important.

## 6. The Stagnation Story: What V6 Fixed and What It Did Not

### Stop-reason distribution

Across both seeds together:

- `v5_full`
  - `all_terminal`: `183`
  - `idle_cycles`: `177`
  - pass rate among `all_terminal`: `40.98%`

- `v6_base`
  - `all_terminal`: `214`
  - `idle_cycles`: `146`
  - pass rate among `all_terminal`: `37.38%`

- `v6_A`
  - `all_terminal`: `208`
  - `idle_cycles`: `152`
  - pass rate among `all_terminal`: `40.87%`

Key fact:

- every `idle_cycles` stop is a failure in this campaign

So reducing `idle_cycles` matters.

### What `v6_base` really changed

From `v5_full` to `v6_base`, among query-seed cases that were originally `idle_cycles` failures:

- `12` became passes
- `22` became `all_terminal` failures
- `143` stayed `idle_cycles` failures

This is extremely informative.

It means `v6_base` did not just "solve stagnation". It often transformed:

- early failure -> completed but still invalid plan

That is progress, but it is incomplete progress.

### What `v6_A` adds

From `v6_base` to `v6_A`, among query-seed cases that were `all_terminal` failures in `v6_base`:

- `9` became passes
- `117` stayed `all_terminal` failures
- `8` fell back to `idle_cycles`

This suggests that the recovery controller is not mainly a pure anti-idle mechanism. It also helps rescue part of the "finished but not good enough" population by improving coordination quality before the final plan stabilizes.

## 7. Behavior by Query Type

Using the TravelPlanner dataset fields (`days`, `visiting_city_number`, `level`, `local_constraint`), the pass-rate landscape is:

| Query bucket | n | v5_full | v6_base | v6_A |
|---|---:|---:|---:|---:|
| one city | 60 | 31.67% | 30.83% | 35.83% |
| three cities | 60 | 11.67% | 14.17% | 13.33% |
| 6+ days | 60 | 11.67% | 14.17% | 13.33% |
| hard level | 60 | 15.83% | 20.83% | 20.00% |
| room type constraint | 64 | 14.06% | 18.75% | 20.31% |
| house-rule constraint | 77 | 18.83% | 22.73% | 22.73% |
| cuisine constraint | 48 | 19.79% | 20.83% | 19.79% |
| transportation preference | 51 | 16.67% | 22.55% | 21.57% |
| very complex | 105 | 14.76% | 17.62% | 17.62% |

### Interpretation

The gains are not uniform.

Strongest current areas:

- one-city queries
- room-type constraints
- house-rule constraints
- hard queries overall
- transportation preferences

Still clearly weak:

- three-city planning
- 6+ day queries
- very complex long-horizon routing

This matters for thesis defense because it shows the framework is not randomly better or worse. It is improving specific failure regimes.

## 8. Diagnostic Case Studies

### Case 1: Query 78

Prompt type:

- `3-day`
- `1-city`
- accommodation constraint (`entire rooms`)

Pattern:

- `v5_full`: fail in both seeds by `idle_cycles`
- `v6_base`: pass in both seeds
- `v6_A`: pass in both seeds

Reading:

- classic anti-stagnation win
- the system already knew enough to solve the task, but it was stopping too early in `v5_full`

### Case 2: Query 170

Prompt type:

- `7-day`
- `3-city`
- group of `6`
- children / room suitability
- no self-driving

Pattern:

- `v5_full`: fail in both seeds by `idle_cycles`
- `v6_base`: pass in both seeds, but with `38-43` ticks and much higher cost
- `v6_A`: pass in both seeds with `23-28` ticks and much lower runtime

Reading:

- `v6_base` proves the task is not impossible
- `v6_A` shows the recovery controller can rescue difficult coordination while reducing waste

This is one of the best "serious defense" examples in the campaign.

### Case 3: Query 42

Prompt type:

- `7-day`
- `3-city`
- California multi-city itinerary

Pattern:

- `v5_full`: pass in both seeds
- `v6_base`: fail in both seeds
- `v6_A`: mixed, one seed repaired, one still failed

Reading:

- this is a good cautionary example
- V6 is not monotonically better on every complex query
- recovery helps, but the system still lacks a robust city-level persistent repair logic for some multi-city tasks

This case is useful in defense because it shows rigor and honesty.

## 9. What You Can Defend Seriously

### Claims that are well supported

1. **The framework improves under a frozen benchmark contract.**
   The scorer, split, and evaluation semantics are preserved, yet `v6_A` improves `final_pass_rate` over `v5_full`.

2. **The V6 controls improve distributed control quality, not only raw activity.**
   The best preset is also the fastest one, which is strong evidence that the gain is not merely extra brute-force search.

3. **Emergence metrics are diagnostically meaningful.**
   Success consistently aligns with lower switching, lower coordination waste, and better realized parallelism.

4. **The framework is capable of moving failures from premature collapse toward evaluable plans.**
   This is exactly what we would expect from a stronger stigmergic control layer.

5. **The residual bottleneck is now legible.**
   The next improvement target is not vague "better prompting"; it is specifically repair of terminal-but-invalid plans and stronger support for multi-city persistence.

### Claims that are not yet safe

1. **Do not claim strong general multi-city robustness.**
   The `3-city` regime remains weak.

2. **Do not claim strong emergent specialization.**
   The colony is collaborative, but specialization remains low.

3. **Do not overclaim statistical certainty.**
   Two seeds are enough for a serious directional reading, not for definitive significance language.

## 10. Why `v6_C` Is the Right Next Run

Based on the current evidence, `v6_C` has higher information value than `v6_B`.

Why:

1. the main V5 problem was premature stagnation
2. `v6_base` partially fixed that by reducing `idle_cycles`
3. the residual failure mass moved toward `all_terminal` but invalid plans
4. `v6_A` improved that quality/efficiency balance, but did not eliminate the residual invalid-plan regime
5. `v6_C` is exactly the preset designed to address this new bottleneck through targeted repair markers

Said differently:

- `v6_B` tests whether short-horizon continuity can reduce local thrashing
- `v6_C` tests whether the system can convert terminal-invalid completions into scorer-valid plans

Given the evidence in this campaign, the second question is more urgent.

My recommendation:

- run `v6_C` before spending time on a full `v6_B` campaign
- if `v6_C` materially converts `all_terminal` failures into passes, it will confirm that the frontier has shifted from search continuation to repair continuation

## 11. Improvement Priorities After `v6_C`

### Priority 1: quality-aware repair after operational convergence

Current issue:

- the system often reaches terminality without satisfying all official constraints

Action:

- make repair markers the main follow-up mechanism for terminal-invalid outputs
- export per-constraint failure frequencies in future runs

### Priority 2: persistent multi-city coverage

Current issue:

- long-horizon and `3-city` tasks remain structurally fragile

Action:

- keep city-level subgoals explicit and persistent in the DAG
- strengthen route continuity across city transitions
- preserve unresolved city coverage instead of allowing the plan to collapse into a partial but terminal-looking state

### Priority 3: reduce contention before adding more agents

Current issue:

- `lock_contention_rate` stays around `0.75`
- `parallel_utilization` remains low

Action:

- narrow candidate sets earlier
- favor conflict-aware target filtering
- avoid scaling `num_agents` upward before the DAG width justifies it

### Priority 4: distinguish operational convergence from semantic convergence

Current issue:

- `all_terminal` does not mean `final_pass`

Action:

- add an explicit quality-aware convergence signal
- track whether terminality is accompanied by unresolved official constraint failures

### Priority 5: make the benchmark argument easier to defend

Action:

- keep publishing paired-seed tables
- add per-bucket deltas by `(days, visiting_city_number, level, constraint family)`
- add `final_pass_given_delivery` systematically in every scientific readout

## 12. Suggested Defense Narrative

If you need a clear verbal positioning in front of a jury, this is the message I would defend:

> My framework is not a simple multi-agent prompt chain. It is a stigmergic orchestration system in which agents coordinate through a shared marker space with pressure, decay, inhibition, lock arbitration, and adaptive runtime control.  
>  
> The benchmark evidence shows that when we add general runtime controls, we do not only change the score; we change the failure regime. V6 reduces premature collapse, increases delivery and constraint satisfaction, and with the recovery controller it achieves the best pass rate while also reducing runtime and coordination waste.  
>  
> The remaining weakness is now legible: the system too often reaches terminal states that are operationally complete but semantically invalid, especially on long multi-city tasks. That is precisely why targeted repair is the next scientifically coherent step.

That narrative is:

- technically accurate
- modest enough to be credible
- strong enough to show a real systems contribution

## 13. Bottom Line

If I compress the whole campaign into one sentence:

`v6_base` proves that anti-stagnation matters, `v6_A` proves that better control can improve both pass rate and efficiency, and the next real frontier is targeted repair of terminal-invalid plans rather than more raw exploration.
