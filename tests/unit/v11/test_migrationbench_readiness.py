"""V11 MigrationBench readiness report tests."""

from __future__ import annotations

from pathlib import Path

from scripts.bench.compare_strategies import V11_ARMS, _extras_for_arm
from scripts.v11.run_v11_migrationbench_campaign import (
    _causal_activation_ok,
    _pairwise_divergence,
)


def test_pairwise_divergence_reports_treatment_decision_changes() -> None:
    comparison = {
        "arms": [
            {
                "arm_id": "B2_branching_repair",
                "instances": [
                    {
                        "instance_id": "repo-a",
                        "selected_hypothesis_id": "repo-a-c0",
                        "stop_reason": "repair_exhausted",
                        "strict_success": False,
                    }
                ],
            },
            {
                "arm_id": "B6_operator_search",
                "instances": [
                    {
                        "instance_id": "repo-a",
                        "selected_hypothesis_id": "repo-a-c0-op",
                        "stop_reason": "repair_exhausted",
                        "strict_success": False,
                        "decision_influenced_count": 1,
                        "operator_applied_count": 1,
                    }
                ],
            },
        ]
    }

    rows = _pairwise_divergence(comparison)

    assert rows == [
        {
            "control_arm": "B2_branching_repair",
            "treatment_arm": "B6_operator_search",
            "divergence_count": 1,
            "instance_count": 1,
            "divergence_rate": 1.0,
            "instances": [
                {
                    "instance_id": "repo-a",
                    "diverged": True,
                    "reasons": [
                        "selected_hypothesis_id",
                        "decision_influenced",
                        "operator_applied",
                    ],
                    "control_selected": "repo-a-c0",
                    "treatment_selected": "repo-a-c0-op",
                    "control_strict_success": False,
                    "treatment_strict_success": False,
                }
            ],
        }
    ]


def test_compare_strategy_extras_are_scoped_per_arm() -> None:
    arm = V11_ARMS[1]
    scoped = _extras_for_arm(
        {
            "out_dir": "campaign_results/v11/global",
            "workspace_root_root": "workspaces/migrationbench_v11",
            "artifacts_root": "campaign_results/v11/artifacts",
        },
        arm=arm,
        arm_out_dir=Path("campaign_results/v11/run") / arm.arm_id,
    )

    assert scoped["out_dir"].endswith("B5_stigmergic_scheduler")
    assert scoped["workspace_root_root"].endswith("B5_stigmergic_scheduler")
    assert scoped["artifacts_root"].endswith("B5_stigmergic_scheduler")


def test_causal_activation_gate_allows_local_green_no_repair_case() -> None:
    arms = {
        "B5_stigmergic_scheduler": {
            "validation_passed_total": 1,
            "validation_failed_total": 0,
            "validation_error_total": 0,
            "validation_partial_total": 0,
            "signal_read_total": 0,
            "decision_influenced_total": 0,
        },
        "B6_operator_search": {
            "validation_passed_total": 1,
            "validation_failed_total": 0,
            "validation_error_total": 0,
            "validation_partial_total": 0,
            "signal_read_total": 0,
            "decision_influenced_total": 0,
        },
    }

    assert _causal_activation_ok(arms) is True


def test_causal_activation_gate_requires_reads_after_failures() -> None:
    arms = {
        "B5_stigmergic_scheduler": {
            "validation_failed_total": 1,
            "validation_error_total": 0,
            "validation_partial_total": 0,
            "signal_read_total": 0,
            "decision_influenced_total": 0,
        },
        "B6_operator_search": {
            "validation_failed_total": 1,
            "validation_error_total": 0,
            "validation_partial_total": 0,
            "signal_read_total": 1,
            "decision_influenced_total": 1,
        },
    }

    assert _causal_activation_ok(arms) is False
