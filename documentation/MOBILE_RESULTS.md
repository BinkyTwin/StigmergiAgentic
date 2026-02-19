# Mobile Results Snapshot (Sprint 4)

This document is designed for quick reading from a phone.

## Scope

- Snapshot date (UTC): **2026-02-17**
- Benchmark batch: **`metrics/output/sprint4_20260217_full`**
- Test repo: **`docopt/docopt@0.6.2`**
- Model: **`qwen/qwen3-235b-a22b-2507`**
- Compared modes (5 runs each): `stigmergic`, `single_agent`, `sequential`
- Fairness setup: same repo/ref/model/temperature/config family for all modes
- Run mode: **unbounded** (no forced `--max-ticks 1`, no forced `--max-tokens 5000`)

> This is the Sprint 4 thesis-grade comparison batch (5x3), not the previous bounded smoke snapshot.

---

## Quick Scoreboard (Mean over 5 runs)

| Mode | Success rate | Tokens | Cost (USD) | Mean ticks | Dominant stop reason |
|---|---:|---:|---:|---:|---|
| single_agent | 1.000000 | 34224.6 | 0.009907 | 23.0 | all_terminal (5/5) |
| stigmergic | 0.956522 | 79921.6 | 0.027932 | 26.0 | all_terminal (5/5) |
| sequential | 0.382609 | 49138.4 | 0.016244 | 3.4 | idle_cycles (3/5) |

### Fast takeaway

- `single_agent` is best on this batch for both quality and efficiency.
- `stigmergic` is close in quality (`22/23` files on average) but much more expensive in tokens/cost.
- `sequential` has high variance (2 successful runs, 3 early stops on `idle_cycles`).

---

## Pareto Snapshot (tokens vs success)

From `pareto_summary.json` (`plot_mode=per-run`, required baselines enforced):

- `single_agent`: `success_mean=1.000000`, `success_ci95=0.000000`, `x_mean=34224.6`, `x_ci95=1015.5737`
- `stigmergic`: `success_mean=0.956522`, `success_ci95=0.000000`, `x_mean=79921.6`, `x_ci95=1851.6709`
- `sequential`: `success_mean=0.382609`, `success_ci95=0.459226`, `x_mean=49138.4`, `x_ci95=18261.5425`
- Pareto frontier baselines: **`single_agent`**

---

## Example run summaries (one run per mode)

### Stigmergic

```json
{
  "run_id": "20260217T191307Z",
  "stop_reason": "all_terminal",
  "success_rate": 0.956522,
  "files_validated": 22,
  "files_total": 23,
  "total_ticks": 26,
  "total_tokens": 78057,
  "total_cost_usd": 0.027523
}
```

### Sequential baseline

```json
{
  "run_id": "sequential_20260217T191252Z_r01",
  "baseline": "sequential",
  "scheduler": "sequential",
  "stop_reason": "all_terminal",
  "success_rate": 0.956522,
  "files_validated": 22,
  "files_total": 23,
  "total_ticks": 4,
  "total_tokens": 63234,
  "total_cost_usd": 0.026608
}
```

### Single-agent baseline

```json
{
  "run_id": "single_agent_20260217T141053Z_r01",
  "baseline": "single_agent",
  "scheduler": "single_agent",
  "stop_reason": "all_terminal",
  "success_rate": 1.0,
  "files_validated": 23,
  "files_total": 23,
  "total_ticks": 23,
  "total_tokens": 32956,
  "total_cost_usd": 0.007619
}
```

---

## How to regenerate this benchmark

```bash
OUT=metrics/output/sprint4_20260217_full
REPO=https://github.com/docopt/docopt.git
REF=0.6.2
MODEL=qwen/qwen3-235b-a22b-2507

# 1) Baselines (5 runs each)
uv run python baselines/single_agent.py --repo "$REPO" --repo-ref "$REF" \
  --model "$MODEL" --config stigmergy/config.yaml --output-dir "$OUT" --runs 5

uv run python baselines/sequential.py --repo "$REPO" --repo-ref "$REF" \
  --model "$MODEL" --config stigmergy/config.yaml --output-dir "$OUT" --runs 5

# 2) Stigmergic (5 runs)
for i in 1 2 3 4 5; do
  uv run python main.py --repo "$REPO" --repo-ref "$REF" \
    --model "$MODEL" --config stigmergy/config.yaml --output-dir "$OUT"
done

# 3) Pareto outputs with baseline coverage check
uv run python metrics/pareto.py \
  --input-dir "$OUT" \
  --output "$OUT/pareto.png" \
  --plot-mode per-run \
  --require-baselines stigmergic,single_agent,sequential \
  --export-json "$OUT/pareto_summary.json"
```
