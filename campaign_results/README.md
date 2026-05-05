# Raw Campaign Results Exposed For Review

This directory is normally ignored because benchmark campaigns can contain
large workspaces, local logs, SQLite databases, and in-progress runs.

For external review, the repository intentionally exposes a small set of
completed V10 raw campaigns:

- `v10/migrationbench_smoke/` — Phase 4 MigrationBench V10 smoke evidence
  with raw EventLogs and verifier artifacts.
- `v10/phase5_toy_compare/` — Phase 5 toy ablation raw campaign.
- `v10/ablation_main30/` — Phase 5 A1/A2/A3 main_30 campaign with raw
  manifests, summaries, runs, EventLogs, hypothesis graphs, and artifacts.
- `v10/ablation_main30_llm_v2/` — Phase 5 LLM-backed A1/A2/A3 main_30
  campaign used as the closest pre-A4 raw comparison point.
- `v10/ablation_a3_vs_a4_smoke/` — Phase 6 A3 vs A4 smoke campaign.
- `v10/ablation_a3_vs_a4_main30/` — Phase 6 A3 vs A4 main_30 raw campaign
  supporting `documentation/redisgn_v2/phase_06_ablation_main30.md`.

The older raw `campaign_results/migrationbench_v6v7/` tree is deliberately
not exposed because it is about 1.5 GB and contains large legacy SQLite and
audit artifacts. Its tracked summaries remain available in
`output/migrationbench_v6v7_comparison/`.

In-progress or failed retry campaigns, such as budget=5 retry attempts, are
also kept ignored until they have a completed documented summary.
