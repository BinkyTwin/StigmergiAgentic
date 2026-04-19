"""Shared pytest fixtures for V2 Sprint 1 unit tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
FIXTURES_ROOT = REPO_ROOT / "tests" / "fixtures"
if str(FIXTURES_ROOT) not in sys.path:
    sys.path.insert(0, str(FIXTURES_ROOT))

from core.marker_store import MarkerStore  # noqa: E402


@pytest.fixture
def config_dict() -> dict:
    """Minimal config fixture for unit tests."""
    return {
        "framework": {"name": "stigmergy-v3", "version": "3.0.0"},
        "agents": {
            "num_agents": 4,
            "num_agents_mode": "fixed",
            "files_per_agent": 6,
            "selection_temperature": 0.1,
            "memory_capacity": 20,
            "memory_decay_rate": 0.1,
            "local_sensing": {
                "enabled": False,
                "intensity_threshold": 0.0,
                "type_affinity_weight": 0.4,
                "semantic_affinity_weight": 0.3,
                "recency_weight": 0.3,
                "max_candidates": 0,
                "affinity_exploration_rate": 0.2,
            },
            "stickiness": {
                "enabled": False,
                "recent_progress_window": 3,
                "continuity_bonus": 0.08,
                "max_consecutive_reuse": 2,
            },
        },
        "markers": {
            "decay_type": "exponential",
            "decay_rate": 0.05,
            "default_decay_rate": 0.05,
            "decay_rates_by_type": {
                "task": 0.05,
                "dependency": 0.01,
                "anticipatory": 0.15,
                "lesson": 0.01,
            },
            "inhibition_decay_rate": 0.08,
            "inhibition_increment": 0.5,
            "inhibition_threshold": 0.1,
            "prune_threshold": 0.05,
            "session_isolation": False,
            "intensity_clamp": [0.1, 1.0],
            "time_decay": {
                "enabled": False,
                "decay_period_seconds": 60.0,
            },
        },
        "reinforcement": {
            "enabled": True,
            "rate": 0.1,
            "propagation_factor": 0.5,
            "max_intensity": 1.0,
            "lesson_threshold": 0.7,
            "frequentation": {
                "enabled": False,
                "read_boost": 0.01,
                "completion_boost": 0.05,
                "max_boost_per_tick": 0.1,
                "diminishing_factor": 0.5,
            },
        },
        "guardrails": {
            "max_retry_count": 3,
            "scope_lock_ttl": 3,
            "traceability": True,
            "audit_completeness": True,
        },
        "orchestrator": {
            "max_ticks": 50,
            "idle_cycles_to_stop": 3,
            "parallel": True,
            "emergent_resolution": {
                "enabled": False,
                "base_probability": 0.1,
            },
            "recovery_controller": {
                "enabled": False,
                "stagnation_ticks": 5,
                "contention_threshold": 0.6,
                "recovery_cooldown_ticks": 8,
                "temperature_boost": 0.1,
                "temperature_boost_duration": 3,
                "inhibition_relief": 0.2,
                "dynamic_idle": {
                    "enabled": False,
                    "node_per_idle_cycle": 6,
                    "max_extra_idle_cycles": 8,
                },
            },
            "targeted_repair": {
                "enabled": False,
                "max_cycles": 2,
                "repair_marker_intensity": 0.95,
            },
        },
        "emergence": {
            "enabled": True,
            "metrics": [
                "specialization_entropy",
                "colony_specialization",
                "collaboration_density",
                "action_switching_rate",
                "convergence_tick",
                "lock_contention_rate",
                "parallel_utilization",
                "pressure_entropy",
            ],
            "feedback_loop": {
                "enabled": False,
                "interval_ticks": 5,
                "max_adaptation_delta": 0.2,
            },
        },
        "llm": {
            "provider": "openrouter",
            "model": "qwen/qwen3.5-9b",
            "temperature": 0.2,
            "max_tokens_total": 200000,
            "max_budget_usd": 5.0,
            "request_timeout_seconds": 300,
            "retry_attempts": 3,
            "min_429_backoff_seconds": 8.0,
        },
        "pressures": {
            "formula": "aco",
            "alpha": 1.0,
            "beta": 2.0,
            "default_weights": {},
        },
        "decompose": {
            "max_depth": 2,
            "max_subtasks": 8,
            "allow_redecompose": False,
        },
        "async": {
            "max_concurrent_llm_calls": 4,
            "subprocess_timeout": 120,
        },
        "tools": {
            "sandbox_root": ".",
            "allowed_commands": ["python", "pytest", "git", "pip", "uv"],
            "bash_timeout_seconds": 120,
            "max_file_size_bytes": 1048576,
            "web_search_provider": "none",
            "web_search_max_results": 5,
        },
    }


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """Per-test marker DB path."""
    return tmp_path / "pheromones" / "markers.db"


@pytest.fixture
def marker_store(db_path: Path) -> MarkerStore:
    """Marker store fixture with default retry limit and traceability."""
    return MarkerStore(db_path=db_path)
