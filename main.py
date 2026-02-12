"""CLI entrypoint for Sprint 3 stigmergic runs."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import logging
import logging.handlers
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from git import Repo
from git.exc import GitCommandError, InvalidGitRepositoryError

from environment.pheromone_store import PheromoneStore
from metrics.export import ensure_output_dir, write_manifest_json
from stigmergy.loop import run_loop


DEFAULT_CONFIG_PATH = Path("stigmergy/config.yaml")
PHEROMONE_FILES = ["tasks.json", "status.json", "quality.json"]


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.repo_ref == "":
        args.repo_ref = None

    base_path = Path(__file__).resolve().parent
    load_dotenv(base_path / ".env")

    config = _load_config(path=Path(args.config))
    _apply_cli_overrides(config=config, args=args)
    config.setdefault("runtime", {})
    config["runtime"]["dry_run"] = bool(args.dry_run)
    config["runtime"]["seed"] = args.seed
    config["runtime"]["base_path"] = str(base_path)

    _configure_logging(
        base_path=base_path,
        verbose=bool(args.verbose),
    )
    logger = logging.getLogger("main")

    if args.review:
        if args.repo:
            target_repo_path, _ = _prepare_target_repo(
                repo_spec=args.repo,
                repo_ref=args.repo_ref,
                base_path=base_path,
                config=config,
                resume=True,
            )
        else:
            target_repo_path = base_path / "target_repo"
        return _run_review_mode(config=config, base_path=base_path, target_repo_path=target_repo_path)

    if not args.repo:
        raise ValueError("--repo is required for run/resume modes")

    target_repo_path, repo = _prepare_target_repo(
        repo_spec=args.repo,
        repo_ref=args.repo_ref,
        base_path=base_path,
        config=config,
        resume=bool(args.resume),
    )

    if not args.resume:
        _reset_pheromone_state(base_path=base_path)

    run_id = _build_run_id()
    config["runtime"]["run_id"] = run_id

    manifest = _build_run_manifest(
        run_id=run_id,
        config=config,
        target_repo_path=target_repo_path,
        repo=repo,
        seed=args.seed,
        base_path=base_path,
    )
    config["runtime"]["manifest"] = manifest

    output_dir = Path(config.get("metrics", {}).get("output_dir", "metrics/output"))
    if not output_dir.is_absolute():
        output_dir = base_path / output_dir
    ensure_output_dir(output_dir)
    manifest_path = output_dir / f"run_{run_id}_manifest.json"
    write_manifest_json(path=manifest_path, manifest=manifest)

    logger.info("Starting run_id=%s repo=%s", run_id, target_repo_path)
    result = run_loop(
        config=config,
        target_repo_path=target_repo_path,
    )
    summary = result["summary"]

    logger.info(
        "Run completed run_id=%s stop_reason=%s success_rate=%.3f",
        run_id,
        summary.get("stop_reason", "unknown"),
        float(summary.get("success_rate", 0.0)),
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run stigmergic Python2->Python3 migration")
    parser.add_argument("--repo", type=str, default=None, help="Repository URL or local path")
    parser.add_argument(
        "--repo-ref",
        type=str,
        default=None,
        help="Tag/branch/commit to checkout in target repository",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=str(DEFAULT_CONFIG_PATH),
        help="Config file path",
    )
    parser.add_argument("--max-ticks", type=int, default=None, help="Override loop.max_ticks")
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=None,
        help="Override llm.max_tokens_total",
    )
    parser.add_argument("--model", type=str, default=None, help="Override llm model")
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Override metrics output directory",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    parser.add_argument("--dry-run", action="store_true", help="Disable git commit/revert")
    parser.add_argument(
        "--review",
        action="store_true",
        help="Interactive review for needs_review files",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from existing pheromone state",
    )
    parser.add_argument("--seed", type=int, default=None, help="Seed for reproducibility")
    return parser.parse_args(argv)


def _load_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle) or {}
    if not isinstance(loaded, dict):
        raise ValueError(f"Config must be a mapping: {path}")
    return loaded


def _apply_cli_overrides(config: dict[str, Any], args: argparse.Namespace) -> None:
    if args.max_ticks is not None:
        config.setdefault("loop", {})["max_ticks"] = int(args.max_ticks)
    if args.max_tokens is not None:
        config.setdefault("llm", {})["max_tokens_total"] = int(args.max_tokens)
    if args.model:
        config.setdefault("llm", {})["model"] = str(args.model)
    if args.output_dir:
        config.setdefault("metrics", {})["output_dir"] = str(args.output_dir)


def _configure_logging(base_path: Path, verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    log_dir = base_path / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "stigmergic.log"

    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    stream_handler.setLevel(level)

    file_handler = logging.handlers.RotatingFileHandler(
        log_path,
        maxBytes=1_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)

    logging.basicConfig(
        level=level,
        handlers=[stream_handler, file_handler],
        force=True,
    )


def _is_git_url(value: str) -> bool:
    return value.startswith(("http://", "https://", "git@"))


def _prepare_target_repo(
    repo_spec: str,
    repo_ref: str | None,
    base_path: Path,
    config: dict[str, Any],
    resume: bool,
) -> tuple[Path, Repo]:
    target_repo_path = base_path / "target_repo"
    target_repo_preexisted = target_repo_path.exists()

    if resume and target_repo_path.exists():
        return target_repo_path, _open_or_init_repo(target_repo_path)

    if target_repo_preexisted:
        _clear_target_repo_path(target_repo_path)

    if _is_git_url(repo_spec):
        clone_kwargs: dict[str, Any] = {}
        shallow_clone = bool(config.get("git", {}).get("shallow_clone", True))
        if shallow_clone and not repo_ref:
            clone_kwargs["depth"] = 1
        if target_repo_preexisted:
            temp_clone_path = base_path / ".target_repo_clone_tmp"
            if temp_clone_path.exists():
                shutil.rmtree(temp_clone_path)
            Repo.clone_from(repo_spec, temp_clone_path, **clone_kwargs)
            shutil.copytree(
                temp_clone_path,
                target_repo_path,
                dirs_exist_ok=True,
            )
            shutil.rmtree(temp_clone_path)
        else:
            Repo.clone_from(repo_spec, target_repo_path, **clone_kwargs)
    else:
        source_path = Path(repo_spec).expanduser()
        if not source_path.is_absolute():
            source_path = (base_path / source_path).resolve()
        if not source_path.exists():
            raise FileNotFoundError(f"Repository path not found: {source_path}")
        shutil.copytree(
            source_path,
            target_repo_path,
            dirs_exist_ok=target_repo_preexisted,
            ignore=shutil.ignore_patterns(
                ".git",
                ".venv",
                "__pycache__",
                ".pytest_cache",
                ".mypy_cache",
                ".ruff_cache",
            ),
        )

    repo = _open_or_init_repo(target_repo_path)

    if repo_ref:
        repo.git.checkout(repo_ref)

    _ensure_work_branch(repo=repo, config=config)
    return target_repo_path, repo


def _clear_target_repo_path(target_repo_path: Path) -> None:
    """Clear target repo path while tolerating mounted directories."""
    try:
        shutil.rmtree(target_repo_path)
        return
    except OSError:
        pass

    if not target_repo_path.exists():
        target_repo_path.mkdir(parents=True, exist_ok=True)
        return

    # Mount-backed directories can intermittently fail with EBUSY/ENOTEMPTY.
    # Clearing bottom-up avoids deleting the mountpoint itself.
    for root, dirs, files in os.walk(target_repo_path, topdown=False):
        root_path = Path(root)
        for filename in files:
            (root_path / filename).unlink(missing_ok=True)
        for dirname in dirs:
            dir_path = root_path / dirname
            try:
                dir_path.rmdir()
            except OSError:
                shutil.rmtree(dir_path, ignore_errors=True)


def _ensure_work_branch(repo: Repo, config: dict[str, Any]) -> None:
    branch_prefix = str(config.get("git", {}).get("branch_prefix", "stigmergic-migration"))
    branch_name = f"{branch_prefix}-{_build_run_id()}"
    try:
        repo.git.checkout("-b", branch_name)
    except GitCommandError:
        # Branch can already exist in repeated local runs with same timestamp.
        fallback_name = f"{branch_name}-retry"
        repo.git.checkout("-b", fallback_name)


def _open_or_init_repo(path: Path) -> Repo:
    try:
        return Repo(path, search_parent_directories=False)
    except InvalidGitRepositoryError:
        repo = Repo.init(path)
        repo.git.add(".")
        repo.index.commit("initial")
        return repo


def _reset_pheromone_state(base_path: Path) -> None:
    pheromone_dir = base_path / "pheromones"
    pheromone_dir.mkdir(parents=True, exist_ok=True)

    for filename in PHEROMONE_FILES:
        (pheromone_dir / filename).write_text("{}\n", encoding="utf-8")

    (pheromone_dir / "audit_log.jsonl").write_text("", encoding="utf-8")


def _build_run_manifest(
    run_id: str,
    config: dict[str, Any],
    target_repo_path: Path,
    repo: Repo,
    seed: int | None,
    base_path: Path,
) -> dict[str, Any]:
    config_hash = _hash_json_payload(_normalized_config_for_hash(config))
    prompt_bundle_hash = _hash_text(_prompt_bundle_payload())
    requirements_path = base_path / "requirements.txt"
    dependency_lock_hash = _hash_file(requirements_path)

    return {
        "run_id": run_id,
        "timestamp_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "target_repo_commit": repo.head.commit.hexsha,
        "target_repo_path": str(target_repo_path),
        "config_hash": f"sha256:{config_hash}",
        "prompt_bundle_hash": f"sha256:{prompt_bundle_hash}",
        "model_provider": config.get("llm", {}).get("provider", "openrouter"),
        "model_name": config.get("llm", {}).get("model", ""),
        "seed": seed,
        "python_version": sys.version.split()[0],
        "dependency_lock_hash": f"sha256:{dependency_lock_hash}",
    }


def _normalized_config_for_hash(config: dict[str, Any]) -> dict[str, Any]:
    payload = copy.deepcopy(config)
    runtime = payload.get("runtime", {})
    if isinstance(runtime, dict):
        runtime.pop("manifest", None)
        runtime.pop("run_id", None)
        runtime.pop("tick", None)
    return payload


def _prompt_bundle_payload() -> str:
    return "\n".join(
        [
            "scout_system:You are a Python 2 to Python 3 migration analyst.",
            "transformer_system:You are a Python 2 to Python 3 migration expert. Convert the full file while preserving semantics.",
            "transformer_user:Convert this Python 2 file to Python 3 and return only the complete converted Python 3 file.",
        ]
    )


def _hash_json_payload(payload: dict[str, Any]) -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _hash_file(path: Path) -> str:
    if not path.exists():
        return hashlib.sha256(b"").hexdigest()
    data = path.read_bytes()
    return hashlib.sha256(data).hexdigest()


def _build_run_id() -> str:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    return now.strftime("%Y%m%dT%H%M%SZ")


def _run_review_mode(config: dict[str, Any], base_path: Path, target_repo_path: Path) -> int:
    store = PheromoneStore(config=config, base_path=base_path)
    review_entries = store.query("status", status="needs_review")

    if not review_entries:
        print("No needs_review files found.")
        return 0

    high_threshold = float(config.get("thresholds", {}).get("validator_confidence_high", 0.8))

    for file_key in sorted(review_entries.keys()):
        quality_entry = store.read_one("quality", file_key) or {}
        confidence = float(quality_entry.get("confidence", 0.0))
        issues = quality_entry.get("issues", [])
        print(f"\nFile: {file_key}")
        print(f"Confidence: {confidence:.3f}")
        print(f"Issues: {issues}")
        action = _prompt_review_action(file_key=file_key)

        if action == "validate":
            store.update(
                "quality",
                file_key=file_key,
                agent_id="human_review",
                confidence=max(confidence, high_threshold),
            )
            store.update(
                "status",
                file_key=file_key,
                agent_id="human_review",
                status="validated",
                previous_status="needs_review",
                metadata={"decision": "manual_validate"},
            )
        elif action == "retry":
            retry_count = int(review_entries[file_key].get("retry_count", 0)) + 1
            inhibition = float(review_entries[file_key].get("inhibition", 0.0)) + 0.5
            store.update(
                "status",
                file_key=file_key,
                agent_id="human_review",
                status="retry",
                previous_status="needs_review",
                retry_count=retry_count,
                inhibition=inhibition,
                metadata={"decision": "manual_retry"},
            )
        else:
            store.update(
                "status",
                file_key=file_key,
                agent_id="human_review",
                status="skipped",
                previous_status="needs_review",
                metadata={"decision": "manual_skip"},
            )

    print(f"\nReview updates applied on target repo: {target_repo_path}")
    return 0


def _prompt_review_action(file_key: str) -> str:
    valid_actions = {"validate", "retry", "skip"}
    while True:
        raw = input(f"Choose action for {file_key} [validate/retry/skip]: ").strip().lower()
        if raw in valid_actions:
            return raw
        print("Invalid action. Please choose one of: validate, retry, skip.")


if __name__ == "__main__":
    raise SystemExit(main())
