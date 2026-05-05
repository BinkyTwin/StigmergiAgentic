"""Tests for final campaign aggregation semantics."""

from __future__ import annotations

import json

from scripts.aggregate_campaign_comparison import _load_stigmergy_row, aggregate


def test_stigmergy_no_plan_artifact_delivery_is_not_official_delivery(tmp_path) -> None:
    payload = {
        "adapter": "travelplanner",
        "assistant_response": "No travel plan generated.",
        "evaluation": {
            "evaluated_queries": 0,
            "query_results": [
                {
                    "query_idx": 90,
                    "delivered": True,
                    "final_pass": False,
                    "failure_reason": "idle_cycles",
                }
            ],
        },
        "tokens_used": 123,
        "cost_used": 0.01,
        "runtime_seconds": 4.2,
    }
    path = tmp_path / "query_90.json"
    path.write_text("console preamble\n" + json.dumps(payload, indent=2))

    row = _load_stigmergy_row(path, "gemma", "stigmergiagentic_c3")

    assert row is not None
    assert row["artifact_delivered"] is False
    assert row["official_delivered"] is False
    assert row["delivered"] is False
    assert row["raw_final_pass"] is False
    assert row["strict_final_pass"] is False

    summary = aggregate([row])[("gemma", "stigmergiagentic_c3")]
    assert summary["artifact_delivery_rate"] == 0.0
    assert summary["official_delivery_rate"] == 0.0
    assert summary["delivery_rate"] == 0.0
    assert summary["final_pass_rate"] == 0.0
