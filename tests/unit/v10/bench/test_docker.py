from __future__ import annotations

import json

from scripts.bench.docker import (
    CampaignDockerSpec,
    expected_volumes,
    harness_command,
)


def test_harness_command_round_trips_extras_as_json() -> None:
    spec = CampaignDockerSpec(
        service_name="migrationbench-v10-smoke",
        adapter="migrationbench",
        strategy="branching_repair",
        subset="fixtures/migrationbench/subsets/smoke_5.jsonl",
        out_dir="campaign_results/v10/migrationbench_smoke",
        extras={"workspace_root_root": "workspaces/migrationbench_v10"},
    )
    cmd = harness_command(spec)
    assert cmd[0:5] == ["python", "-m", "scripts.bench.harness", "--adapter", "migrationbench"]
    assert "--extras" in cmd
    extras_idx = cmd.index("--extras")
    extras = json.loads(cmd[extras_idx + 1])
    assert extras["workspace_root_root"] == "workspaces/migrationbench_v10"


def test_harness_command_includes_strategy_knobs() -> None:
    spec = CampaignDockerSpec(
        service_name="migrationbench-v10-smoke",
        adapter="migrationbench",
        strategy="agentless_basic",
        subset="s.jsonl",
        out_dir="out",
        max_candidates=3,
        max_repair_rounds=2,
        max_repairs_per_candidate=4,
    )
    cmd = harness_command(spec)
    assert "--max-candidates" in cmd
    assert cmd[cmd.index("--max-candidates") + 1] == "3"
    assert cmd[cmd.index("--max-repair-rounds") + 1] == "2"
    assert cmd[cmd.index("--max-repairs-per-candidate") + 1] == "4"


def test_expected_volumes_mount_required_paths() -> None:
    spec = CampaignDockerSpec(
        service_name="x",
        adapter="migrationbench",
        strategy="branching_repair",
        subset="s.jsonl",
        out_dir="out",
    )
    volumes = expected_volumes(spec, repo_root=".")
    assert any(v.endswith(":/app/out") for v in volumes)
    assert any(v.endswith(":/app/external") for v in volumes)
    assert any("workspaces/migrationbench_v10" in v for v in volumes)
