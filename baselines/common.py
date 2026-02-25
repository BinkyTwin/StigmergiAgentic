"""Shared baseline utilities for Sprint 4 experiments."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

from environment.pheromone_store import PheromoneStore
from main import (
    _apply_cli_overrides,
    _configure_logging,
    _prepare_target_repo,
    _reset_pheromone_state,
)
from metrics.export import (
    ensure_output_dir,
    write_manifest_json,
    write_summary_json,
    write_ticks_csv,
)


DEFAULT_CONFIG_PATH = Path("stigmergy/config.yaml")


def parse_baseline_args(description: str) -> argparse.Namespace:
    """Parse CLI arguments shared by baseline scripts."""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--repo", type=str, required=True, help="Repository URL or local path"
    )
    parser.add_argument(
        "--repo-ref", type=str, default=None, help="Tag/branch/commit to checkout"
    )
    parser.add_argument(
        "--config", type=str, default=str(DEFAULT_CONFIG_PATH), help="Config file path"
    )
    parser.add_argument(
        "--output-dir", type=str, default=None, help="Override metrics output directory"
    )
    parser.add_argument(
        "--max-ticks",
        type=int,
        default=None,
        help="Override max ticks for baseline scheduler",
    )
    parser.add_argument(
        "--max-tokens", type=int, default=None, help="Override global token budget"
    )
    parser.add_argument(
        "--max-budget-usd", type=float, default=None, help="Override global USD budget"
    )
    parser.add_argument("--model", type=str, default=None, help="Override model name")
    parser.add_argument(
        "--seed", type=int, default=None, help="Seed stored in run manifest"
    )
    parser.add_argument("--runs", type=int, default=1, help="Number of repeated runs")
    parser.add_argument(
        "--dry-run", action="store_true", help="Disable git commit/revert mutations"
    )
    parser.add_argument(
        "--resume", action="store_true", help="Reuse existing target_repo checkout"
    )
    parser.add_argument("--verbose", action="store_true", help="Enable debug logs")
    return parser.parse_args()


def load_runtime_config(args: argparse.Namespace, base_path: Path) -> dict[str, Any]:
    """Load and prepare baseline runtime config."""
    load_dotenv(base_path / ".env")
    with Path(args.config).open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle) or {}

    _apply_cli_overrides(config=config, args=args)
    config.setdefault("runtime", {})
    config["runtime"]["dry_run"] = bool(args.dry_run)
    config["runtime"]["seed"] = args.seed
    config["runtime"]["base_path"] = str(base_path)
    return config


def prepare_run_environment(
    args: argparse.Namespace,
    base_path: Path,
    config: dict[str, Any],
    reset_pheromones: bool = True,
) -> tuple[Path, PheromoneStore]:
    """Prepare target repository and pheromone store for one baseline run."""
    target_repo_path, _ = _prepare_target_repo(
        repo_spec=str(args.repo),
        repo_ref=args.repo_ref,
        base_path=base_path,
        config=config,
        resume=bool(args.resume),
    )

    if reset_pheromones:
        _reset_pheromone_state(base_path=base_path)

    store = PheromoneStore(config=config, base_path=base_path)
    return target_repo_path, store


def build_run_id(prefix: str, run_index: int = 1) -> str:
    """Build deterministic UTC run identifier for baseline runs."""
    timestamp = (
        datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y%m%dT%H%M%SZ")
    )
    return f"{prefix}_{timestamp}_r{run_index:02d}"


def build_manifest(
    *,
    run_id: str,
    baseline_name: str,
    config: dict[str, Any],
    target_repo_path: Path,
    seed: int | None,
) -> dict[str, Any]:
    """Build experiment manifest payload for a baseline run."""
    manifest_source = {
        "baseline": baseline_name,
        "config": copy.deepcopy(config),
        "target_repo_path": str(target_repo_path),
        "seed": seed,
    }
    manifest_hash = hashlib.sha256(
        json.dumps(manifest_source, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()

    return {
        "run_id": run_id,
        "baseline": baseline_name,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "target_repo_path": str(target_repo_path),
        "seed": seed,
        "manifest_hash": manifest_hash,
        "model": str(config.get("llm", {}).get("model", "unknown")),
        "max_tokens_total": int(config.get("llm", {}).get("max_tokens_total", 0)),
        "max_budget_usd": float(config.get("llm", {}).get("max_budget_usd", 0.0)),
    }


def persist_run_outputs(
    *,
    config: dict[str, Any],
    run_id: str,
    manifest: dict[str, Any],
    summary: dict[str, Any],
    tick_rows: list[dict[str, Any]],
) -> tuple[Path, Path, Path]:
    """Persist run outputs using the same format as the stigmergic loop."""
    base_path = Path(config.get("runtime", {}).get("base_path", Path.cwd()))
    output_dir = Path(config.get("metrics", {}).get("output_dir", "metrics/output"))
    if not output_dir.is_absolute():
        output_dir = base_path / output_dir

    ensure_output_dir(output_dir)
    ticks_path = output_dir / f"run_{run_id}_ticks.csv"
    summary_path = output_dir / f"run_{run_id}_summary.json"
    manifest_path = output_dir / f"run_{run_id}_manifest.json"

    write_ticks_csv(path=ticks_path, tick_rows=tick_rows)
    write_summary_json(path=summary_path, summary=summary)
    write_manifest_json(path=manifest_path, manifest=manifest)
    return ticks_path, summary_path, manifest_path


def setup_logging(base_path: Path, verbose: bool) -> None:
    """Configure standard project logging handlers."""
    _configure_logging(base_path=base_path, verbose=verbose)
