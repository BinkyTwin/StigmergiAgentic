# TravelPlanner Organization-Philosophy Scientific Protocol

## Objective

This protocol evaluates whether the stigmergic organization implemented in `StigmergiAgentic` outperforms reproducible centralized or monolithic organization philosophies on TravelPlanner under a controlled same-backbone setup.

## Research Question

At backbone-constant conditions and under the official TravelPlanner scorer, does the stigmergic organization outperform reproducible centralized or monolithic organizations, and at what operational cost?

## Compared Philosophies

- `Direct Solo`
- `CoT Solo`
- `Self-Refine Solo`
- `Central Planner-Executor`
- `Central Graph Supervisor`
- `StigmergiAgentic`

Implementation names such as `LangGraph` are treated as technical backends, not as the scientific claim itself.

## Controlled Dimensions

- Provider: `OpenRouter`
- Model: `qwen/qwen3.5-9b`
- Split: `validation`
- Official scorer: `scripts/eval_travelplanner_official.py`
- Output contract: `query_XXX.json -> runs.json -> official_eval.json`
- Execution environment: Docker-first through `travelplanner-smoke`
- Temperature: `0.0`
- Request timeout: `120` seconds
- Retry attempts: `2`
- Max response tokens: `512`
- Reasoning config: `{"effort": "none", "exclude": true}`

## Replications

- Seeds: `42`, `43`, `44`
- The replications are robustness runs, not a proof of strict determinism.
- Each successful full run covers the `180` TravelPlanner validation queries.

## Endpoints

Primary endpoint:
- `Final Pass Rate`

Secondary endpoints:
- `Delivery Rate`
- `Commonsense Constraint Micro`
- `Commonsense Constraint Macro`
- `Hard Constraint Micro`
- `Hard Constraint Macro`
- Tokens
- Cost
- Runtime
- Coordination overhead
- Reproducibility status

## Gating Logic

1. `Preflight`
   - Run `3` validation queries on the canonical seed (`42`) for all philosophies.
   - A philosophy that fails preflight does not proceed to pilot or full.
2. `Pilot`
   - Run `20` validation queries on the canonical seed for all philosophies that passed preflight.
   - A philosophy that fails pilot does not proceed to full.
3. `Full`
   - Run `180` validation queries for each philosophy and for each seed `42/43/44`.

## Run Classification

Each run is classified as one of:
- `success`
- `infra_failure`
- `framework_failure`
- `partial_success`

Runs that fail are never converted into score `0`.

## Statistical Analysis

The scientific pack produced by the benchmark includes:
- main table with `mean ± sd` across the three full replications
- run-level secondary table
- paired `Final Pass` comparisons on the canonical seed
- exact McNemar test for `Final Pass`
- paired bootstrap 95% confidence interval for `Final Pass` deltas
- operational summaries for cost, runtime, and coordination overhead
- reproducibility report
- threats-to-validity report
- DSR / FEDS Episode 1 summary

## DSR Alignment

This protocol operationalizes:
- `OC3` through a controlled comparison against reproducible centralized baselines
- `FEDS Episode 1` through quantitative benchmarking, efficiency metrics, and reproducibility evidence

## Interpretation Rule

Results must be phrased as:
- organization-philosophy comparisons
- same-backbone controlled benchmark findings
- conditional outperformance under the TravelPlanner protocol

Results must not be phrased as universal superiority claims over all multi-agent systems or all frameworks.
