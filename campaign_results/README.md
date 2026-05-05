# Raw Campaign Results Exposed For Review

This directory is normally ignored because benchmark campaigns can contain
large workspaces, local logs, SQLite databases, and in-progress runs.

For external review, the repository intentionally exposes a small set of
completed V10 raw campaigns that were stable enough to commit:

- `v10/ablation_main30/` — Phase 5 A1/A2/A3 main_30 campaign with raw
  manifests, summaries, runs, EventLogs, hypothesis graphs, and artifacts.
- `v10/ablation_a3_vs_a4_smoke/` — Phase 6 A3 vs A4 smoke campaign.
- `v10/ablation_a3_vs_a4_main30/` — Phase 6 A3 vs A4 main_30 raw campaign
  supporting `documentation/redisgn_v2/phase_06_ablation_main30.md`.

Other local raw campaign trees, including `v10/migrationbench_smoke/`,
`v10/phase5_toy_compare/`, `v10/ablation_main30_llm_v2/`, and the older
`campaign_results/migrationbench_v6v7/`, are deliberately not committed here.
Some are local/in-progress or were held open by Docker/FileProvider during
publication; `migrationbench_v6v7` is also about 1.5 GB with large legacy
SQLite and audit artifacts. Its tracked summaries remain available in
`output/migrationbench_v6v7_comparison/`.

In-progress or failed retry campaigns, such as budget=5 retry attempts, are
also kept ignored until they have a completed documented summary.
