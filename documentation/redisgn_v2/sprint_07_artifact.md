# Sprint 07 — V5-Full Execution Artifact

## Sprint scope

Sprint 7 hardens the TravelPlanner execution path for the V5-full campaign without modifying `core/`:
- create the `config/ablation/v5_full.yaml` preset from the V4-only preset
- add TravelPlanner-side marker shaping for empty searches, empty plans, and failed validations
- enrich `PlanDayTool` prompts with train-only few-shot examples plus an explicit multi-city instruction
- add a train-only ACO hyperparameter tuning script that updates `v5_full.yaml`
- align the benchmark runner with the plan CLI (`stigmergic`, inclusive `--start/--end`) and subset-aware official scoring

## Current artifact behavior

The TravelPlanner execution stack now has three additional steering layers on top of Sprint 6:

1. search markers keep their current intensity when a deterministic search returns no rows, which preserves retry pressure for unresolved inventory gaps
2. planning markers jump back to `intensity=0.8` when the LLM returns an empty plan, instead of decaying toward inactivity
3. validation markers reshape the local marker field on failure:
   - the validation marker is boosted to `intensity=0.9` and `inhibition=0.0`
   - commonsense failures also inhibit the upstream plan marker path by `+0.3`

Prompt behavior also changes:
- `PlanDayTool` now tries to load two few-shot examples from `osunlp/TravelPlanner` split `train` only
- one example is single-city and one is multi-city when both are available
- multi-city prompts now include an explicit transfer/stay-day instruction
- dataset loading failure only emits a warning and does not break planning

Benchmark/tuning behavior:
- `scripts/tune_aco_travelplanner.py` generates temporary `train` configs, runs the existing framework benchmark over a parameter grid, aggregates official `final_pass_rate` and `delivery_rate`, selects the best combination, and can apply the winning values back into `config/ablation/v5_full.yaml`
- `scripts/run_travelplanner_framework_benchmark.py` now accepts the `stigmergic` alias and inclusive `--start/--end` bounds, while propagating the evaluated subset to the official scorer

## Public interfaces and contracts

### Configs

- `config/travelplanner_v4_only.yaml`
- `config/ablation/v5_full.yaml`

### Scripts

- `scripts/run_travelplanner_framework_benchmark.py`
  - accepts `--framework stigmergic`
  - accepts inclusive `--start` / `--end`
- `scripts/tune_aco_travelplanner.py`
  - `--base-config`
  - `--split train` only
  - `--n-queries`
  - `--seeds`
  - `--out-dir`
  - `--apply`

### Tests

- `tests/unit/test_travelplanner_marker_shaping.py`
- `tests/unit/test_tune_aco_travelplanner.py`
- extended prompt/config/benchmark-runner tests in existing unit suites

## Guardrails and constraints

- `core/` remains unchanged
- `third_party/travelplanner_official/` remains unchanged by this sprint
- `markers.session_isolation` stays enabled in `config/ablation/v5_full.yaml`
- the tuning script rejects any split other than `train`
- few-shot loading is explicitly train-only and warning-only on failure
- the base V5-full preset remains a validation preset; the tuner uses generated temporary train configs instead of permanently flipping the base split

## Known limits / not executed in this session

- the live train tuning run was not executed here because it is a long, API-costly benchmark workflow
- the final 3-seed validation benchmark campaign (`42`, `43`, `44`) was not executed here for the same reason
- few-shot prompt enrichment depends on Hugging Face dataset availability at runtime; when unavailable, prompts fall back to the non-few-shot behavior
- full local validation currently needs the declared `langgraph` dependency available in the runtime environment

## Validation evidence

- `uv run pytest tests/unit/test_config.py tests/unit/test_travelplanner_tools.py tests/unit/test_travelplanner_marker_shaping.py tests/unit/test_travelplanner_benchmark_runner.py tests/unit/test_tune_aco_travelplanner.py -q` -> `43 passed`
- `uv run --with 'langgraph>=1.0.0' pytest tests/ -q` -> `275 passed`
