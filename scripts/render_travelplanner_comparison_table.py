"""Render a compact comparison table from official TravelPlanner scorer outputs."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


METRIC_ORDER = [
    ("delivery_rate", "Delivery"),
    ("commonsense_micro", "Commonsense Micro"),
    ("commonsense_macro", "Commonsense Macro"),
    ("hard_constraint_micro", "Hard Constraint Micro"),
    ("hard_constraint_macro", "Hard Constraint Macro"),
    ("final_pass_rate", "Final"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render a markdown/csv comparison table for TravelPlanner official scores"
    )
    parser.add_argument(
        "--run",
        action="append",
        default=[],
        help="Repeated argument formatted as METHOD=PATH_TO_OFFICIAL_EVAL_JSON",
    )
    parser.add_argument("--out-md", type=Path, default=None, help="Optional markdown output path")
    parser.add_argument("--out-csv", type=Path, default=None, help="Optional csv output path")
    parser.add_argument("--out-json", type=Path, default=None, help="Optional json output path")
    return parser.parse_args()


def load_scores(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    scores = payload.get("scores", {})
    if not isinstance(scores, dict):
        raise ValueError(f"Invalid official eval payload: {path}")
    return scores


def format_percent(value: Any) -> str:
    try:
        return f"{float(value) * 100:.1f}"
    except Exception:  # noqa: BLE001
        return "0.0"


def build_rows(run_args: list[str]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for item in run_args:
        if "=" not in item:
            raise ValueError(f"Invalid --run value (expected METHOD=PATH): {item}")
        method, raw_path = item.split("=", 1)
        path = Path(raw_path).expanduser().resolve()
        scores = load_scores(path)
        row = {"Method": method}
        for key, label in METRIC_ORDER:
            row[label] = format_percent(scores.get(key, 0.0))
        row["Official Eval JSON"] = str(path)
        rows.append(row)
    return rows


def render_markdown(rows: list[dict[str, str]]) -> str:
    headers = ["Method", *[label for _, label in METRIC_ORDER]]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row[h] for h in headers) + " |")
    return "\n".join(lines) + "\n"


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    headers = ["Method", *[label for _, label in METRIC_ORDER], "Official Eval JSON"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    args = parse_args()
    if not args.run:
        raise ValueError("At least one --run METHOD=PATH argument is required")

    rows = build_rows(args.run)
    markdown = render_markdown(rows)
    print(markdown)

    if args.out_md is not None:
        out_md = args.out_md.expanduser().resolve()
        out_md.parent.mkdir(parents=True, exist_ok=True)
        out_md.write_text(markdown, encoding="utf-8")
        print(f"wrote {out_md}")

    if args.out_csv is not None:
        out_csv = args.out_csv.expanduser().resolve()
        write_csv(out_csv, rows)
        print(f"wrote {out_csv}")

    if args.out_json is not None:
        out_json = args.out_json.expanduser().resolve()
        out_json.parent.mkdir(parents=True, exist_ok=True)
        out_json.write_text(json.dumps({"rows": rows}, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {out_json}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
