from __future__ import annotations

import pytest

from adapters_v10.migrationbench.context import (
    migration_context_from_instance,
    migration_context_from_observation,
)
from core_v10.contracts import Observation, RunInstance


def test_missing_target_java_fails_fast() -> None:
    with pytest.raises(ValueError, match="target_java"):
        migration_context_from_observation(Observation(summary="missing", data={}))

    with pytest.raises(ValueError, match="target_java"):
        migration_context_from_instance(
            RunInstance(
                instance_id="repo__case",
                adapter_name="migrationbench_v10",
                objective="migrate",
                metadata={"instance": {"repo_url": "x", "base_commit": "abc"}},
            )
        )
