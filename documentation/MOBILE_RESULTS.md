# Mobile Results Snapshot (Sprint 4)

This document is designed for quick reading from a phone.

## Scope

- Snapshot date (UTC): **2026-02-14**
- Test repo used for this snapshot: **1 small Python 2 file**
- Compared modes:
  - `stigmergic` (main round-robin loop)
  - `single_agent` baseline
  - `sequential` baseline

> Important: this is a **smoke comparison snapshot**, not the final thesis benchmark.

---

## Quick Scoreboard

| Mode | Success rate | Tokens | Cost (USD) | Stop reason |
|---|---:|---:|---:|---|
| sequential | 1.00 | 118 | 0.000026 | all_terminal |
| stigmergic | 1.00 | 119 | 0.000031 | all_terminal |
| single_agent | 1.00 | 146 | 0.000038 | all_terminal |

### Fast takeaway

- On this tiny smoke case, all three modes validate 1/1 file.
- `sequential` is the cheapest in tokens/cost for this specific run.
- `stigmergic` is very close to `sequential` here.
- `single_agent` consumed more tokens on this sample.

---

## Pareto Snapshot (tokens vs success)

Aggregated view (1 run per mode in this snapshot):

- `sequential`: x_mean=118.0, success_mean=1.0
- `stigmergic`: x_mean=119.0, success_mean=1.0
- `single_agent`: x_mean=146.0, success_mean=1.0
- Pareto frontier winner for this sample: **sequential**

---

## Exact run summaries (JSON content)

### Stigmergic

```json
{
  "audit_completeness": 1.0,
  "files_failed": 0,
  "files_needs_review": 0,
  "files_total": 1,
  "files_validated": 1,
  "human_escalation_rate": 0.0,
  "retry_resolution_rate": 0.0,
  "rollback_rate": 0.0,
  "run_id": "20260214T194651Z",
  "starvation_count": 0,
  "stop_reason": "all_terminal",
  "success_rate": 1.0,
  "total_cost_usd": 3.1e-05,
  "total_ticks": 1,
  "total_tokens": 119
}
```

### Sequential baseline

```json
{
  "audit_completeness": 1.0,
  "baseline": "sequential",
  "files_failed": 0,
  "files_needs_review": 0,
  "files_total": 1,
  "files_validated": 1,
  "human_escalation_rate": 0.0,
  "retry_resolution_rate": 0.0,
  "rollback_rate": 0.0,
  "run_id": "sequential_20260214T194645Z_r01",
  "scheduler": "sequential",
  "starvation_count": 0,
  "stop_reason": "all_terminal",
  "success_rate": 1.0,
  "total_cost_usd": 2.6e-05,
  "total_ticks": 1,
  "total_tokens": 118
}
```

### Single-agent baseline

```json
{
  "audit_completeness": 1.0,
  "baseline": "single_agent",
  "files_failed": 0,
  "files_needs_review": 0,
  "files_total": 1,
  "files_validated": 1,
  "human_escalation_rate": 0.0,
  "retry_resolution_rate": 0.0,
  "rollback_rate": 0.0,
  "run_id": "single_agent_20260214T194641Z_r01",
  "scheduler": "single_agent",
  "starvation_count": 0,
  "stop_reason": "all_terminal",
  "success_rate": 1.0,
  "total_cost_usd": 3.8e-05,
  "total_ticks": 1,
  "total_tokens": 146
}
```

---

## How to regenerate this snapshot later

```bash
# 1) Run baselines + stigmergic
uv run python baselines/single_agent.py --repo <repo_or_path> --config stigmergy/config.yaml --output-dir <out_dir>
uv run python baselines/sequential.py --repo <repo_or_path> --config stigmergy/config.yaml --output-dir <out_dir>
uv run python main.py --repo <repo_or_path> --config stigmergy/config.yaml --output-dir <out_dir>

# 2) Build Pareto outputs
uv run python metrics/pareto.py --input-dir <out_dir> --output <out_dir>/pareto.png --export-json <out_dir>/pareto_summary.json
```

---

## Next step for thesis-grade comparison

Use at least **5 runs per mode** on the real target repo (same model, same budgets, same config), then compare mean + variance on success/tokens/USD.
