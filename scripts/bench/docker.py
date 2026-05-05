"""Docker run helpers for V10 bench campaigns.

These helpers are pure command builders — they do not invoke the Docker
CLI themselves. They exist so the same recipe can be reused from
``docker-compose.campaign.yml``, from a maintainer's shell, or from
integration tests.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CampaignDockerSpec:
    """Frozen description of a Dockerised V10 bench run."""

    service_name: str
    adapter: str
    strategy: str
    subset: str
    out_dir: str
    extras: dict[str, Any] = field(default_factory=dict)
    seed: int = 42
    max_candidates: int = 1
    max_repair_rounds: int = 0
    max_repairs_per_candidate: int = 1


def harness_command(spec: CampaignDockerSpec) -> list[str]:
    """Return the ``python -m scripts.bench.harness`` argv for ``spec``."""

    import json

    cmd = [
        "python",
        "-m",
        "scripts.bench.harness",
        "--adapter",
        spec.adapter,
        "--strategy",
        spec.strategy,
        "--subset",
        spec.subset,
        "--out-dir",
        spec.out_dir,
        "--seed",
        str(int(spec.seed)),
        "--max-candidates",
        str(int(spec.max_candidates)),
        "--max-repair-rounds",
        str(int(spec.max_repair_rounds)),
        "--max-repairs-per-candidate",
        str(int(spec.max_repairs_per_candidate)),
        "--extras",
        json.dumps(dict(spec.extras), sort_keys=True),
    ]
    return cmd


def expected_volumes(spec: CampaignDockerSpec, repo_root: Path | str = ".") -> list[str]:
    """Return the canonical bind mounts needed for a campaign run."""

    repo_root = str(repo_root)
    return [
        f"{repo_root}/{spec.out_dir}:/app/{spec.out_dir}",
        f"{repo_root}/workspaces/migrationbench_v10:/app/workspaces/migrationbench_v10",
        f"{repo_root}/external:/app/external",
    ]


__all__ = [
    "CampaignDockerSpec",
    "expected_volumes",
    "harness_command",
]
