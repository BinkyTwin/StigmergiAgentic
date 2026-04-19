# Project Captures

## 2026-04-19 — Paired-Seed V6 Readout: Stagnation Relief Shifted the Residual Failure Mass Toward Terminal-Invalid Plans

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `9/10`
- `confidence`: `high`
- `scope`: `Post-hoc analysis of the paired-seed TravelPlanner campaign v5_full vs v6_base vs v6_A over the 2026-04-18 overnight run set`

### Outcome

Analyzed the paired-seed benchmark artifacts in `output/travelplanner_framework_compare/v6_overnight_20260418/` and established a clear V6 progression. `v6_base` confirms the anti-stagnation hypothesis by cutting `idle_cycles` failures and raising delivery plus hard-constraint adherence, but it often converts early collapse into `all_terminal` yet still invalid plans rather than directly into passes. `v6_A` is the best current balance: it raises `final_pass_rate` to `23.6%`, restores delivered-plan quality close to `v5_full`, and reduces runtime plus coordination overhead relative to `v6_base`. The key insight is that the frontier has moved: the main residual problem is no longer only search continuation, but repair of terminal-invalid outputs, which makes `v6_C` the highest-value next ablation.

### Reusable Patterns (1-3)

1. **When an anti-stagnation change reduces `idle_cycles`, always track where the rescued failures migrate next.** If they mostly become `all_terminal` failures instead of passes, the next lever should be repair quality rather than more exploration time.
2. **Read `final_pass_given_delivery` together with `delivery_rate`.** A preset can look better on coverage while quietly degrading the quality of delivered plans; this distinction was essential to separate `v6_base` from `v6_A`.
3. **In this TravelPlanner stigmergic regime, better emergence looks like lower switching and higher realized parallelism, not higher collaboration density.** Successful runs consistently used fewer ticks, switched actions less, and realized more parallel work.

### Evidence

- `analysis/travelplanner_v6_benchmark_report_20260419.md`
- `output/travelplanner_framework_compare/v6_overnight_20260418/v5_full/seed42/runs.json`
- `output/travelplanner_framework_compare/v6_overnight_20260418/v5_full/seed43/runs.json`
- `output/travelplanner_framework_compare/v6_overnight_20260418/v6_base/seed42/runs.json`
- `output/travelplanner_framework_compare/v6_overnight_20260418/v6_base/seed43/runs.json`
- `output/travelplanner_framework_compare/v6_overnight_20260418/v6_A/seed42/runs.json`
- `output/travelplanner_framework_compare/v6_overnight_20260418/v6_A/seed43/runs.json`

## 2026-04-17 — Expériences idle_cycles 8/16 et découvertes sur la stagnation différentielle

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `9/10`
- `confidence`: `high`
- `scope`: `Expériences contrôlées idle_cycles_to_stop={4,8,16} sur seed44, même benchmark validation 180 queries, backbone qwen3.5-9b`

### Outcome

Trois découvertes empiriques majeures issues des expériences idle_cycles sur le même seed (seed44) :

**Découverte 1 — Le bénéfice d'idle_cycles est non-uniforme selon la complexité de la query.**
idle=16 améliore fortement les 7j (+8pp, 11.7% → 20.0%) mais dégrade légèrement les 5j (20.0% → 16.7%) et est neutre sur les 3j. Cela confirme que la stagnation a deux causes distinctes : pour les 7j, le swarm a besoin de temps pour résoudre les dépendances inter-city via decay et réactivation ; pour les 5j, le problème est structurel (sous-objectifs perdus dans le DAG) et plus de temps ne suffit pas.

**Découverte 2 — Le seuil idle_cycles a un effet de palier, pas continu.**
Entre idle=4 et idle=8 : aucun gain net (20.6% vs 21.7% — variance seed). Entre idle=8 et idle=16 : gain net sur 7j. Il existe un seuil minimal à franchir pour que le mécanisme de decay+réactivation ait le temps d'agir. idle=8 est en dessous du seuil pour les 7j.

**Découverte 3 — `num_agents: 6` est sur-dimensionné pour le DAG TravelPlanner.**
Avec 6 agents, seulement ~1.5 travaillent simultanément (`parallel_utilization ≈ 0.22`, soit 1.49/6). `lock_contention_rate ≈ 0.75` indique que 75% des tentatives de lock sont bloquées. Cause structurelle : le DAG TravelPlanner est principalement séquentiel (search → plan → validate → finalize). Ajouter des agents n'augmente pas le parallélisme réel — cela augmente seulement la contention. Le levier est la largeur du DAG (T2), pas le nombre d'agents.

### Chiffres de référence

| Config | 3j | 5j | 7j | Global | Ticks moy | Idle% |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| v5_full idle=4 (seed42) | 33.3% | 20.0% | 11.7% | 21.7% | 19.4 | 50.0% |
| v5_idle8 idle=8 (seed44) | 33.3% | 20.0% | 8.3% | 20.6% | 24.6 | 52.8% |
| v5_idle16 idle=16 (seed44) | 31.7% | 16.7% | **20.0%** | **22.8%** | 34.9 | 42.8% |

### Reusable Patterns (1-3)

1. **Toujours stratifier par complexité avant de tuner `idle_cycles_to_stop`.** Un paramètre global unique est sous-optimal : l'optimum pour les 7j est différent de celui pour les 3j. Implémenter un `idle_cycles` dynamique basé sur la taille du DAG (nombre de nodes pending) est la direction correcte.
2. **`lock_contention_rate > 0.7` + `parallel_utilization < 0.25` est un signal de goulot DAG, pas un signal d'insuffisance d'agents.** Ne pas répondre à ce signal en augmentant `num_agents` — répondre en élargissant le DAG (décomposition plus riche, sous-objectifs persistants).
3. **Pour les systèmes stigmergiques multi-tâches, l'effet de temps supplémentaire (idle cycles) est utile uniquement si le mécanisme de decay et réactivation a des markers à réactiver.** Si le DAG est épuisé (sous-objectifs perdus), plus de temps ne fait que retarder l'échec.

### Evidence
- `output/travelplanner_framework_compare/v5_idle8/seed44/official_eval.json`
- `output/travelplanner_framework_compare/v5_idle16/seed44/official_eval.json`
- `scripts/analyze_emergence.py`
- `documentation/redisgn_v2/plan_v6_framework_general_improvement.md`

## 2026-04-17 — Review-Ready V6 Plan for General Framework Improvement Without Benchmark Drift

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `8/10`
- `confidence`: `high`
- `scope`: `Planning document for the next framework-improvement cycle after the ~21% TravelPlanner V5-full validation regime`

### Outcome
Produced a review-ready plan in `documentation/redisgn_v2/plan_v6_framework_general_improvement.md` that converts the latest emergence analysis into a methodology-safe improvement roadmap. The plan explicitly freezes the benchmark and official scorer, separates framework-general workstreams (anti-stagnation, persistent decomposition, validator-guided repair, anti-thrashing, richer emergence adaptation) from TravelPlanner-only follow-ups, and proposes a clean V6 ablation ladder over the same benchmark conditions.

### Reusable Patterns (1-3)
1. When benchmark analysis reveals multiple failure regimes, write the next improvement plan around `general framework mechanisms` first and quarantine `adapter-specific heuristics` into a separate section.
2. For article-grade benchmark work, freeze the scorer, runner semantics, validation split, and baseline config before proposing implementation tasks; review confidence depends on preserving the thermometer.
3. If the goal is scientific credibility, require every proposed improvement cycle to include its own ablation ladder from the frozen baseline rather than bundling several changes into one un-attributable preset.

### Evidence
- `documentation/redisgn_v2/plan_v6_framework_general_improvement.md`
- `output/travelplanner_framework_compare/v5_full/seed42/runs.json`
- `output/travelplanner_framework_compare/v5_full/seed43/runs.json`

## 2026-04-17 — Query-Type Emergence Failure Regimes in V5-Full Validation

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `8/10`
- `confidence`: `high`
- `scope`: `Type-stratified post-hoc analysis of the latest TravelPlanner V5-full validation seeds around the 21% pass-rate regime`

### Outcome
Stratified the latest `v5_full` validation results (`seed42`, `seed43`) by TravelPlanner query type using the dataset’s structured fields (`days`, `visiting_city_number`, `level`, `local_constraint`). The analysis shows two distinct failure regimes. `3-day / 1-city` queries mostly produce non-empty plans and fail on constraint satisfaction, especially for hard cases such as `no self-driving`, `private room`, `pets`, or `4 cuisines`. By contrast, `5-day / 2-city` and especially `7-day / 3-city` queries fail primarily through empty-plan collapse and `idle_cycles`, with much later convergence (`14` then `19` ticks on average) and weaker success rates even when the colony remains collaborative. This indicates that the next framework gains should come from type-specific control: constraint-repair hardening for single-city hard queries, and anti-stagnation / stronger decomposition for multi-city queries.

### Reusable Patterns (1-3)
1. When TravelPlanner pass rate is around the low-20% range, always separate `single-city constraint failure` from `multi-city empty-plan collapse`; the aggregate score mixes two different bottlenecks that require different fixes.
2. Use `empty_plan_rate ~= idle_cycle_rate` as a practical signature of coordination exhaustion in multi-city runs; if those ratios rise together, the issue is search/decomposition rather than final-plan validation.
3. Hard constraints can either overload the planner or provide useful scaffolding depending on query topology: in `3/1` they mostly expose weak constraint handling, while in `7/3` they can outperform easier prompts by giving the colony a more explicit search structure.

### Evidence
- `output/travelplanner_framework_compare/v5_full/seed42/runs.json`
- `output/travelplanner_framework_compare/v5_full/seed43/runs.json`
- `config/ablation/v5_full.yaml`
- `adapters/travelplanner/workspace.py`

## 2026-04-17 — V5-Full Emergence Signal Analysis on Validation Seeds 42 and 43

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `7/10`
- `confidence`: `high`
- `scope`: `Post-hoc analysis of TravelPlanner V5-full validation run emergence metrics for the latest stigmergic benchmark seeds`

### Outcome
Analyzed `summary.emergence` for all 180 queries in the latest `v5_full` validation runs (`seed42`, `seed43`) and compared the emergent metrics against `final_pass`, `stop_reason`, and seed-to-seed flips. The strongest positive signals for query success were high `pressure_entropy` and high `parallel_utilization`, while late `convergence_tick` consistently tracked worse outcomes. `action_switching_rate` behaved differently across seeds but was clearly harmful in `seed42` when it became too high, suggesting that useful emergence in this preset looks more like sustained diversified pressure with actual parallel work than like rapid role thrashing or maximal collaboration density.

### Reusable Patterns (1-3)
1. For TravelPlanner post-hoc analysis, treat `pressure_entropy` and `parallel_utilization` as the primary positive emergence indicators; they separated pass/fail far more clearly than `collaboration_density` or `colony_specialization` in the latest validation seeds.
2. Interpret a high `convergence_tick` as delayed colony stabilization rather than automatically as “more exploration”; in `v5_full`, later convergence coincided with more `idle_cycles` failures and lower final pass.
3. When two seeds disagree on a query outcome, inspect the joint profile `{convergence_tick, pressure_entropy, parallel_utilization, action_switching_rate}` before reading the difference as random variance; the flip cases often show a coherent shift in those signals.

### Evidence
- `output/travelplanner_framework_compare/v5_full/seed42/runs.json`
- `output/travelplanner_framework_compare/v5_full/seed43/runs.json`
- `output/travelplanner_framework_compare/v5_full/seed42/queries/query_063.json`
- `output/travelplanner_framework_compare/v5_full/seed43/queries/query_063.json`
- `output/travelplanner_framework_compare/v5_full/seed42/queries/query_170.json`
- `output/travelplanner_framework_compare/v5_full/seed43/queries/query_170.json`

## 2026-04-13 — Self-Refine Baseline Transport-Failure Hardening

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `8/10`
- `confidence`: `high`
- `scope`: `Implementation of T3 for the TravelPlanner solo_self_refine scientific baseline`

### Outcome
Confirmed from the historical run artifacts that `solo_self_refine` seed 43 failed on `query_idx=139` because `self_refine_draft` propagated an `openai.APIConnectionError` out of `scientific_baselines.py:_call_llm`. Hardened the baseline by adding one extra node-level retry in `TravelPlannerScientificBaselineRunner`, broadening critique fallback from parse-only failures to all provider exceptions, and adding explicit Self-Refine fallbacks so a draft failure returns an empty query payload and a reviser failure reuses the draft instead of aborting the full seed.

### Reusable Patterns (1-3)
1. In long scientific baseline batches, treat provider transport failures as query-local degradations whenever the method can still emit a scorer-compatible payload; otherwise one network blip invalidates the whole seed.
2. For Self-Refine specifically, `critic` can fall back to validator-derived repair instructions and `reviser` can fall back to the last valid draft without violating the method’s overall draft-critique-revise structure.
3. Add resilience first at the orchestration-node boundary (`_call_llm` wrapper + stage-specific fallback) rather than changing the shared LLM client when the client already handles transport retries generically.

### Evidence
- `output/travelplanner_framework_compare/20260409_233919/scientific_pack/run_registry.csv`
- `output/travelplanner_framework_compare/20260409_233919/runs/solo_self_refine/seed_43/full/logs/query_139.log`
- `adapters/travelplanner/scientific_baselines.py`
- `tests/unit/test_travelplanner_scientific_baselines.py`
- `uv run pytest tests/unit/test_travelplanner_scientific_baselines.py -q`

## 2026-04-13 — TravelPlanner V4-Only Preset and Query-Level Failure Taxonomy

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `8/10`
- `confidence`: `high`
- `scope`: `Implementation of T1/T2 from the V5 framework-improvement plan for TravelPlanner`

### Outcome
Implemented a clean `config/travelplanner_v4_only.yaml` preset that activates only the five opt-in V4 stigmergic corrections, and added query-level runtime failure taxonomy for TravelPlanner by persisting planning/validation failure reasons on markers, surfacing `failure_reason` in adapter evaluation and single-query exports, and propagating the same field into benchmark `runs.json` plus failure-reason summaries.

### Reusable Patterns (1-3)
1. Persist operational failure causes on workflow markers (`failure_reason`, `last_failure_reason`, `failure_history`) rather than only in transient tool metadata; adapter-level post-processing can then reconstruct query outcomes without touching the core orchestrator.
2. In benchmark domains, distinguish `operational failure taxonomy` from `quality scoring`: a non-empty evaluated plan can remain `ok` operationally even when `final_pass` is false, while empty-plan and control-flow breakdowns get explicit machine-readable reasons.
3. Keep pure ablation presets as dedicated config files that only flip the intended feature gates and preserve agent count, pressure parameters, and tick budget unchanged.

### Evidence
- `config/travelplanner_v4_only.yaml`
- `adapters/travelplanner/tools.py`
- `adapters/travelplanner/adapter.py`
- `scripts/run_travelplanner_query_export.py`
- `scripts/run_travelplanner_framework_benchmark.py`
- `uv run pytest tests/unit/test_config.py tests/unit/test_travelplanner_tools.py tests/unit/test_travelplanner_adapter.py tests/unit/test_travelplanner_benchmark_runner.py -q`
- `uv run pytest tests/integration/test_travelplanner.py -q`

## 2026-04-12 — V5 Plan Review for TravelPlanner Scientific Campaign

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `8/10`
- `confidence`: `high`
- `scope`: `Review of the proposed V5 framework-improvement plan before execution`

### Outcome
Reviewed `documentation/redisgn_v2/plan_v5_framework_improvement.md` against the current codebase and benchmark evidence. The plan has strong scientific hygiene (train-only tuning, explicit anti-cheating constraints, ablation intent), but should not be executed unchanged because it mixes ablation with optimization, targets some already-implemented mechanisms (`stop_reason`, LLM retry/backoff), points one prompt task at the wrong file (`llm/prompts.py` instead of TravelPlanner tool prompts), and still underweights the main structural failure mode: the current TravelPlanner adapter is effectively single-destination and therefore collapses on multi-city queries.

### Reusable Patterns (1-3)
1. Before launching a new scientific campaign plan, verify each proposed task against the current codebase so the plan does not spend effort re-adding already-present observability or retry mechanisms.
2. Keep pure ablation campaigns isolated from optimization campaigns; once heuristics, prompt tuning, or agent-count changes enter the same preset, the result no longer measures the ablated feature alone.
3. When benchmark failures are dominated by representation mismatch in the adapter, prioritize adapter redesign before local heuristics or hyperparameter tuning; otherwise the plan optimizes around a structural bottleneck.

### Evidence
- `documentation/redisgn_v2/plan_v5_framework_improvement.md`
- `core/orchestrator.py`
- `main.py`
- `llm/client.py`
- `adapters/travelplanner/tools.py`
- `adapters/travelplanner/scientific_baselines.py`

## 2026-04-11 — TravelPlanner Framework Failure Regime Analysis (Run 20260409_233919)

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `9/10`
- `confidence`: `high`
- `scope`: `Post-hoc analysis of the scientific TravelPlanner framework comparison pack for StigmergiAgentic failure modes`

### Outcome
Analyzed the final scientific pack and raw per-query artifacts for `output/travelplanner_framework_compare/20260409_233919` and isolated a two-layer failure regime for `StigmergiAgentic`: first, all benchmark gains are confined to `3-day / 1-city` queries, while `5-day / 2-city` and `7-day / 3-city` requests collapse to zero final-pass; second, the TravelPlanner adapter is structurally single-destination because search markers, fallback search payloads, and routing context all bind to one `dest` value, so multi-city requests frequently end as `No travel plan generated.` with `status=ok`, `stop_reason=all_terminal`, and `final_plan=[]`.

### Reusable Patterns (1-3)
1. When analyzing TravelPlanner benchmark runs, separate failures into `empty-plan delivery collapse` and `non-empty but invalid itinerary`; aggregate `final_pass_rate` alone hides whether the planner failed to synthesize any route at all.
2. If the adapter searches hotels, restaurants, attractions, and route legs only against a single `dest`, treat the implementation as single-destination even when prompts mention `visiting_city_number`; multi-city benchmark failure is then structural, not stochastic.
3. Export `empty_plan_after_max_attempts` as an explicit query-level failure artifact instead of a nominally successful run with `final_plan=[]`, otherwise post-hoc scientific analysis loses the true cause of failure.

### Evidence
- `output/travelplanner_framework_compare/20260409_233919/scientific_pack/paper_table_main.md`
- `output/travelplanner_framework_compare/20260409_233919/scientific_pack/pairwise_final_pass_stats.md`
- `output/travelplanner_framework_compare/20260409_233919/runs/stigmergiagentic/seed_42/full/runs.json`
- `output/travelplanner_framework_compare/20260409_233919/runs/stigmergiagentic/seed_42/full/queries/query_022.json`
- `output/travelplanner_framework_compare/20260409_233919/runs/stigmergiagentic/seed_42/full/queries/query_040.json`
- `adapters/travelplanner/adapter.py`
- `adapters/travelplanner/tools.py`

## 2026-04-09 — LangGraph Structured-Output Fallback Hardening

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `8/10`
- `confidence`: `high`
- `scope`: `TravelPlanner LangGraph supervisor resilience against malformed provider JSON during batch benchmark execution`

### Outcome
Hardened the LangGraph TravelPlanner baseline so malformed or truncated provider JSON in intermediate supervisor nodes no longer aborts the full benchmark batch by default: intermediate prompts were compacted, structured-output calls now retry after schema-parse failures, and deterministic node-specific fallbacks keep the query export alive when parsing still fails.

### Reusable Patterns (1-3)
1. For graph-based LLM benchmarks, separate transport-level retries from schema-parse retries; provider success does not imply usable structured output.
2. Keep intermediate supervisor node outputs minimal and explanation-free when the values are only used for downstream machine consumption.
3. In long batch benchmarks, add deterministic node-level fallbacks for non-final planner stages so one malformed JSON blob does not invalidate the entire campaign.

### Evidence
- `adapters/travelplanner/langgraph_supervisor.py`
- `scripts/run_travelplanner_framework_benchmark.py`
- `output/travelplanner_framework_compare/20260409_144039/langgraph_supervisor/logs/query_006.log`
- `pytest tests/unit/test_travelplanner_langgraph_supervisor.py -q`

## 2026-04-09 — Notebook Docker Build Visibility and Cache Fix

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `7/10`
- `confidence`: `high`
- `scope`: `TravelPlanner comparison notebook setup-cell reliability for Docker-based benchmark startup`

### Outcome
Fixed the principal TravelPlanner comparison notebook so Docker build and run commands stream output live in Jupyter, and repeated runs skip the `travelplanner-smoke` image rebuild when `Dockerfile`, `docker-compose.yml`, and `requirements.txt` are unchanged.

### Reusable Patterns (1-3)
1. In notebook orchestration cells, never hide long-running container build output behind `subprocess.run(capture_output=True)`; stream it live so users can distinguish progress from a hang.
2. Cache Docker build readiness on dependency-level inputs when the runtime source code is bind-mounted into the container; rebuilding the image on every notebook run only wastes wall time.
3. If a notebook depends on external CLIs such as Docker, fail early with a direct PATH/availability message instead of leaving the user at a silent command banner.

### Evidence
- `scripts/create_langgraph_travelplanner_comparison_notebook.py`
- `output/jupyter-notebook/travelplanner-framework-comparison-openrouter-qwen35-9b.ipynb`
- `/opt/miniconda3/bin/python -m py_compile scripts/create_langgraph_travelplanner_comparison_notebook.py`
- `/opt/miniconda3/bin/python - <<'PY' ... compile notebook cells ... PY`

## 2026-04-08 — LangGraph Supervisor TravelPlanner Benchmark Pivot

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `9/10`
- `confidence`: `high`
- `scope`: `Replacement of the principal SwarmAgentic comparison path with a Docker-first LangGraph supervisor baseline for TravelPlanner`

### Outcome
Implemented a reproducible three-arm TravelPlanner comparison path centered on `Solo`, `LangGraph Supervisor`, and `StigmergiAgentic`, with a new LangGraph baseline, a shared Docker-first batch benchmark runner, a regenerated comparison notebook, and thesis-methodology updates that remove SwarmAgentic from the main experimental claim path.

### Reusable Patterns (1-3)
1. When an external baseline becomes operationally non-reproducible, replace it with an in-repo controlled baseline that matches backbone, scorer, split, and output contract before continuing the comparison campaign.
2. Keep benchmark notebooks orchestration-only: route provider-facing execution through one Docker-first batch script and persist `query_XXX.json`, `runs.json`, and `official_eval.json` for resumability and post-hoc analysis.
3. When adding a new orchestration baseline in an existing benchmark domain, reuse the canonical prompt construction, search-payload shaping, normalization, and evaluator paths to avoid scorer drift between methods.

### Evidence
- `adapters/travelplanner/langgraph_supervisor.py`
- `scripts/run_travelplanner_langgraph_query_export.py`
- `scripts/run_travelplanner_framework_benchmark.py`
- `scripts/create_langgraph_travelplanner_comparison_notebook.py`
- `output/jupyter-notebook/travelplanner-framework-comparison-openrouter-qwen35-9b.ipynb`
- `consigne/revue_litterature_v2_DSR.tex`
- `pytest tests/unit/test_travelplanner_langgraph_supervisor.py -q`

## 2026-03-17 — TravelPlanner Official Eval Failure Pattern Analysis

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `8/10`
- `confidence`: `high`
- `scope`: `TravelPlanner validation benchmark result analysis for run 20260317_112916`

### Outcome
Analyzed the official TravelPlanner validation run and isolated a structural regime split: the runtime is viable on single-destination 3-day queries, degrades on 5-day 2-city queries, and collapses to zero delivery on 7-day 3-city queries, with the main bottlenecks shifting from delivery failure to closed-circle and budget/cuisine constraint failures.

### Reusable Patterns (1-3)
1. Segment TravelPlanner benchmark analysis first by `(days, visiting_city_number)` before reading aggregate pass rates; this immediately distinguishes planner-format collapse from constraint-level quality issues.
2. When `final_pass_rate` is low but `delivery_rate` is moderate, inspect `official_detailed` and a few re-evaluated representative queries to separate commonsense route failures from hard-constraint failures.
3. Treat a planner that only searches and injects inventory for `dest` as structurally single-destination, even if prompts mention multi-city travel; benchmark failures on 2-city/3-city tasks will then be expected behavior, not random variance.

### Evidence
- `output/travelplanner_official_full_eval/20260317_112916/official_eval.json`
- `output/travelplanner_official_full_eval/20260317_112916/runs.json`
- Replay of representative queries with `OfficialTravelPlannerEvaluator` (`query_013`, `query_055`, `query_072`, `query_120`, `query_128`, `query_151`)

## 2026-03-17 — Controlled GPT-4o Framework Comparison Notebook for TravelPlanner

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `8/10`
- `confidence`: `high`
- `scope`: `Notebook-driven framework comparison pipeline for StigmergiAgentic vs SwarmAgentic on OpenRouter-routed GPT-4o with the official TravelPlanner scorer`

### Outcome
Prepared a reproducible notebook workflow that compares StigmergiAgentic and SwarmAgentic under the same routed model (`openai/gpt-4o` on OpenRouter) and the same official TravelPlanner scorer, while explicitly documenting the remaining non-controlled dimension that SwarmAgentic performs a PSO optimization phase before evaluation.

### Reusable Patterns (1-3)
1. For cross-framework LLM comparisons, separate `shared evaluation controls` (provider, routed model, split, scorer) from `framework-native steps` (for example PSO training) and state the uncontrolled remainder explicitly in the notebook header.
2. When an external benchmark repo is not directly OpenRouter-compatible, patch only the provider/model adapter layer in a throwaway clone and keep framework logic unchanged.
3. Normalize third-party result files into one local `runs.json` contract before official scoring so downstream analysis, notebooks, and tables can reuse a single scorer path.

### Evidence
- `output/jupyter-notebook/travelplanner-framework-comparison-openrouter-gpt4o.ipynb`
- `scripts/prepare_swarmagentic_openrouter.py`
- `scripts/export_swarmagentic_save_jsonl.py`
- `scripts/convert_swarmagentic_travelplanner_results.py`
- `scripts/render_travelplanner_comparison_table.py`

## 2026-04-01 — SwarmAgentic OpenRouter PSO Resilience Hardening

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `8/10`
- `confidence`: `high`
- `scope`: `TravelPlanner SwarmAgentic OpenRouter adapter hardening for Qwen3.5-9B notebook runs`

### Outcome
Hardened the SwarmAgentic OpenRouter patch path and the Qwen comparison notebook so transient OpenRouter `504` and empty structured-output failures no longer abort the full PSO/evaluation workflow by default, checkpoints are written after each completed PSO iteration, and notebook reruns reuse the existing clone/venv with a lower default concurrency.

### Reusable Patterns (1-3)
1. For long-running third-party LLM optimizers, write resumable checkpoints immediately after each completed evaluation iteration instead of only at the very end of the run.
2. When a hosted provider can return transient `5xx` or null structured outputs, degrade failing tasks to zero-score placeholders and continue the campaign rather than crashing the whole batch.
3. In notebook-driven benchmark reruns, default clone/dependency steps to reuse existing artifacts and lower concurrency first on smaller routed models before increasing throughput.

### Evidence
- `scripts/prepare_swarmagentic_openrouter.py`
- `output/jupyter-notebook/travelplanner-framework-comparison-openrouter-qwen35-9b.ipynb`
- `python -m py_compile scripts/prepare_swarmagentic_openrouter.py`
- `python -m py_compile output/travelplanner_framework_compare/20260401_115306/swarmagentic/repo/travelplanner/swarm/pso.py output/travelplanner_framework_compare/20260401_115306/swarmagentic/repo/travelplanner/swarm/test.py`
- `python -m json.tool output/jupyter-notebook/travelplanner-framework-comparison-openrouter-qwen35-9b.ipynb`

## 2026-03-22 — Opt-In Stigmergic Corrections for V3 Runtime

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `9/10`
- `confidence`: `high`
- `scope`: `Implementation of V4 stigmergic corrections (local sensing, temporal decay, frequentation, emergent conflict resolution, emergence feedback) on top of Sprint 6 V3`

### Outcome
Implemented the full V4 correction plan as opt-in runtime capabilities, preserving backward compatibility while strengthening the framework's stigmergic semantics through local perception, time-aware evaporation, read-traffic reinforcement, and adaptive emergence reuse.

### Reusable Patterns (1-3)
1. When hardening a research runtime against theory-alignment critiques, add new mechanisms behind explicit config gates first, then validate that the legacy path still passes the full suite unchanged.
2. Separate `updated_at` from `last_active_at` when introducing time-based read semantics, so maintenance writes do not accidentally reset temporal dynamics.
3. If agent perception should become observable for later reinforcement, connect read tracking at the orchestrator callback boundary rather than coupling agents directly to store APIs.

### Evidence
- `consigne/V4-correction-plan.md`
- `uv run pytest tests/unit tests/integration -q` (`235 passed`)
- `uv run pytest tests/ -q` (`235 passed`)

## 2026-02-10 — Sprint 1 Environment Foundation

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `9/10`
- `confidence`: `high`
- `scope`: `Sprint 1 environment medium (store, decay, guardrails, tests)`

### Outcome
Implemented a fully testable JSON-based stigmergic medium with POSIX file locking, append-only audit trail, and guardrails enforced by environment primitives.

### Reusable Patterns (1-3)
1. Use a single environment guardrail layer to enforce token budget, retry ceiling, scope lock, and TTL instead of distributing those checks across agents.
2. Persist pheromones as inspectable JSON artifacts and pair every mutation with an append-only JSONL audit event for traceability.
3. Standardize local execution with `uv` + pinned Python minor version and run all validation through `uv run` for reproducible results.

### Evidence
- `uv run pytest tests/test_pheromone_store.py -v` (passed)
- `uv run pytest tests/test_guardrails.py -v` (passed)
- `uv run pytest tests -v -k "pheromone or guardrails"` run twice with stable green results

## 2026-02-11 — Sprint 2 Agent Layer and Deterministic Validation

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `9/10`
- `confidence`: `high`
- `scope`: `Sprint 2 agents, llm client, synthetic fixture repository, unit+integration tests`

### Outcome
Implemented all Sprint 2 units end-to-end: OpenRouter client, four isolated agents, synthetic Python 2 fixture repository, and deterministic handoff tests across the pheromone medium.

### Reusable Patterns (1-3)
1. Keep core orchestration tests deterministic with mocked LLM responses while providing an optional non-blocking live API smoke test.
2. Encode cross-agent coordination only through pheromone transitions (`pending -> in_progress -> transformed -> tested -> validated|needs_review|retry`), never direct agent calls.
3. Store a versioned synthetic legacy-code fixture in `tests/fixtures/` and explicitly exclude it from project-level pytest collection.

### Evidence
- `uv run pytest tests/ -v` (`29 passed, 1 skipped`)
- `uv run pytest tests/test_agents_integration.py -v` (all handoff scenarios passed)

## 2026-02-12 — Sprint 3 Full Loop + Blocking Gate Validation

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `9/10`
- `confidence`: `high`
- `scope`: `Sprint 3 orchestration loop, CLI, metrics, adaptive tester fallback, Docker gate execution`

### Outcome
Implemented and validated the full Sprint 3 runtime with deterministic stop conditions, per-run artifacts, adaptive quality fallback, and successful blocking gates on both synthetic and real repositories (local + Docker).

### Reusable Patterns (1-3)
1. For mixed script/library repos, treat compile-success + usage/optional-dependency import failures as `inconclusive` signals instead of hard failures, while keeping legacy stdlib misses (for example `urllib2`) as related failures.
2. Sanitize LLM outputs before file writes by stripping markdown fence wrappers (including unclosed fences) to avoid test/code corruption on retries.
3. In Docker on macOS, avoid bind-mount churn for actively rewritten repos by using a named volume for the working tree and implementing mountpoint-safe cleanup logic.

### Evidence
- Local: `uv run pytest tests/ -q` (`49 passed, 1 skipped`)
- Local synthetic gate: `metrics/output/run_20260212T170852Z_summary.json` (`success_rate=0.95`)
- Local real gate: `metrics/output/run_20260212T170936Z_summary.json` (`success_rate=0.913043`)
- Docker synthetic gate: `metrics/output/run_20260212T173610Z_summary.json` (`success_rate=0.95`)
- Docker real gate: `metrics/output/run_20260212T173704Z_summary.json` (`success_rate=0.869565`)

## 2026-02-12 — Sprint 3 Patch: Uncapped Output and USD Cost Budget

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `8/10`
- `confidence`: `high`
- `scope`: `LLM client budget model, loop/metrics propagation, CLI budget override`

### Outcome
Removed hard completion capping by default and introduced an optional USD budget control based on OpenRouter model pricing (pre-call estimate) and `usage.cost` (post-call accounting), with cost metrics exported per run.

### Reusable Patterns (1-3)
1. For thinking-heavy LLM workflows, prefer uncapped completion output (`max_tokens` omitted) and control spend with a separate budget mechanism instead of truncation.
2. Combine two budget layers: token ceiling for deterministic guardrails and cost ceiling for monetary governance.
3. Persist cumulative run cost in the same metrics stream as token usage to enable direct cost-quality analysis.

### Evidence
- `uv run pytest tests/ -q` (`60 passed, 1 skipped`)
- `uv run python main.py --repo tests/fixtures/synthetic_py2_repo --config stigmergy/config.yaml --seed 42 --max-ticks 1 --verbose` (`total_cost_usd` present, uncapped request payload)

## 2026-02-12 — Runtime Hard-Disable of `max_tokens` + Docker Image Freshness

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `8/10`
- `confidence`: `high`
- `scope`: `LLM client request payload policy and Docker execution consistency`

### Outcome
Hardened runtime behavior so the client never sends `max_tokens` to OpenRouter (even if configured), preventing accidental output truncation from local configuration drift and stale Docker images.

### Reusable Patterns (1-3)
1. For reasoning-heavy migrations, enforce uncapped completion at client layer instead of trusting config defaults.
2. Keep budget control separate from generation caps (`max_tokens_total`/`max_budget_usd` without per-call output limit).
3. Rebuild Docker image before benchmark/gate runs when runtime policy changes to avoid executing stale logic.

### Evidence
- `uv run pytest tests/test_llm_client.py -q` (`10 passed, 1 skipped`)
- `uv run pytest tests/ -q` (`60 passed, 1 skipped`)
- Docker verbose request payload confirms no `max_tokens` field in `json_data`.

## 2026-02-17 — Sprint 4 Readiness Audit (Tooling vs Benchmark Completion)

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `8/10`
- `confidence`: `high`
- `scope`: `Sprint 4 closure audit (baselines, Pareto, validation gates, thesis-readiness gaps)`

### Outcome
Validated that Sprint 4 code tooling is operational (`baselines/*`, `metrics/pareto.py`) and the full test suite is green, while identifying that thesis-grade Sprint 4 evidence remains incomplete (multi-run fairness benchmark and Pareto methodology alignment).

### Reusable Patterns (1-3)
1. Separate sprint closure into two explicit gates: `tooling complete` (code/tests) and `evidence complete` (benchmark protocol + reproducibility artifacts).
2. Run validation in layered order: target-scope tests, full suite, then static quality gates (`ruff`, `black --check`, `mypy`) to isolate regressions faster.
3. Before Pareto aggregation, verify input summaries contain all compared baselines and enough repetitions per mode; otherwise, treat results as smoke-only.

### Evidence
- `uv run pytest tests/test_loop.py tests/test_metrics.py tests/test_main.py tests/test_pareto.py -v --tb=short` (`17 passed`)
- `uv run pytest tests/ -v --tb=short` (`62 passed, 1 skipped`)
- `uv run pytest tests/ --cov --cov-report=term-missing --no-cov-on-fail` (`TOTAL 86%`)
- `uv run ruff check . --exclude tests/fixtures` (fails: `E402` in `baselines/*`, `F401` in `main.py`)
- `uv run mypy agents/ environment/ stigmergy/ --ignore-missing-imports` (type issues in `environment/pheromone_store.py`, `agents/scout.py`)
- `uv run python metrics/pareto.py --input-dir metrics/output --output /tmp/stigmergiagentic_pareto_check.png --export-json /tmp/stigmergiagentic_pareto_check.json` (`points=13`, `baselines=1`)

## 2026-02-17 — Sprint 4 Closure Implementation (Pareto V2 + 5x3 Benchmark)

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `9/10`
- `confidence`: `high`
- `scope`: `Sprint 4 execution closure (static quality, baseline tests, Pareto CLI V2, bounded 5x3 benchmark, docs sync)`

### Outcome
Completed Sprint 4 closure work end-to-end: static gates green (`ruff`, `black --check`, `mypy`), expanded baseline/Pareto tests, upgraded Pareto tooling (per-run mode + baseline coverage check + CI95 export), and executed a 5x3 bounded benchmark on `docopt/docopt@0.6.2` with refreshed mobile/documentation outputs.

### Reusable Patterns (1-3)
1. Add explicit baseline coverage guards (`--require-baselines`) to analysis tooling so incomplete experiment folders fail fast instead of producing misleading charts.
2. Keep both visualization layers in Pareto workflows: per-run scatter for transparency and aggregate CI95 overlays for comparability.
3. When runtime/cost constraints prevent full unconstrained campaigns, run a bounded protocol with identical caps across configurations and document bounds directly in the results artifact.

### Evidence
- `uv run ruff check . --exclude tests/fixtures` (`All checks passed`)
- `uv run black --check . --exclude '/tests/fixtures/'` (`4985 files would be left unchanged`)
- `uv run mypy agents/ environment/ stigmergy/ --ignore-missing-imports` (`Success: no issues found`)
- `uv run pytest tests/ -v --tb=short` (`72 passed, 1 skipped`)
- `make docker-test` (`72 passed, 1 skipped`)
- Benchmark (5 runs each):
  - `uv run python baselines/single_agent.py ... --max-ticks 1 --max-tokens 5000 --runs 5`
  - `uv run python baselines/sequential.py ... --max-ticks 1 --max-tokens 5000 --runs 5`
  - `for i in 1..5: uv run python main.py ... --max-ticks 1 --max-tokens 5000`
- `uv run python metrics/pareto.py --input-dir metrics/output/sprint4_20260217_benchmark --plot-mode per-run --require-baselines stigmergic,single_agent,sequential --export-json ...` (`points=15`, `baselines=3`)

## 2026-02-17 — Benchmark Stability Hardening (Timeout + Sequential Stage Cap)

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `8/10`
- `confidence`: `medium`
- `scope`: `Runtime stability during repeated baseline benchmarking`

### Outcome
Added explicit OpenRouter request timeout wiring in `LLMClient` and introduced a per-stage action cap in the sequential baseline loop to reduce non-terminating benchmark runs.

### Reusable Patterns (1-3)
1. For repeated LLM benchmark campaigns, set explicit provider request timeouts instead of relying on SDK defaults.
2. Bound nested `while agent.run()` stage loops with configurable action caps to prevent runaway per-tick execution.
3. Validate stability guardrails with focused unit tests before resuming long benchmark batches.

### Evidence
- `uv run pytest tests/test_llm_client.py tests/test_baselines_sequential.py -v --tb=short` (`14 passed, 1 skipped`)
- `uv run ruff check baselines/sequential.py stigmergy/llm_client.py tests/test_baselines_sequential.py tests/test_llm_client.py` (`All checks passed`)

## 2026-02-17 — Unbounded 5x3 Completion (Parallel Isolated Runs + Pareto Final)

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `9/10`
- `confidence`: `high`
- `scope`: `Finalize Sprint 4 evidence batch and close end-of-sprint gates`

### Outcome
Completed the full unbounded benchmark set (`5 x 3` runs) by launching missing runs in parallel from isolated temporary workspaces, then generated final Pareto artifacts and passed the sprint end gate.

### Reusable Patterns (1-3)
1. For concurrent campaign runs, isolate each process in its own copied workspace to avoid collisions on `target_repo`, `.target_repo_clone_tmp`, and `pheromones`.
2. Count completion from `run_*_summary.json` (not manifests) to avoid false-positive progress when runs start but have not finished.
3. After benchmark completion, regenerate Pareto with `--require-baselines` and immediately run `./scripts/sprint_end.sh` to lock both evidence and code-quality gates.

### Evidence
- Final counts in `metrics/output/sprint4_20260217_full`: `{'single_agent': 5, 'sequential': 5, 'stigmergic': 5}`
- `uv run python metrics/pareto.py --input-dir metrics/output/sprint4_20260217_full --plot-mode per-run --require-baselines stigmergic,single_agent,sequential --export-json metrics/output/sprint4_20260217_full/pareto_summary.json`
- `uv run pytest tests/ -v` (`74 passed, 1 skipped`)
- `./scripts/sprint_end.sh` (pass: tests, coverage, lint, format, mypy)

## 2026-02-19 — Sprint 5 Prep: Z.ai `glm-5` Integration

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `8/10`
- `confidence`: `high`
- `scope`: `Provider-aware LLM wiring, config defaults update, provider smoke validation`

### Outcome
Introduced provider-aware LLM routing (`openrouter` and `zai`) with provider-specific API key/base URL resolution, switched Sprint 5 default model to `glm-5` on Z.ai coding endpoint, and validated connectivity with a live smoke call.

### Reusable Patterns (1-3)
1. Centralize provider routing in one client (`provider -> env var + base_url + pricing capability`) instead of scattering provider checks across agents.
2. Keep pricing pre-check optional and provider-gated so token/cost guardrails remain stable even when a provider lacks pricing endpoint integration.
3. Validate provider switches with one deterministic smoke prompt (`Reply with exactly: pong`) before launching full migration loops.

### Evidence
- `uv run pytest tests/test_llm_client.py -q` (`13 passed, 1 skipped`)
- `uv run pytest tests/test_main.py tests/test_loop.py -q` (`12 passed`)
- `uv run python - <<'PY' ... provider='zai', model='glm-5' ...` (`ok=1`, content `pong`)

## 2026-02-19 — Anti-429 Hardening for Z.ai Campaign Runs

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `8/10`
- `confidence`: `high`
- `scope`: `Runtime retry pacing to mitigate provider rate limiting during repeated runs`

### Outcome
Added built-in anti-429 controls to the shared LLM client (inter-call pacing, 429-specific minimum backoff, and retry jitter), then enabled those controls in default config for Sprint 5 Z.ai usage.

### Reusable Patterns (1-3)
1. Combine request pacing (`min_call_interval_seconds`) with retry backoff to reduce bursty provider traffic during agent loops.
2. Treat HTTP 429 separately from generic retryable errors by applying a stronger floor and honoring `Retry-After` when available.
3. Keep anti-rate-limit behavior in the shared LLM client so all orchestration modes inherit it without per-agent patches.

### Evidence
- `uv run pytest tests/test_llm_client.py -q` (`15 passed, 1 skipped`)
- `uv run ruff check stigmergy/llm_client.py tests/test_llm_client.py tests/conftest.py` (`All checks passed`)

## 2026-02-19 — Default Runtime Switch Back to OpenRouter

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `7/10`
- `confidence`: `high`
- `scope`: `Provider default reconfiguration for faster repeated runs`

### Outcome
Switched project defaults back to OpenRouter (`qwen/qwen3-235b-a22b-2507`) and disabled inter-call pacing by default to reduce wall-clock time for benchmark batches, while keeping anti-429 controls available.

### Reusable Patterns (1-3)
1. Keep provider-specific resilience controls configurable so defaults can be tuned quickly per provider behavior.
2. For throughput-focused benchmark phases, disable global pacing and rely on retry/backoff floors only.
3. Validate provider switches immediately with a one-shot smoke call and token accounting check.

### Evidence
- `uv run python - <<'PY' ... provider='openrouter' ...` (`ok=1`, `tokens=24`, `content=pong`)

## 2026-02-19 — GPT-5-nano Trial Batch (5 Stigmergic Runs, No Max Tokens)

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `8/10`
- `confidence`: `high`
- `scope`: `Model A/B trial before Sprint 4 comparison lock`

### Outcome
Executed 5 complete stigmergic runs on `docopt/docopt@0.6.2` using `openai/gpt-5-nano` via OpenRouter with no `--max-tokens`, and generated a curated 5-run Pareto artifact set for clean comparison.

### Reusable Patterns (1-3)
1. When a long sequential batch is interrupted, isolate and re-run the missing runs in parallel workspaces to finish quickly without corrupting outputs.
2. Keep a curated output subset when accidental extra runs are produced, so analysis stays exactly on the requested sample size.
3. Verify model/repo/ref consistency from manifest files for each run before comparing metrics.

### Evidence
- `metrics/output/pre_sprint4_gpt5nano_20260219_stigmergic_5runs_curated` (5 manifests, 5 summaries, 5 ticks CSV)
- `uv run python metrics/pareto.py --input-dir metrics/output/pre_sprint4_gpt5nano_20260219_stigmergic_5runs_curated --output .../pareto.png --plot-mode per-run --export-json .../pareto_summary.json` (`points=5`, `baselines=1`)

## 2026-02-26 — V2 Sprint 1 Core Environment Reset (SQLite WAL)

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `9/10`
- `confidence`: `high`
- `scope`: `Hard reset V0.1 runtime and implement V2 Sprint 1 generic environment core`

### Outcome
Delivered a clean V2 baseline with a generic `Marker` contract, transactional SQLite/WAL `MarkerStore`, append-only JSONL audit, guardrails, strict config validation, and a complete 31-test Sprint 1 unit gate.

### Reusable Patterns (1-3)
1. For architecture resets, remove legacy runtime paths early in a dedicated branch to prevent hybrid coupling and simplify acceptance gates.
2. Use SQLite `WAL` + `BEGIN IMMEDIATE` for coordination state to keep write integrity while preserving concurrent read scalability.
3. Treat audit logging as a first-class write-path invariant (`before/after` per mutation) rather than a post-processing export.

### Evidence
- `uv run pytest tests/unit -v` (`31 passed`)
- `uv run pytest tests/unit/test_marker_store.py -v` (`12 passed`)
- `uv run pytest tests/unit/test_guardrails.py -v` (`6 passed`)

## 2026-02-26 — V2 Sprint Documentation Rule (`documentation/redisgn_v2`)

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `8/10`
- `confidence`: `high`
- `scope`: `Process governance for per-sprint artifact-state documentation`

### Outcome
Established a mandatory sprint-close documentation protocol in `documentation/redisgn_v2`, with a reusable template and a first concrete artifact status document for Sprint 1.

### Reusable Patterns (1-3)
1. Introduce a dedicated sprint-state folder to separate architecture evolution notes from generic construction logs.
2. Enforce one fixed file naming convention (`sprint_XX_artifact.md`) to make cross-sprint retrieval deterministic.
3. Make the protocol executable by embedding it directly in agent instruction files (`AGENTS.md`, `CLAUDE.md`).

### Evidence
- `documentation/redisgn_v2/README.md`
- `documentation/redisgn_v2/sprint_01_artifact.md`
- Rule references added in `AGENTS.md` and `CLAUDE.md`

## 2026-02-26 — Sprint 2 V2 Generic Runtime Closure

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `9/10`
- `confidence`: `high`
- `scope`: `Sprint 2 V2 runtime (agent, pressure, orchestrator, tool contracts, llm client port, unit validation)`

### Outcome
Delivered a generic, testable multi-agent runtime on top of the Sprint 1 marker environment, including asynchronous orchestration with deterministic sync entrypoints, lock-safe conflict resolution, and provider-aware LLM client integration.

### Reusable Patterns (1-3)
1. Keep async orchestration core with a synchronous wrapper for deterministic unit tests and low-friction local validation.
2. Enforce marker-state transitions and budget checks in the environment layer so tools stay domain-focused and side effects remain auditable.
3. Test orchestration deterministically with a mock adapter exposing simple staged tools (`increment/check/finalize`) to validate conflicts, stop conditions, and parallel tick behavior.

### Evidence
- `uv run pytest tests/unit/test_pressure.py tests/unit/test_agent.py tests/unit/test_orchestrator.py tests/unit/test_llm_client.py -q` (`30 passed`)
- `uv run pytest tests/unit -v` (`61 passed`)

## 2026-02-26 — Sprint 3 V2 Infrastructure Tools + Assistant Mode

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `9/10`
- `confidence`: `high`
- `scope`: `Sprint 3 V2 tools layer, assistant adapter, CLI runtime, unit+integration validation`

### Outcome
Implemented Sprint 3 end-to-end by adding reusable infrastructure tools, a sandboxed assistant adapter, and a CLI execution path that runs the stigmergic orchestrator without domain-specific adapters.

### Reusable Patterns (1-3)
1. Keep infrastructure tools under the same `Tool` contract as domain tools so pressure-driven action selection remains uniform across adapters.
2. Enforce workspace safety at the workspace layer (path resolution + size constraints + allowlists), then let tools focus on action semantics.
3. Combine deterministic integration runs (`num_agents=1`, `temperature=0`) with mock LLM outputs to validate full tick-loop behavior without external API coupling.

### Evidence
- `uv run pytest tests/unit -q` (`81 passed`)
- `uv run pytest tests/integration/test_assistant_run.py -q` (`4 passed`)
- `uv run pytest tests/unit tests/integration -q` (`85 passed`)
- `uv run python main.py --adapter assistant --objective "Create a short checklist" --max-ticks 12 --agents 1 --seed 7` (`stop_reason=all_terminal`)

## 2026-03-04 — Assistant Action Eligibility Rework (Execution-First)

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `9/10`
- `confidence`: `high`
- `scope`: `assistant adapter marker seeding, tool eligibility policy, response synthesis, Sprint 3 tests`

### Outcome
Reworked assistant marker/tool eligibility so explicit `eligible_actions` remains optional, while default behavior now enables action selection from marker context (instead of hard-locking to `decompose/think`), and expanded CLI response synthesis to include concrete tool outputs (`last_read`, `last_bash`, `last_write`, `last_search`) alongside reasoning.

### Reusable Patterns (1-3)
1. Treat marker action filters as optional override contracts; when omitted, infer tool eligibility from marker payload prerequisites (`path`, `command`, `query`, `write`) instead of forcing one hardcoded action.
2. Keep `decompose` root-only by default using marker-local context (`decomposed` + `parent_id`) to avoid recursive decomposition loops without adding central orchestration branches.
3. Build assistant final responses from execution artifacts first (file/bash/write/search outputs), then include reasoning text as supporting context.

### Evidence
- `uv run pytest tests/unit -q` (`83 passed`)
- `uv run pytest tests/integration/test_assistant_run.py -q` (`4 passed`)
- `uv run pytest tests/unit/test_assistant_adapter.py tests/unit/test_file_tools.py tests/unit/test_pressure.py tests/integration/test_assistant_run.py -q` (`26 passed`)

## 2026-03-04 — Think-Then-Act Gate + `.env`-Aware CLI

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `9/10`
- `confidence`: `high`
- `scope`: `think/decompose runtime gating, assistant config provider defaults, integration/runtime reliability`

### Outcome
Implemented a think-then-act execution gate: `think` no longer advances generic active subtasks, active subtasks must be progressed by concrete tools, decomposed root markers retain a controlled completion path, and CLI now auto-loads `.env` so API keys used in notebooks are also available in direct `main.py` runs.

### Reusable Patterns (1-3)
1. Prevent plan-only loops by blocking planner actions on active subtasks and requiring concrete tool outputs for `active -> completed` progression.
2. Handle coordinator/root markers as a distinct lifecycle class (decomposed-root exception) to avoid deadlocking orchestration after decomposition.
3. Call `load_dotenv()` at CLI entrypoints to align notebook and shell execution environments for provider credentials.

### Evidence
- `uv run pytest tests/unit/test_think_tool.py tests/integration/test_assistant_run.py -q` (`7 passed`)
- `uv run pytest tests/unit tests/integration/test_assistant_run.py -q` (`92 passed`)
- `uv run pytest tests/unit/test_main_response.py tests/integration/test_assistant_run.py -q` (`6 passed`)

## 2026-03-04 — Emergent Decomposition + LLM-Only Tool Hinting

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `9/10`
- `confidence`: `high`
- `scope`: `assistant decomposition policy, think prompt contract, configurable intensity dynamics, test/integration stabilization`

### Outcome
Removed structural hardcoding that forced planning shape and fallback hints: decomposition no longer enforces a fixed default subtask count, think no longer auto-infers tool hints from heuristics, prompts now expose optional fields dynamically based on declared available tools, and all intensity decrements/floors are configurable from marker settings.

### Reusable Patterns (1-3)
1. Keep `subtask_count` as an optional operator hint, not a required runtime invariant, so decomposition shape can emerge from objective complexity.
2. Prefer strict LLM JSON contracts over local heuristic hint injection when execution eligibility should reflect model intent rather than adapter guesswork.
3. Move marker intensity constants to config keys to tune planning/execution pressure without code edits.

### Evidence
- `uv run pytest tests/unit tests/integration/test_assistant_run.py -v` (`94 passed`)

## 2026-03-04 — Sprint 4 V3 Runtime Overhaul (Structured Async + DAG)

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `9/10`
- `confidence`: `high`
- `scope`: `V3 runtime hardening (typed LLM outputs, async execution, dependency gating, reinforcement, session isolation)`

### Outcome
Implemented Sprint 4 V3 end-to-end with schema-validated async LLM calls, dependency-aware scheduling, reinforcement propagation, session-isolated storage, and expanded test coverage validated at 128 passing tests.

### Reusable Patterns (1-3)
1. Keep sync and async LLM paths side-by-side (`call` + `acall`) to preserve backward compatibility while enabling typed structured-output enforcement in new runtime flows.
2. Treat marker dependencies as first-class runtime constraints (`depends_on` + unblocked filtering) instead of soft conventions in prompts.
3. Pair per-run `session_id` with isolated persistence path (`pheromones/<session_id>/markers.db`) to avoid cross-run contamination during concurrent experiments.

### Evidence
- `uv run pytest tests/unit -q` (`127 passed`)
- `uv run pytest tests/integration/test_assistant_run.py -q` (`4 passed`)
- `uv run pytest tests/unit tests/integration -q` (`131 passed`)
- `uv run pytest tests/unit/test_llm_client.py tests/unit/test_dependency.py tests/unit/test_reinforcement.py -q` (structured async + DAG + reinforcement focus)

## 2026-03-04 — Sprint 5 V3 Memory + Emergence + Lesson Runtime

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `9/10`
- `confidence`: `high`
- `scope`: `agent episodic memory, emergence metrics, lesson marker deposition, heuristic-aware pressure, CLI dashboard`

### Outcome
Implemented Sprint 5 V3 end-to-end with bounded episodic memory in agents, run-level emergence telemetry from tick rows and audit traces, automatic lesson marker deposition on high-quality transitions, heuristic-aware ACO pressure extension, and CLI emergence dashboard integration.

### Reusable Patterns (1-3)
1. Add cognitive extensions at decision boundaries (`perceive_and_decide`/`execute`) by passing contextual payload through decision contracts instead of mutating persistent marker schema.
2. Compute collaboration metrics from append-only audit logs to avoid storage schema churn while still quantifying cross-agent interaction density.
3. Promote high-quality transitions into durable `lesson` markers so reusable coordination knowledge can outlive local agent memory decay.

### Evidence
- `uv run pytest tests/ -v` (`168 passed`)
- `uv run python main.py --adapter assistant --objective "Summarize workspace status" --max-ticks 10 --agents 2` (emergence dashboard shown; JSON includes `emergence`)
- `sqlite3 pheromones/<session_id>/markers.db "SELECT id, marker_type, state, target FROM markers WHERE marker_type='lesson';"` (lesson marker present)

## 2026-03-05 — Sprint 6 V3 TravelPlanner Adapter (DSR Iteration 1)

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `9/10`
- `confidence`: `high`
- `scope`: `TravelPlanner domain adapter implementation + legacy V0.1 cleanup + paper-facing metrics wiring`

### Outcome
Implemented the first application-domain adapter on V3 (`travelplanner`) with CSV/HF workspace integration, deterministic domain search tools, schema-validated itinerary planning, programmatic commonsense/hard validation, CLI adapter dispatch, and end-to-end tests; removed obsolete V0.1 runtime surfaces and legacy tests.

### Reusable Patterns (1-3)
1. Keep domain adapters thin by placing data IO in `workspace`, action semantics in `tools`, and benchmark scoring in `evaluator`, while preserving core runtime contracts unchanged.
2. For benchmark-grade reproducibility, use LLM only for plan generation and keep constraint validation fully programmatic with explicit micro/macro/final metrics.
3. Introduce a domain setup script that verifies both data assets (CSV integrity) and query source availability before runtime execution.

### Evidence
- `uv run pytest tests/unit tests/integration -q` (`204 passed`)
- `uv run pytest tests/ -q` (`209 passed`)
- `uv run python scripts/setup_travelplanner.py --output-dir /tmp/travelplanner_db_check --force` (setup + integrity checks passed)

## 2026-03-06 — OC1-OC5 Alignment Audit (Review vs Plan vs Runtime)

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `8/10`
- `confidence`: `high`
- `scope`: `Thesis-alignment audit of V3 plan against literature review and current runtime evidence`

### Outcome
Produced a repo-backed audit that separates theoretical intent, V3 plan promises, and currently proven V3 capabilities, concluding that the framework is strong on runtime architecture (OC1-OC2) but still only partially validated at thesis scale (OC3-OC5, DSR/FEDS, governance).

### Reusable Patterns (1-3)
1. Audit thesis artifacts against three explicit layers: literature target, implementation plan, and current repo evidence.
2. Treat configured-but-unwired metrics or controls as intentions, not capabilities, until runtime outputs or tests prove them.
3. Separate `runtime complete` from `research validated`; benchmarks, case studies, and expert evaluation must be tracked as independent proof layers.

### Evidence
- `pytest -q` (`209 passed`)
- `documentation/v3_oc1_oc5_alignment_audit.md`
- V3 evidence sources reviewed: Sprint 4-6 ADRs, Sprint 6 artifact note, `core/*`, `adapters/*`, `tests/*`

## 2026-03-06 — Colab Qwen3-14B-AWQ Benchmark Notebook Rebuild

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `7/10`
- `confidence`: `medium`
- `scope`: `Google Colab notebook rebuild for local Qwen3-14B-AWQ benchmarking on Tesla T4`

### Outcome
Created a new Colab-oriented benchmark notebook that replaces brittle vLLM startup assumptions with a cleaner install-restart flow, conservative T4 memory settings, file-backed server logs, and the same latency/throughput plus structured-JSON checks needed for local model viability testing.

### Reusable Patterns (1-3)
1. For Colab notebooks that upgrade `torch` or `vllm`, separate the dependency install into its own restart-triggering section and resume runtime logic only after reconnect.
2. On constrained T4 setups, prefer auto-detected AWQ handling with conservative vLLM settings (`max_model_len`, `max_num_seqs`, `gpu_memory_utilization`) before adding backend or quantization overrides.
3. Persist vLLM startup logs to a file and surface the full tail on health-check timeout so notebook failures expose the real engine cause instead of a generic wrapper exception.

### Evidence
- `notebooks/benchmark_colab_qwen3_14b_t4_clean.ipynb`
- Static validation: notebook JSON parsed successfully and every code cell passed `ast.parse`
- Manual comparison against the failing notebook identified removed risk points: forced `FLASHINFER`, forced `awq_marlin`, truncated startup logs

## 2026-03-06 — TravelPlanner Colab Benchmark Notebook Rebuild

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `8/10`
- `confidence`: `medium`
- `scope`: `Rewrite the Sprint 6 TravelPlanner benchmark notebook for Colab T4 with local vLLM serving and resumable official evaluation`

### Outcome
Rebuilt the TravelPlanner benchmark notebook around the stable Colab T4 procedure: restart-aware environment install, pinned local vLLM stack, temporary local LLM override config, per-query checkpointing, and official TravelPlanner evaluation using the repository runtime instead of a hosted LLM backend.

### Reusable Patterns (1-3)
1. For repo-level Colab benchmarks, separate the notebook into `environment install`, `local model serving`, and `benchmark execution` phases so a runtime restart does not invalidate the run protocol.
2. When a benchmark loop depends on expensive local inference, save a checkpoint after every item instead of every N items to survive Colab disconnects and preemption.
3. For local OpenAI-compatible servers in a repo that expects hosted providers, inject a temporary config override plus a dummy provider API key rather than patching runtime code just for notebook execution.

### Evidence
- `travelplanner-sprint6-benchmark.ipynb`
- Static validation: notebook JSON parsed successfully and every code cell passed `ast.parse`
- Notebook now uses `main.py --query-idx ... --config <local override>` with official TravelPlanner scorer and per-query checkpoint persistence

## 2026-03-06 — Root-Level Colab Qwen3-14B-AWQ Feasibility Notebook

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `7/10`
- `confidence`: `medium`
- `scope`: `Root-level Colab notebook for thesis-facing local feasibility and benchmark credibility assessment`

### Outcome
Created a root-level notebook artifact that answers the thesis-facing question directly by separating minimal viability from repeated stability, exporting environment provenance and failure events, and producing a `GO` / `CONDITIONAL GO` / `NO-GO` verdict for using `Qwen/Qwen3-14B-AWQ` locally on Google Colab Free T4 without OpenRouter.

### Reusable Patterns (1-3)
1. Separate `runs once` from `benchmark credible` by combining a minimal viability suite with a repeated stability campaign on representative prompts.
2. Export benchmark provenance (`packages`, GPU, env overrides, launch command) and failure events together so Colab-session conclusions stay auditable and reproducible.
3. Translate benchmark outcomes into three thesis-use levels (`smoke`, `exploratory`, `primary`) instead of a binary feasibility flag.

### Evidence
- `benchmark_colab_qwen3_14b_t4_clean.ipynb`
- Static validation: notebook JSON parsed successfully and every code cell passed `ast.parse`
- The notebook writes a machine-readable summary to `qwen3_14b_awq_benchmark_results.json` with verdict, rationale, provenance, and repeated-run records

## 2026-03-12 — RunPod Ops Skill for Repo-Level Benchmarking

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `8/10`
- `confidence`: `high`
- `scope`: `Create a repo-local RunPod skill for Pod operations, storage handling, and benchmark execution`

### Outcome
Created a local `runpod-ops` skill that combines official RunPod product constraints with the currently installed `runpodctl` command shape, plus a repo-specific workflow for running `vLLM` and TravelPlanner evaluation on RunPod Pods.

### Reusable Patterns (1-3)
1. For external CLI skills, anchor command syntax to the installed CLI `--help` output when official docs still contain deprecated verbs or outdated flows.
2. Keep infrastructure skills concise in `SKILL.md` and move command maps plus repo runbooks into `references/` files.
3. Separate durable Pod storage and SSH workflows from ad-hoc transfer utilities so benchmark instructions stay reproducible.

### Evidence
- `runpodctl version` -> `2.1.6-400ac40`
- `runpodctl user` exited successfully with local config-based auth
- `.codex/skills/runpod-ops/SKILL.md`
- `.codex/skills/runpod-ops/references/runpodctl.md`
- `.codex/skills/runpod-ops/references/stigmergiagentic-runpod.md`

## 2026-03-12 — Autoresearch Integration Strategy for Research Workflows

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `8/10`
- `confidence`: `medium`
- `scope`: `Integration design for adapting karpathy/autoresearch patterns into the V3 stigmergic runtime`

### Outcome
Mapped `karpathy/autoresearch` to the current V3 runtime as an integration pattern instead of a direct code import. The reusable core is a fixed evaluator plus one mutable artifact plus a keep/discard loop, while thesis-style literature research additionally requires scholarly retrieval, citation grounding, and synthesis scoring.

### Reusable Patterns (1-3)
1. Reuse `autoresearch` as a control-loop pattern, not as a domain implementation: preserve immutable evaluation, mutable artifact iteration, and experiment logging, but swap the metric to a grounded research score.
2. Add research support as a dedicated adapter vertical slice rather than overloading the generic assistant adapter, so tool surface, state machine, and evaluator remain explicit and testable.
3. Feed evaluator-produced `quality_score` back into V3 reinforcement so high-value source chains and synthesis strategies are amplified across ticks.

### Evidence
- External sources reviewed: `https://github.com/karpathy/autoresearch`, `https://raw.githubusercontent.com/karpathy/autoresearch/master/README.md`, `https://raw.githubusercontent.com/karpathy/autoresearch/master/program.md`
- Local integration anchors reviewed: `main.py`, `adapters/base.py`, `adapters/assistant/adapter.py`, `core/environment.py`, `tools/decompose.py`, `tools/web_search.py`, `adapters/travelplanner/evaluator.py`

## 2026-03-13 — Repo-Local Objective Autoresearch Skill

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `8/10`
- `confidence`: `high`
- `scope`: `Create a hybrid repo-local skill for bounded autoresearch-style framework improvement and sourced research loops`

### Outcome
Implemented a repo-local `objective-autoresearch` skill that encodes a goal-locked iterative loop with explicit mode selection (`framework-improvement` vs `objective-research`), fixed evaluator discipline, keep/discard decisions, and bounded failure-stop guardrails.

### Reusable Patterns (1-3)
1. For hybrid strategy skills, keep the top-level `SKILL.md` short and decision-oriented, then push mode-specific procedures into separate `references/` files.
2. When the user wants autonomy without drift, encode autonomy as a fixed loop contract plus immutable evaluator rules and explicit failure-stop thresholds.
3. For repo-local autoresearch workflows, select mode from the final deliverable rather than from intermediate actions such as browsing, brainstorming, or patching.

### Evidence
- `.codex/skills/objective-autoresearch/SKILL.md`
- `.codex/skills/objective-autoresearch/references/framework-mode.md`
- `.codex/skills/objective-autoresearch/references/research-mode.md`
- `.codex/skills/objective-autoresearch/references/evaluator-contracts.md`
- `python /Users/lotfi/.codex/skills/.system/skill-creator/scripts/quick_validate.py .codex/skills/objective-autoresearch` -> `Skill is valid!`

## 2026-03-13 — Simplified Home AGENTS Governance

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `7/10`
- `confidence`: `high`
- `scope`: `Remove the heavy knowledge-governance block from the home-level AGENTS file and keep only lightweight skill-locality guidance`

### Outcome
Simplified `/Users/lotfi/.codex/AGENTS.md` by removing the dedicated `Knowledge Governance` section and replacing it with a short repo-local skill preference under `Skill Hygiene`, preserving the practical rules without the heavier policy framing.

### Reusable Patterns (1-3)
1. When an instruction file becomes noisy, prefer deleting rigid policy sections and preserving only the minimum operational rule that still guides behavior.
2. Keep home-level AGENTS files broad and lightweight; push repository-specific process rules down into repo-local files.
3. For skill systems, a simple "prefer repo-local for repo-specific workflows" rule is often clearer than a full governance section.

### Evidence
- `/Users/lotfi/.codex/AGENTS.md`
- Removed section: `## Knowledge Governance`
- Added guidance under `## Skill Hygiene` for repo-local skills

## 2026-03-13 — RunPod TravelPlanner Repo-Local Workflow

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `8/10`
- `confidence`: `high`
- `scope`: `Repo-local RunPod workflow for provisioning a Pod, bootstrapping the repo, running the TravelPlanner smoke flow, and retrieving artifacts`

### Outcome
Implemented a repo-local RunPod workflow composed of one operational guide plus four shell scripts that cover local pod creation, on-pod repository bootstrap, TravelPlanner smoke execution, and artifact packaging around the current `runpodctl 2.1.6` command shape.

### Reusable Patterns (1-3)
1. For remote pod runs, treat a pushed Git ref as the only source of truth and bootstrap empty machines from a raw GitHub script before cloning the full repository.
2. Split remote execution into four phases with separate scripts: local pod creation, on-pod bootstrap, in-repo smoke run, and artifact packaging/transfer.
3. Prefer environment-variable secrets and `runpodctl send/receive` artifact handoff over syncing an entire local workspace to the pod.

### Evidence
- `documentation/runpod_travelplanner_workflow.md`
- `scripts/runpod/create_travelplanner_pod.sh`
- `scripts/runpod/bootstrap_travelplanner_repo.sh`
- `scripts/runpod/run_travelplanner_smoke.sh`
- `scripts/runpod/package_artifacts.sh`
- `bash -n scripts/runpod/create_travelplanner_pod.sh scripts/runpod/bootstrap_travelplanner_repo.sh scripts/runpod/run_travelplanner_smoke.sh scripts/runpod/package_artifacts.sh`
- `uv run pytest tests/integration/test_travelplanner.py -q` (`5 passed`)
- `uv run python scripts/setup_travelplanner.py --output-dir /tmp/travelplanner_runpod_impl_check --force`
- `REPO_DIR=/Users/lotfi/Documents/EMLV/Memoire/StigmergiAgentic ARCHIVE_PATH=/tmp/travelplanner_runpod_artifacts_test.tgz bash scripts/runpod/package_artifacts.sh`

## 2026-03-13 — OpenRouter 9B Baseline Reset and Repo Cleanup

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `8/10`
- `confidence`: `high`
- `scope`: `Reset the checked-in runtime baseline to OpenRouter qwen/qwen3.5-9b, add verifiable CLI metadata, replace the pod-specific smoke entrypoint with a local TravelPlanner smoke script, and remove workflow detours from the main repo path`

### Outcome
Reset the default runtime path to `OpenRouter -> qwen/qwen3.5-9b`, aligned test fixtures and LLM fallback defaults, exposed `llm_provider` and `llm_model` in the CLI JSON summary, added a local `scripts/run_travelplanner_smoke.sh` verifier, and removed benchmark notebooks, repo-local infra skills, RunPod workflow artifacts, and leftover session scratch files from the standard repository surface. Final hardening for the live TravelPlanner path included compacting the itinerary prompt, injecting restaurant candidates from workspace data instead of raw `reference_information`, restoring bounded `max_response_tokens`, disabling OpenRouter reasoning for strict JSON calls, and coercing nullable LLM string fields so the end-to-end smoke completed successfully.

### Reusable Patterns (1-3)
1. Keep exactly one checked-in hosted LLM baseline across config, runtime fallbacks, and test fixtures; move alternate backends and experiments into transient scripts or notebooks.
2. For strict JSON tasks on OpenRouter reasoning models, pass `reasoning` through `extra_body`, set `effort: "none"` for the runtime path, cap `max_response_tokens`, and tolerate nullable string fields at the schema edge.
3. Keep benchmark prompts compact and domain-scoped: prefer workspace-backed slices such as restaurant/flight/hotel records over raw dataset blobs like `reference_information`.

### Evidence
- `config/default.yaml`
- `llm/client.py`
- `main.py`
- `scripts/run_travelplanner_smoke.sh`
- `tests/conftest.py`
- `tests/unit/test_llm_client.py`
- `tests/unit/test_main_summary.py`
- `tests/unit/test_schemas.py`
- `uv run pytest tests/unit/test_llm_client.py tests/unit/test_main_summary.py tests/unit/test_travelplanner_tools.py tests/unit/test_travelplanner_adapter.py tests/unit/test_travelplanner_evaluator.py tests/integration/test_travelplanner.py -q` -> `43 passed`
- `uv run pytest tests/ -q` -> `216 passed`
- `bash -n scripts/run_travelplanner_smoke.sh`
- `QUERY_IDX=0 OBJECTIVE='Query 0' bash scripts/run_travelplanner_smoke.sh` -> summary JSON emitted with `llm_provider=openrouter`, `llm_model=qwen/qwen3.5-9b`

## 2026-03-17 — TravelPlanner Live-Path Failure Audit for Query 0

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `7/10`
- `confidence`: `high`
- `scope`: `Audit the latest live OpenRouter smoke run on Query 0 to identify the next highest-leverage fixes for raising official TravelPlanner pass rate`

### Outcome
The latest smoke run completes end-to-end but fails official evaluation because the generated plan is not aligned with the exact string semantics expected by the upstream scorer. The two live commonsense failures for Query 0 are `is_valid_information_in_current_city` and `is_valid_information_in_sandbox`: the model emits a bare `transportation="Flight"` instead of a route-bearing transport string, and it chooses an accommodation that exists in the raw CSV but is excluded from the upstream evaluator inventory after `dropna()`. A second structural gap is that the planner only searches the outbound flight leg and never exposes return-leg or ground-transport options, even though the official task expects a closed-circle trip from origin to destination and back. The current replan loop is also too lossy because it feeds only failed constraint keys back to the planner, not the official error messages that explain what exact field formatting or grounding must be fixed.

### Reusable Patterns (1-3)
1. For scorer-backed benchmarks, align retrieval inventories with the scorer's own filtered dataset view; "present in source CSV" is not enough if the official evaluator applies additional filtering such as `dropna()`.
2. When an evaluator parses fields by literal substrings, feed the model canonical field templates and the exact candidate strings it should copy instead of relying on high-level natural-language guidance.
3. Replan loops should carry scorer messages, not only constraint IDs, whenever the evaluator exposes concrete failure reasons that can be repaired in the next generation pass.

### Evidence
- `output/travelplanner_smoke/travelplanner_query0_20260313_174033.json`
- `output/travelplanner_smoke/travelplanner_query0_20260313_174033.log`
- `adapters/travelplanner/tools.py`
- `adapters/travelplanner/adapter.py`
- `adapters/travelplanner/workspace.py`
- `third_party/travelplanner_official/evaluation/commonsense_constraint.py`
- `third_party/travelplanner_official/tools/accommodations/apis.py`
- `python - <<'PY' ... load_dataset('osunlp/TravelPlanner', 'validation', split='validation[:1]')[0] ... PY` -> Query 0 is `Washington -> Myrtle Beach`, 3 days, budget `1400`
- `python - <<'PY' ... OfficialTravelPlannerEvaluator(...).evaluate_plan(...) ... PY` -> `is_valid_information_in_current_city=false`, `is_valid_information_in_sandbox=false`
- `python - <<'PY' ... commonsense_constraint.is_valid_information_in_sandbox(...) ... PY` -> `(False, 'The accommodation in day 1 is invalid in the sandbox.')`
- `python - <<'PY' ... Accommodations().data ... PY` -> official accommodation inventory excludes `Private sunny room with private bathroom&entrance, Myrtle Beach`

## 2026-03-17 — Dockerized TravelPlanner Benchmark Validation Baseline

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `8/10`
- `confidence`: `high`
- `scope`: `Move the TravelPlanner smoke path from host-local execution to Docker Compose so benchmark evidence matches the repository's containerized validation contract`

### Outcome
The TravelPlanner smoke entrypoint now delegates to Docker Compose by default and runs the integration test plus live OpenRouter objective inside the repository container instead of on the host shell. This keeps benchmark validation aligned with the repo's Docker baseline and removes ambiguity about whether `.env`, Python dependencies, and runtime behavior came from the workstation or from the reproducible container image. The containerized smoke reproduced the same functional result as the prior host run: integration passes, the OpenRouter path completes end-to-end, and `final_pass_rate` remains `0.0`, which confirms that the remaining work is framework quality on scorer semantics rather than host-environment drift.

### Reusable Patterns (1-3)
1. For benchmark evidence, make the top-level smoke script enter Docker first and only execute the workflow directly once inside the container.
2. When a Docker runner image exposes the project virtualenv on `PATH`, container scripts should call `python` and `pytest` directly instead of assuming host tools like `uv` exist in the runtime image.
3. If benchmark artifacts must survive the run, bind-mount the repository into the smoke service so logs, outputs, and the current working tree stay synchronized without image rebuild confusion.

### Evidence
- `docker-compose.yml`
- `scripts/run_travelplanner_smoke.sh`
- `bash -n scripts/run_travelplanner_smoke.sh`
- `docker compose config`
- `docker version --format '{{.Server.Version}}'` -> `29.1.3`
- `docker compose run --rm travelplanner-smoke python --version` -> `Python 3.11.14`
- `docker compose run --rm travelplanner-smoke pytest --version` -> `pytest 9.0.2`
- `QUERY_IDX=0 OBJECTIVE='Query 0' bash scripts/run_travelplanner_smoke.sh` -> containerized smoke completed with `llm_provider=openrouter`, `llm_model=qwen/qwen3.5-9b`, `final_pass_rate=0.0`

## 2026-03-17 — TravelPlanner Scorer-Grounded Planning Loop Passes Query 0

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `9/10`
- `confidence`: `high`
- `scope`: `Upgrade the TravelPlanner adapter and planner loop so scorer-facing outputs are grounded in benchmark search data, replay official failure messages during replanning, and validate the result through the Docker benchmark path`

### Outcome
The TravelPlanner adapter now exposes both outbound and return route options, adds explicit ground-transport and restaurant search tasks, aligns search inventories with the official sandbox view, and normalizes planner outputs into scorer-facing canonical strings. The validation loop now persists official error messages and feeds them back into replanning instead of only constraint IDs. On top of that, hotel candidates shown to the planner are filtered by stay feasibility and occupancy constraints, and the prompt explicitly enforces exact day-count and closed-circle requirements. With those framework-level changes, the Dockerized OpenRouter smoke for `Query 0` moved from partial commonsense success to a full official pass: `commonsense_micro=1.0`, `hard_constraint_micro=1.0`, and `final_pass_rate=1.0`.

### Reusable Patterns (1-3)
1. When a benchmark scorer validates literal field syntax, normalize planner outputs against tool-grounded canonical options instead of trusting raw free-form text.
2. Surface route legs and alternative transport modes as explicit search tasks in the DAG when itinerary correctness depends on them; do not hide critical benchmark context inside one monolithic prompt blob.
3. Use scorer messages to drive replanning and prune infeasible accommodation candidates by declared trip constraints before generation when those constraints are already available in the task state.

### Evidence
- `adapters/travelplanner/adapter.py`
- `adapters/travelplanner/tools.py`
- `adapters/travelplanner/workspace.py`
- `adapters/travelplanner/evaluator.py`
- `third_party/travelplanner_official/runner.py`
- `tests/unit/test_travelplanner_workspace.py`
- `tests/unit/test_travelplanner_adapter.py`
- `tests/unit/test_travelplanner_tools.py`
- `tests/unit/test_travelplanner_evaluator.py`
- `uv run pytest tests/ -q` -> `222 passed`
- `QUERY_IDX=0 OBJECTIVE='Query 0' bash scripts/run_travelplanner_smoke.sh` -> Docker smoke completed with `final_pass_rate=1.0`
- `output/travelplanner_smoke/travelplanner_query0_20260317_102020.json`

## 2026-03-17 — Dockerized TravelPlanner Full-Eval Notebook Driver

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `7/10`
- `confidence`: `high`
- `scope`: `Add a Jupyter notebook that launches the full official TravelPlanner evaluation through Docker, checkpoints one artifact per query, and runs the official scorer on the aggregated run set`

### Outcome
The repository now includes a notebook driver at `output/jupyter-notebook/travelplanner-official-full-eval.ipynb` that orchestrates the full official TravelPlanner validation campaign without moving benchmark execution out of Docker. The notebook builds or reuses the `travelplanner-smoke` image, prepares the database, counts split size, runs queries one by one through `scripts/run_travelplanner_query_export.py`, checkpoints each query JSON into a resumable `runs.json`, and finally launches `scripts/eval_travelplanner_official.py` on the complete run set. The notebook was validated by compiling every code cell successfully and by executing its setup and dataset-count path, which resolved the official validation split size to `180`.

### Reusable Patterns (1-3)
1. For long-running benchmark notebooks, keep the notebook as a driver and inspection surface only; dispatch actual benchmark execution into the same Docker service used by the official scripted path.
2. Persist one structured JSON per query plus an aggregate `runs.json` checkpoint so interrupted benchmark campaigns can resume without rerunning completed queries.
3. Run the official scorer as a separate final container step against aggregated predictions so generation, checkpointing, and evaluation remain reproducible and inspectable.

### Evidence
- `output/jupyter-notebook/travelplanner-official-full-eval.ipynb`
- `scripts/run_travelplanner_query_export.py`
- `scripts/eval_travelplanner_official.py`
- `python - <<'PY' ... ast.parse(...) ... PY` -> all notebook code cells compiled successfully
- `python - <<'PY' ... exec cells 2,3 ... PY` -> notebook helper/config cells executed successfully
- `python - <<'PY' ... exec cell 4 with BUILD_IMAGE=False PREPARE_DATA=False MAX_QUERIES=1 ... PY` -> Docker dataset count succeeded with `total_queries_in_split=180`

## 2026-03-17 — Docker Script Entrypoints Need Explicit Repo Root Imports

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `6/10`
- `confidence`: `high`
- `scope`: `Fix the notebook-driven full evaluation path after every query failed with runtime import errors inside Docker`

### Outcome
The full-evaluation notebook had recorded `180` runtime failures because each containerized query invocation executed `python /app/scripts/run_travelplanner_query_export.py`, which put `/app/scripts` on `sys.path` instead of the repository root and broke imports like `from core.environment import Environment`. The export script now inserts `REPO_ROOT` into `sys.path` before importing project modules, matching the robustness already used by the official evaluation script. After the fix, the same Docker entrypoint succeeds for `--help` and for a minimal `Query 0` export run, which returns structured JSON with `status="ok"` instead of exiting with `ModuleNotFoundError`.

### Reusable Patterns (1-3)
1. Any repo script meant to run as `python /abs/path/to/script.py` inside Docker should prepend the repository root to `sys.path` before importing local packages.
2. When a resumable benchmark notebook marks failed queries as checkpointed, diagnose the first per-query log before rerunning the whole split; uniform failures often indicate an entrypoint bug, not model quality.
3. Validate Docker benchmark entrypoints with one cheap `--help` run plus one minimal real invocation before launching the full split campaign.

### Evidence
- `scripts/run_travelplanner_query_export.py`
- `output/travelplanner_official_full_eval/20260317_112022/queries/query_000.log` -> `ModuleNotFoundError: No module named 'core'`
- `python -m py_compile scripts/run_travelplanner_query_export.py`
- `docker compose run --rm travelplanner-smoke python /app/scripts/run_travelplanner_query_export.py --help`
- `docker compose run --rm travelplanner-smoke python /app/scripts/run_travelplanner_query_export.py --objective 'Query 0' --query-idx 0 --seed 42 --max-ticks 1` -> exits `0` and emits structured JSON

## 2026-03-22 — Controlled Qwen TravelPlanner Framework Comparison Notebook

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `8/10`
- `confidence`: `high`
- `scope`: `Add a reproducible notebook to compare solo Qwen, SwarmAgentic, and StigmergiAgentic on TravelPlanner with the same OpenRouter model and the same official scorer`

### Outcome
The repository now includes a controlled comparison notebook at `output/jupyter-notebook/travelplanner-framework-comparison-openrouter-qwen35-9b.ipynb` that runs three benchmark arms on the same routed model `qwen/qwen3.5-9b`: a solo baseline, SwarmAgentic, and StigmergiAgentic. The notebook reuses the local official scorer, writes one output subtree per method, and renders a final comparison table after evaluation. To support this protocol, the repo now also includes a solo TravelPlanner export runner plus small interoperability scripts that patch a cloned SwarmAgentic checkout for OpenRouter, normalize its saved state/results, and convert them into the local scorer format. The notebook and all helper scripts were validated by compiling every code cell and every Python entrypoint successfully.

### Reusable Patterns (1-3)
1. For framework comparisons, add a solo-model arm alongside agentic systems so gains can be attributed to orchestration rather than the hosted model alone.
2. When reusing an external benchmark repo, keep compatibility glue outside the main runtime: patch the cloned repo in-place, then convert its artifacts into one local scorer format.
3. Store each method's official evaluation JSON under a method-specific subtree and render the final table from those scorer outputs rather than from raw generation logs.

### Evidence
- `output/jupyter-notebook/travelplanner-framework-comparison-openrouter-qwen35-9b.ipynb`
- `scripts/run_travelplanner_solo_query_export.py`
- `scripts/prepare_swarmagentic_openrouter.py`
- `scripts/export_swarmagentic_save_jsonl.py`
- `scripts/convert_swarmagentic_travelplanner_results.py`
- `scripts/render_travelplanner_comparison_table.py`
- `python - <<'PY' ... compile(code_cell_source, ...) ... PY` -> all notebook code cells compiled successfully
- `python -m py_compile scripts/run_travelplanner_solo_query_export.py scripts/prepare_swarmagentic_openrouter.py scripts/export_swarmagentic_save_jsonl.py scripts/convert_swarmagentic_travelplanner_results.py scripts/render_travelplanner_comparison_table.py`

## 2026-04-02 — TravelPlanner Framework Comparison Review Hygiene

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `7/10`
- `confidence`: `high`
- `scope`: `Audit the scientific validity of the solo-versus-StigmergiAgentic TravelPlanner comparison notebook before using it in thesis reporting`

### Outcome
The persisted run `output/travelplanner_framework_compare/20260326_132646` is internally consistent for the two completed arms and confirms that StigmergiAgentic improves `final_pass_rate` from `6/180` to `18/180` on the same validation queries with the same official scorer. The review also found three reporting risks that matter scientifically: the notebook output mixes multiple `RUN_TAG` values from different executions, the current evidence is single-run and therefore lacks variance estimates for a stochastic LLM setting, and the Swarm interoperability script changes more than provider compatibility, so any future three-way claim must either disclose a patched variant explicitly or narrow the comparison claim.

### Reusable Patterns (1-3)
1. Treat benchmark notebooks as publishable artifacts only after rerendering them from one clean run tag; mixed historical cell outputs break reproducibility even when the underlying JSON files are correct.
2. For framework comparisons on stochastic LLM benchmarks, report paired per-query results plus cost/token deltas and at least one uncertainty estimate; aggregate pass rates alone are too weak for thesis-level claims.
3. When adapting an external baseline, any patch that changes retries, exception handling, checkpointing, or optimizer control flow must be described as a behavioral fork, not as a pure compatibility shim.

### Evidence
- `output/jupyter-notebook/travelplanner-framework-comparison-openrouter-qwen35-9b.ipynb`
- `output/travelplanner_framework_compare/20260326_132646/solo/official_eval.json`
- `output/travelplanner_framework_compare/20260326_132646/stigmergiagentic/official_eval.json`
- `output/travelplanner_framework_compare/20260326_132646/solo/runs.json`
- `output/travelplanner_framework_compare/20260326_132646/stigmergiagentic/runs.json`
- `python - <<'PY' ... paired comparison over runs.json ... PY` -> `final_pass` improved on 13 queries, degraded on 1, exact McNemar `p=0.0018310546875`
- `python - <<'PY' ... aggregate tokens/cost from runs.json ... PY` -> StigmergiAgentic used about `4.03x` tokens and `4.14x` cost versus the solo arm

## 2026-04-02 - Fair SwarmAgentic Qwen Benchmark Orchestration

- `repo_slug`: `stigmergiagentic-33b989`
- `type`: `implementation`
- `area`: `benchmarking`
- `summary`: `Refactored the Qwen TravelPlanner comparison notebook so SwarmAgentic runs through a dedicated orchestrator script with preflight/pilot/full modes, explicit infra-vs-framework failure statuses, mode-specific artifacts, and a separate non-comparable paper-context note.`
- `impact_score`: `8/10`
- `confidence`: `high`
- `scope`: `Stabilize the thesis benchmark workflow around qwen/qwen3.5-9b without mixing provider outages into framework scores`

### Outcome
The notebook now delegates SwarmAgentic execution to `scripts/run_swarmagentic_benchmark.py`, which writes `benchmark_status.json`, `reproducibility.md`, `context.md`, mode-specific `runs.json`, and `official_eval.json` when available. The same change also extends `scripts/eval_travelplanner_official.py` with a subset-aware scorer for pilot runs, and switches notebook-local repo scripts from `uv run` to `python` so the benchmark no longer depends on a broken project `.venv` for solo/StigmergiAgentic/offline scoring steps.

### Reusable Patterns (1-3)
1. Keep benchmark notebooks as orchestration surfaces only; move fragile multi-phase baseline execution into versioned Python scripts that emit explicit status and artifact files.
2. Separate `infra_failure` from `framework_failure` in LLM benchmark runs so provider outages do not get silently converted into model or framework score regressions.
3. When a project `.venv` becomes unreliable, route notebook-local scripts through the known-good interpreter and reserve isolated virtualenvs only for external cloned baselines that genuinely need them.

### Evidence
- `scripts/run_swarmagentic_benchmark.py`
- `scripts/eval_travelplanner_official.py`
- `scripts/update_qwen35_benchmark_notebook.py`
- `output/jupyter-notebook/travelplanner-framework-comparison-openrouter-qwen35-9b.ipynb`
- `python -m py_compile scripts/run_swarmagentic_benchmark.py scripts/eval_travelplanner_official.py scripts/update_qwen35_benchmark_notebook.py scripts/prepare_swarmagentic_openrouter.py`
- `python -m json.tool output/jupyter-notebook/travelplanner-framework-comparison-openrouter-qwen35-9b.ipynb >/dev/null`
- `python - <<'PY' ... compile notebook cells 3,5,9,11,13,15 ... PY`
- `python scripts/eval_travelplanner_official.py --runs-json <tmp> --database-root data/travelplanner/database --split validation --start-index 0 --end-index 1`

## 2026-04-03 - Dedicated SwarmAgentic Full Scientific Notebook

- `repo_slug`: `stigmergiagentic-33b989`
- `type`: `implementation`
- `area`: `benchmarking`
- `summary`: `Created a standalone notebook dedicated to a strict full SwarmAgentic benchmark against the already-completed Solo and StigmergiAgentic reference runs, with official-score comparison and paired final-pass analysis.`
- `impact_score`: `7/10`
- `confidence`: `high`
- `scope`: `Give thesis work a baseline-only notebook that runs Swarm full evaluation without reusing the heavier three-arm orchestration notebook`

### Outcome
The new notebook `travelplanner-swarmagentic-full-scientific-comparison-openrouter-qwen35-9b.ipynb` runs only the SwarmAgentic full benchmark, blocks the final scientific comparison when Swarm ends in infra/framework failure, loads the completed reference artifacts from run `20260326_132646` by default, and renders both the official aggregate table and paired final-pass comparisons against Solo and StigmergiAgentic.

### Reusable Patterns (1-3)
1. When one baseline is the unstable part of a comparison campaign, give it a dedicated notebook instead of forcing every rerun through a single all-arms orchestration notebook.
2. Default strict comparison notebooks to known-good reference artifact paths, but keep those paths overridable by environment variable so the notebook stays reusable across runs.
3. For thesis-grade reruns, combine official aggregate metrics with paired per-query final-pass comparisons in the same notebook so reproducibility and comparative significance are visible together.

### Evidence
- `scripts/create_swarmagentic_full_scientific_notebook.py`
- `output/jupyter-notebook/travelplanner-swarmagentic-full-scientific-comparison-openrouter-qwen35-9b.ipynb`
- `output/travelplanner_framework_compare/20260326_132646/solo/official_eval.json`
- `output/travelplanner_framework_compare/20260326_132646/stigmergiagentic/official_eval.json`
- `output/travelplanner_framework_compare/20260326_132646/solo/runs.json`
- `output/travelplanner_framework_compare/20260326_132646/stigmergiagentic/runs.json`
- `python -m py_compile scripts/create_swarmagentic_full_scientific_notebook.py`
- `python -m json.tool output/jupyter-notebook/travelplanner-swarmagentic-full-scientific-comparison-openrouter-qwen35-9b.ipynb >/dev/null`
- `python - <<'PY' ... compile notebook code cells 2-10 ... PY`

## 2026-04-07 - Notebook Interpreter Auto-Selection

- `repo_slug`: `stigmergiagentic-33b989`
- `type`: `bugfix`
- `area`: `benchmarking`
- `summary`: `Hardened the dedicated SwarmAgentic scientific notebook so it auto-selects a Python interpreter that can import repo-required modules like datasets, instead of assuming bare shell python is usable.`
- `impact_score`: `6/10`
- `confidence`: `high`
- `scope`: `Prevent setup failures when Jupyter/kernel python and shell python diverge`

### Outcome
The notebook generator now emits a helper that probes several Python candidates (`sys.executable`, repo `.venv`, Miniconda, `/usr/bin/python3`) and picks the first interpreter that can import `datasets`, `yaml`, and `pydantic`. The generated notebook then uses `REPO_PYTHON` for `setup_travelplanner.py`, dataset counting, Swarm benchmark orchestration, and comparison-table rendering.

### Reusable Patterns (1-3)
1. In notebooks that shell out to repository scripts, resolve the actual working interpreter explicitly instead of calling `python` by name.
2. When the notebook depends on third-party data tooling, test the interpreter against required imports up front and fail early with a precise error.
3. Use the selected interpreter consistently for every local script in the notebook to avoid mixed-environment drift across cells.

### Evidence
- `scripts/create_swarmagentic_full_scientific_notebook.py`
- `output/jupyter-notebook/travelplanner-swarmagentic-full-scientific-comparison-openrouter-qwen35-9b.ipynb`
- `python - <<'PY' ... import datasets,yaml,pydantic ... PY`
- `python - <<'PY' ... inspect notebook cells 2,6,7,8 for REPO_PYTHON ... PY`

## 2026-04-07 — SwarmAgentic Benchmark Watchdog and Live Monitoring

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `8/10`
- `confidence`: `high`
- `scope`: `SwarmAgentic TravelPlanner benchmark observability hardening for Qwen/OpenRouter full scientific runs`

### Outcome
Added explicit runtime observability to the SwarmAgentic comparison path: the benchmark runner now emits heartbeats, snapshots watched artifact paths, writes a live monitor JSON, kills stalled train/eval phases after configurable inactivity, refreshes stale clones when the local patch revision changes, and the patched upstream `pso.py` / `test.py` now print step-level progress so notebook runs no longer appear silently frozen.

### Reusable Patterns (1-3)
1. For long-running third-party LLM baselines, pair provider retries with an outer watchdog based on `child output or artifact movement`, not only subprocess liveness.
2. Version local patches to external benchmark clones with a small revision file and automatically refresh clones when the patch revision changes, so new reliability fixes are actually applied.
3. Surface benchmark observability in two layers: live stdout heartbeats for notebook usability and file-backed monitor artifacts (`live_monitor.json`, `heartbeat.log`) for post-mortem debugging.

### Evidence
- `scripts/run_swarmagentic_benchmark.py`
- `scripts/prepare_swarmagentic_openrouter.py`
- `scripts/create_swarmagentic_full_scientific_notebook.py`
- `output/jupyter-notebook/travelplanner-swarmagentic-full-scientific-comparison-openrouter-qwen35-9b.ipynb`
- `python -m py_compile scripts/run_swarmagentic_benchmark.py scripts/prepare_swarmagentic_openrouter.py scripts/create_swarmagentic_full_scientific_notebook.py`
- Fresh upstream smoke patch on `/private/tmp/swarmagentic_patch_test.TpvCDT/repo` with `python -m py_compile /tmp/swarmagentic_patch_test.TpvCDT/repo/travelplanner/swarm/pso.py /tmp/swarmagentic_patch_test.TpvCDT/repo/travelplanner/swarm/test.py`

## 2026-04-09 — TravelPlanner Organization-Philosophy Scientific Pack

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `9/10`
- `confidence`: `high`
- `scope`: `Replace named-framework comparison with a publication-oriented organization-philosophy benchmark on TravelPlanner`

### Outcome
Added a new scientific benchmarking path for TravelPlanner that evaluates six organization philosophies under the same provider/model/scorer contract, orchestrates preflight/pilot/full gates across three seeds, and produces a reusable paper pack with main tables, paired final-pass statistics, reproducibility reporting, threats to validity, and a DSR Episode 1 summary. The repo now includes controlled baselines for direct solo, CoT solo, self-refine solo, and centralized planner-executor, alongside the existing LangGraph supervisor and StigmergiAgentic arms.

### Reusable Patterns (1-3)
1. When the scientific claim targets coordination philosophy rather than vendor tooling, benchmark named implementations only as backends and keep the public protocol framed around organizational forms.
2. Split large benchmark studies into two repository scripts: one for run-matrix orchestration with gating/status taxonomy and one for analysis-pack generation from persisted artifacts.
3. Treat publishable notebooks as Markdown-first orchestration surfaces that trigger repo scripts and display generated artifacts, not as places where the core experimental logic lives inline.

### Evidence
- `adapters/travelplanner/scientific_baselines.py`
- `scripts/run_travelplanner_scientific_study.py`
- `scripts/build_travelplanner_scientific_pack.py`
- `scripts/create_travelplanner_organization_scientific_notebook.py`
- `output/jupyter-notebook/travelplanner-organization-philosophy-scientific-comparison-openrouter-qwen35-9b.ipynb`
- `documentation/travelplanner_organization_scientific_protocol.md`
- `pytest tests/unit/test_travelplanner_scientific_baselines.py -q`
- `pytest tests/unit/test_travelplanner_langgraph_supervisor.py -q`

## 2026-04-09 — TravelPlanner Official Evaluator Path Hardening

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `7/10`
- `confidence`: `high`
- `scope`: `Fix LangGraph benchmark crashes caused by stale official-eval database symlinks and runtime relative-path lookups`

### Outcome
Hardened the subprocess bridge to the upstream TravelPlanner evaluator so query-level validation no longer crashes when the repo-global `third_party/travelplanner_official/database` symlink points to a stale location or when upstream modules open `../database/...` files at runtime outside the expected working directory. The runner now recreates stale symlinks safely, re-enters the `evaluation/` directory for the sensitive runtime calls, and is covered by a regression test that poisons the symlink before evaluation.

### Reusable Patterns (1-3)
1. When vendoring evaluation code that relies on relative paths, wrap every runtime entrypoint that performs file IO in a temporary working-directory context instead of fixing imports only.
2. Treat repo-global symlinks used by subprocess bridges as mutable state: validate the target each invocation and recreate stale or broken links before executing third-party code.
3. Add regression tests that deliberately corrupt integration state first, then assert the bridge repairs it automatically, so long-running benchmarks do not rediscover the same failure hours later.

### Evidence
- `third_party/travelplanner_official/runner.py`
- `tests/unit/test_travelplanner_evaluator.py`
- `python -m py_compile third_party/travelplanner_official/runner.py`
- `pytest tests/unit/test_travelplanner_evaluator.py -q`
- `pytest tests/unit/test_travelplanner_langgraph_supervisor.py -q`

## 2026-04-10 — Non-Invasive Benchmark Progress Inspection

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `4/10`
- `confidence`: `high`
- `scope`: `Read long-running TravelPlanner study progress and partial results without perturbing the active Docker benchmark`

### Outcome
Confirmed that the active scientific study can be monitored safely by reading `scientific_pack/run_registry.csv`, per-arm `official_eval.json`, and the newest `queries/query_XXX.json` timestamps instead of attaching to the subprocess or touching notebook state. This surfaced complete `solo_direct` results, partial/failed `planner_executor` status, and the live `langgraph_supervisor` seed progression while the study kept running.

### Reusable Patterns (1-3)
1. For long notebook-driven benchmarks, treat persisted registry rows and query artifact mtimes as the source of truth for progress rather than cell output.
2. Only report aggregate metrics from arms that already have `official_eval.json`; classify everything else as in-progress or invalid rather than extrapolating.
3. Distinguish a completed arm seed from a completed arm family, especially when the study averages across multiple seeds.

### Evidence
- `output/travelplanner_framework_compare/20260409_233919/scientific_pack/run_registry.csv`
- `output/travelplanner_framework_compare/20260409_233919/runs/solo_direct/seed_42/full/official_eval.json`
- `output/travelplanner_framework_compare/20260409_233919/runs/langgraph_supervisor/seed_42/full/official_eval.json`
- `output/travelplanner_framework_compare/20260409_233919/runs/langgraph_supervisor/seed_44/full/queries/query_046.json`

## 2026-04-11 — Scientific Baseline Fallback Hardening

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `8/10`
- `confidence`: `high`
- `scope`: `Prevent TravelPlanner self-refine and planner-executor study arms from aborting on truncated JSON responses`

### Outcome
Hardened the scientific baseline runners so truncated structured outputs no longer abort entire benchmark seeds. `Self-Refine` now compacts evaluator feedback and falls back to a local critique object when the reviewer JSON is invalid, while `Planner-Executor` now requests a smaller planner blueprint and can recover by generating a fallback itinerary then converting it into a normalized blueprint when the planner JSON is truncated.

### Reusable Patterns (1-3)
1. When a benchmark baseline uses multiple structured-output substeps, treat non-essential intermediate JSON as recoverable and derive a deterministic local fallback instead of failing the whole query.
2. Reduce structured-output failure rate by asking planner schemas to emit only non-empty day entries and reconstructing omitted defaults downstream.
3. For planner-style baselines, a direct valid itinerary can serve as a reliable intermediate fallback artifact from which a smaller blueprint is reconstructed.

### Evidence
- `adapters/travelplanner/scientific_baselines.py`
- `tests/unit/test_travelplanner_scientific_baselines.py`
- `python -m py_compile adapters/travelplanner/scientific_baselines.py`
- `pytest tests/unit/test_travelplanner_scientific_baselines.py -q`
- `pytest tests/unit/test_travelplanner_langgraph_supervisor.py tests/unit/test_travelplanner_evaluator.py -q`

## 2026-04-12 — V5.1 Plan Executability Review for TravelPlanner

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `7/10`
- `confidence`: `high`
- `scope`: `Review the updated V5.1 scientific improvement plan against the current TravelPlanner codebase to confirm what is now sound and what is still underspecified`

### Outcome
Confirmed that V5.1 is materially stronger than V5 because it now targets the main structural bottleneck (single-destination TravelPlanner encoding), uses the correct statistical framing for binary `final_pass`, and separates ablation stages cleanly. The remaining gaps are operational rather than conceptual: the multi-city redesign cannot rely on parsing `dest` alone, the proposed ACO heuristic hook is not currently pluggable from the adapter layer, and campaign robustness work should extend the existing per-query checkpointing instead of reintroducing it.

### Reusable Patterns (1-3)
1. Treat a scientific improvement plan as executable only after every major task is checked against the current extension points in code, not just against the intended architecture.
2. When a benchmark adapter compresses a structured task into a scalar field like `dest`, fix the task representation before tuning prompts or hyperparameters.
3. If a benchmark runner already checkpoints per query, subsequent robustness tasks should focus on continue-on-error semantics, failure taxonomy, and clean resume behavior rather than duplicate checkpoint logic.

### Evidence
- `adapters/travelplanner/workspace.py`
- `adapters/travelplanner/adapter.py`
- `adapters/travelplanner/tools.py`
- `core/agent.py`
- `scripts/run_travelplanner_framework_benchmark.py`

## 2026-04-12 — V5.1-Final Plan Review: Partial Scoring Caveat

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `6/10`
- `confidence`: `high`
- `scope`: `Validate the final revised V5.1 benchmark-improvement plan against the scorer and runner behavior before approving it as executable`

### Outcome
Validated that the revised V5.1-final plan closes nearly all earlier methodological and implementation gaps. The remaining caveat is in T5 wording: the official TravelPlanner scorer does not produce a truly partial denominator when some queries fail. Missing predictions are evaluated as empty plans over the full query range, so the campaign can continue and still emit a full `official_eval.json`, but that file is not an `N-k` subset score unless the scorer is explicitly run on a reduced index range.

### Reusable Patterns (1-3)
1. When designing continue-on-error benchmark runners, distinguish `partial artifact availability` from `partial official scoring`; many scorers silently treat missing predictions as empty failures under the full denominator.
2. Acceptance tests for resilience features should reference the exact scorer semantics, not the intended runner semantics.
3. A scientific plan can be considered execution-ready even when one wording fix remains, provided the remaining issue is about measurement phrasing rather than architecture or validity.

### Evidence
- `scripts/run_travelplanner_framework_benchmark.py`
- `scripts/eval_travelplanner_official.py`
- `adapters/travelplanner/workspace.py`

## 2026-04-12 — Official Scoring Wording Patch for V5.1 T5

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `5/10`
- `confidence`: `high`
- `scope`: `Align the V5.1 benchmark-plan wording for continue-on-error with the actual denominator semantics of the official TravelPlanner scorer`

### Outcome
Updated the V5.1 plan so T5 no longer describes continue-on-error runs as producing a subset-scored `official_eval.json`. The plan now states the correct behavior: the campaign continues, failed queries are checkpointed and summarized, and the official scorer still evaluates the full requested range, treating missing predictions as empty failed plans.

### Reusable Patterns (1-3)
1. Distinguish `campaign continuity` from `subset official scoring` in benchmark plans; they are not the same behavior.
2. Acceptance criteria for resilience work should describe both the runner artifact semantics and the scorer denominator semantics.
3. Wording fixes in research plans matter when they change how future readers interpret benchmark validity.

### Evidence
- `documentation/redisgn_v2/plan_v5_framework_improvement.md`
- `scripts/eval_travelplanner_official.py`
- `scripts/run_travelplanner_framework_benchmark.py`

## 2026-04-12 — TravelPlanner Multi-City Adapter T0

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `8/10`
- `confidence`: `high`
- `scope`: `Implement V5.1 T0 by inferring a TravelPlanner city sequence from the local databases, expanding the adapter DAG to multi-city routing, and updating prompts/search payload handling without touching core/`

### Outcome
Implemented a TravelPlanner-side multi-city path that infers `city_sequence` from the local city/state inventory and route availability, injects that sequence into normalized queries and objectives, expands `initial_markers()` into alternating route and per-city search tasks, and teaches the planning toolchain to consume dynamic per-city/per-leg result keys while preserving the single-city keys for backward compatibility. Added a dedicated multi-city fixture and regression tests covering inferred city order, linear inter-city dependencies, and prompt/search payload expansion.

### Reusable Patterns (1-3)
1. When a benchmark query names a state or region but the runtime needs concrete cities, infer the city sequence from inventory coverage plus route feasibility instead of overloading one scalar destination field.
2. Preserve legacy single-entity keys while introducing prefix-based dynamic keys for multi-entity expansion; then make downstream prompt and normalization code match by prefix rather than by exact key.
3. Model multi-city workflows as alternating `route -> city search -> next route` dependencies so the final planning task can depend on one explicit, auditable DAG instead of hidden sequencing logic.

### Evidence
- `adapters/travelplanner/workspace.py`
- `adapters/travelplanner/adapter.py`
- `adapters/travelplanner/tools.py`
- `tests/fixtures/travelplanner_data.py`
- `tests/unit/test_travelplanner_multi_city.py`

## 2026-04-14 — TravelPlanner T5 Continue-on-Error Runner

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `8/10`
- `confidence`: `high`
- `scope`: `Implement T5 end-to-end in the TravelPlanner framework benchmark runner with per-query failure checkpoints, failure taxonomy, and explicit full-denominator scorer semantics`

### Outcome
Implemented T5 in the TravelPlanner batch benchmark runner so a single failing query no longer aborts the whole seed. The runner now persists failed query artifacts with empty-plan outputs and machine-readable failure reasons, continues to the next query, writes an enriched `benchmark_summary.json` with success/failure ratios and tolerance status, and keeps the official scorer contract explicit: campaign resilience improves resumability and traceability without changing the official evaluation denominator.

### Reusable Patterns (1-3)
1. In batch benchmark runners, convert per-item subprocess failures into checkpointable result payloads so resumed runs stay deterministic and auditable.
2. Keep failed query artifacts structurally compatible with downstream scorers by emitting explicit empty-plan outputs rather than omitting the query from the run ledger.
3. When resilience changes runner behavior but not scorer behavior, encode the denominator semantics directly in the machine-readable summary to prevent later misinterpretation.

### Evidence
- `scripts/run_travelplanner_framework_benchmark.py`
- `tests/unit/test_travelplanner_benchmark_runner.py`
- `scripts/eval_travelplanner_official.py`

## 2026-04-16 — TravelPlanner V5-Full Execution Hardening

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `9/10`
- `confidence`: `high`
- `scope`: `Implement TravelPlanner-side V5-full execution upgrades (preset, marker shaping, train-only few-shots, train-only tuning script, and benchmark-runner subset alignment) without modifying core/`

### Outcome
Implemented the V5-full execution layer entirely outside `core/`: a new `config/ablation/v5_full.yaml` preset, marker shaping in TravelPlanner tools, train-only few-shot prompt enrichment with warning-only fallback, and a train-only ACO tuning script that writes temporary train configs and can apply the winning values back to the V5 preset. The existing framework benchmark runner was extended to accept the planned `stigmergic` CLI alias plus inclusive `--start/--end`, and to propagate the evaluated subset bounds to the official scorer. Local validation finished with `275 passed` once the declared `langgraph` dependency was made available for the run.

### Reusable Patterns (1-3)
1. When a benchmark improvement plan forbids `core/` changes, concentrate steering logic in adapter-local tool state updates plus benchmark-script alignment rather than pushing experiment-specific behavior into the generic runtime.
2. For train-only tuning against a validation preset, generate temporary split-overridden configs for the tuning runs and only write the winning scalar hyperparameters back to the reusable base preset.
3. If a benchmark runner already emits per-query artifacts, make subset official scoring explicit by forwarding the requested index bounds to the scorer instead of inferring subset semantics from the partial run ledger.

### Evidence
- `config/ablation/v5_full.yaml`
- `adapters/travelplanner/tools.py`
- `scripts/run_travelplanner_framework_benchmark.py`
- `scripts/tune_aco_travelplanner.py`
- `tests/unit/test_travelplanner_marker_shaping.py`

## 2026-04-17 — V6 Framework Plan Review for Executability and Attribution

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `7/10`
- `confidence`: `high`
- `scope`: `Review the proposed V6 framework-improvement plan against the current runtime extension points, benchmark methodology, and existing TravelPlanner repair loop`

### Outcome
Reviewed `documentation/redisgn_v2/plan_v6_framework_general_improvement.md` against the live codebase and found the overall direction methodologically strong: benchmark freeze, framework-vs-adapter separation, and stratified metrics are all sound. The main caveats are executional: the idle-cycle evidence currently mixes seeds across configs, T1 and T5 overlap with the existing emergence feedback control plane, `marker_reads` are not a reliable proxy for lock contention, T2 is a representation-contract redesign rather than a light runtime tweak, and T3 partly duplicates an adapter-local repair loop that already exists in TravelPlanner.

### Reusable Patterns (1-3)
1. Before accepting a framework-improvement plan, verify that every proposed hook maps to an existing runtime extension point rather than assuming the current architecture already exposes the needed control surface.
2. If a runtime already has one adaptive control loop, route new anti-stagnation and temperature logic through that same control plane unless you explicitly want competing controllers.
3. When comparing benchmark configs, keep seed pairing consistent across variants before drawing causal conclusions from pass-rate deltas.

### Evidence
- `documentation/redisgn_v2/plan_v6_framework_general_improvement.md`
- `core/orchestrator.py`
- `core/emergence.py`
- `core/agent.py`
- `core/marker_store.py`
- `tools/decompose.py`
- `adapters/travelplanner/tools.py`

## 2026-04-18 — V6 Plan Rewritten Into a Three-Arm, Executable Framework Ablation

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `8/10`
- `confidence`: `high`
- `scope`: `Rewrite the V6 framework-improvement plan into a more executable roadmap with paired-seed baseline discipline, a unified control plane, and three attributable ablation arms`

### Outcome
Rewrote `documentation/redisgn_v2/plan_v6_framework_general_improvement.md` into a tighter V6 roadmap. The new version keeps the original scientific boundary conditions, explicitly downgrades mixed-seed `idle=16` evidence to directional status until rerun on paired seeds, merges anti-stagnation and dynamic adaptation into one runtime control plane, reduces the first ablation cycle to `V6-A`, `V6-B`, and `V6-C`, and defers persistent subgoal coverage to a separate `V6.2` track because it changes task representation rather than lightly tuning the runtime.

### Reusable Patterns (1-3)
1. When an improvement plan has too many additive steps, convert it into a short branching ablation around one shared core change so each gain remains attributable.
2. If benchmark evidence mixes seeds across configs, preserve the insight but mark it as directional until a paired-seed replay confirms the effect.
3. Separate runtime control-plane upgrades from task-representation redesigns; the former fit first-pass ablations, the latter deserve their own scoped plan.

### Evidence
- `documentation/redisgn_v2/plan_v6_framework_general_improvement.md`

## 2026-04-18 — V6 Phase-1 Runtime Controls, Lock Telemetry, and Generic Targeted Repair

- `repo_slug`: `stigmergiagentic-33b989`
- `impact_score`: `9/10`
- `confidence`: `high`
- `scope`: `Implement the first executable V6 framework wave in core runtime + TravelPlanner bridge, with frozen V5 reference and dedicated V6 ablation presets`

### Outcome
Implemented the executable phase-1 V6 framework surface in the generic runtime. `core.marker_store` now records explicit lock-attempt telemetry through `marker_lock_events` and exposes aggregated `lock_stats`; `core.orchestrator` now owns a bounded recovery controller with dynamic idle and activation audit; `core.agent` now supports short-horizon stickiness plus recovery-aware target choice; and `core.tool_registry` / `core.environment` now expose a generic validation/repair contract that can materialize repair markers when enabled. TravelPlanner was bridged to that contract behind an opt-in flag, and new ablation presets (`v6_base`, `v6_A`, `v6_B`, `v6_C`) were added while leaving `v5_full.yaml` untouched.

### Reusable Patterns (1-3)
1. For benchmark-sensitive runtime upgrades, preserve the old reference preset and express new behavior through explicit config gates plus dedicated ablation presets.
2. If a coordination controller needs contention awareness, instrument real lock attempts and conflicts directly, then expose the aggregated signal both to the controller and to agent snapshots.
3. A generic repair contract stays clean when the adapter owns `what to repair` and `why`, while the runtime owns `how to materialize and track the repair execution surface`.

### Evidence
- `core/marker_store.py`
- `core/orchestrator.py`
- `core/agent.py`
- `core/environment.py`
- `core/tool_registry.py`
- `adapters/travelplanner/tools.py`
- `config/ablation/v6_base.yaml`
- `config/ablation/v6_A.yaml`
- `config/ablation/v6_B.yaml`
- `config/ablation/v6_C.yaml`
- `documentation/decisions/20260418-sprint8-v6-general-runtime-controls.md`
