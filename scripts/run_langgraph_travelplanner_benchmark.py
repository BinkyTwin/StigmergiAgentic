"""Thin wrapper around the shared TravelPlanner benchmark runner for LangGraph."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.run_travelplanner_framework_benchmark import main as benchmark_main


def main() -> int:
    return benchmark_main(["--framework", "langgraph_supervisor", *sys.argv[1:]])


if __name__ == "__main__":
    raise SystemExit(main())
