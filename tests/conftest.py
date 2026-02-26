"""Shared pytest fixtures for V2 Sprint 1 unit tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.marker_store import MarkerStore


@pytest.fixture
def config_dict() -> dict:
    """Minimal config fixture for unit tests."""
    return {
        "framework": {"name": "stigmergy-v2", "version": "2.0.0"},
        "agents": {
            "num_agents": 4,
            "num_agents_mode": "fixed",
            "files_per_agent": 6,
            "selection_temperature": 0.1,
        },
        "markers": {
            "decay_type": "exponential",
            "decay_rate": 0.05,
            "inhibition_decay_rate": 0.08,
            "inhibition_increment": 0.5,
            "inhibition_threshold": 0.1,
            "intensity_clamp": [0.1, 1.0],
        },
        "guardrails": {
            "max_retry_count": 3,
            "scope_lock_ttl": 3,
            "traceability": True,
            "audit_completeness": True,
        },
        "orchestrator": {
            "max_ticks": 50,
            "idle_cycles_to_stop": 2,
            "parallel": True,
        },
        "llm": {
            "provider": "openrouter",
            "model": "qwen/qwen3-235b-a22b-2507",
            "temperature": 0.2,
            "max_tokens_total": 200000,
            "max_budget_usd": 5.0,
            "request_timeout_seconds": 300,
            "retry_attempts": 3,
            "min_429_backoff_seconds": 8.0,
        },
        "pressures": {"default_weights": {}},
    }


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """Per-test marker DB path."""
    return tmp_path / "pheromones" / "markers.db"


@pytest.fixture
def marker_store(db_path: Path) -> MarkerStore:
    """Marker store fixture with default retry limit and traceability."""
    return MarkerStore(db_path=db_path)
