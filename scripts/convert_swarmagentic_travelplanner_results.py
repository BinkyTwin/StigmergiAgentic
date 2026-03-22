"""Convert SwarmAgentic TravelPlanner results.jsonl into official-eval runs.json."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert SwarmAgentic TravelPlanner evaluation outputs to runs.json"
    )
    parser.add_argument(
        "--results-jsonl",
        type=Path,
        required=True,
        help="Path to SwarmAgentic results.jsonl",
    )
    parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="Output runs.json path",
    )
    parser.add_argument(
        "--expected-count",
        type=int,
        default=None,
        help="If set, add missing query_idx entries as empty plans up to this count",
    )
    parser.add_argument(
        "--method-name",
        type=str,
        default="SwarmAgentic",
        help="Method name recorded in the output metadata",
    )
    return parser.parse_args()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if not text:
                continue
            loaded = json.loads(text)
            if isinstance(loaded, dict):
                rows.append(loaded)
    return rows


def normalize_plan(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    normalized: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, dict):
            normalized.append(dict(item))
    return normalized


def build_runs(rows: list[dict[str, Any]], expected_count: int | None) -> list[dict[str, Any]]:
    converted: dict[int, dict[str, Any]] = {}
    for row in rows:
        try:
            query_idx = int(row.get("idx"))
        except Exception:  # noqa: BLE001
            continue
        converted[query_idx] = {
            "status": "ok",
            "query_idx": query_idx,
            "objective": str(row.get("query", "")).strip(),
            "final_plan": normalize_plan(row.get("plan")),
            "plan": normalize_plan(row.get("plan")),
            "score": float(row.get("score", 0.0) or 0.0),
            "framework": "swarmagentic",
        }

    if expected_count is not None and expected_count > 0:
        for query_idx in range(expected_count):
            converted.setdefault(
                query_idx,
                {
                    "status": "missing",
                    "query_idx": query_idx,
                    "objective": "",
                    "final_plan": [],
                    "plan": [],
                    "score": 0.0,
                    "framework": "swarmagentic",
                },
            )

    return [converted[key] for key in sorted(converted)]


def main() -> int:
    args = parse_args()
    results_jsonl = args.results_jsonl.expanduser().resolve()
    out_path = args.out.expanduser().resolve()
    rows = load_jsonl(results_jsonl)
    runs = build_runs(rows, args.expected_count)

    payload = {
        "method_name": args.method_name,
        "source_results_jsonl": str(results_jsonl),
        "runs": runs,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(f"wrote {out_path}")
    print(f"converted_runs={len(runs)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
