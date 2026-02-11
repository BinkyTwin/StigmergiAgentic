"""Pytest path bootstrap for local package imports."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Fixture repositories under tests/fixtures are data, not project test suites.
collect_ignore_glob = ["fixtures/*"]


def pytest_configure(config) -> None:  # type: ignore[no-untyped-def]
    """Register custom markers used by this project test suite."""
    config.addinivalue_line(
        "markers",
        "live_api: optional tests hitting real OpenRouter endpoints",
    )
