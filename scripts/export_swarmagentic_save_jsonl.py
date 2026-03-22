"""Export SwarmAgentic TravelPlanner save_state.jsonl into save.jsonl for test.py."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert SwarmAgentic save_state.jsonl into save.jsonl archives"
    )
    parser.add_argument(
        "--state-jsonl",
        type=Path,
        required=True,
        help="Path to save_state.jsonl",
    )
    parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="Output save.jsonl path",
    )
    parser.add_argument(
        "--state-idx",
        type=int,
        default=-1,
        help="State index to export (-1 selects the latest state)",
    )
    return parser.parse_args()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
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


def build_archive(state: dict[str, Any]) -> dict[str, Any]:
    particles = state.get("particles", [])
    archive: list[dict[str, Any]] = []
    if isinstance(particles, list):
        for item in particles:
            if not isinstance(item, dict):
                continue
            best_position = item.get("best_position")
            if not isinstance(best_position, list) or len(best_position) != 2:
                continue
            archive.append(
                {
                    "team": best_position[0],
                    "code": best_position[1],
                    "score": item.get("best_fitness", 0.0),
                }
            )
    return {"archive": archive}


def main() -> int:
    args = parse_args()
    state_jsonl = args.state_jsonl.expanduser().resolve()
    out_path = args.out.expanduser().resolve()
    states = read_jsonl(state_jsonl)
    if not states:
        raise ValueError(f"No states found in {state_jsonl}")

    state = states[args.state_idx]
    payload = build_archive(state)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=True) + "\n", encoding="utf-8")
    print(f"wrote {out_path}")
    print(f"archive_particles={len(payload['archive'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
