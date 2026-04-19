"""Grid-tune TravelPlanner ACO hyperparameters on the train split only."""

from __future__ import annotations

import argparse
import copy
import itertools
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
GRID = {
    "alpha": [0.5, 1.0, 1.5],
    "beta": [1.0, 2.0, 3.0],
    "temperature": [0.1, 0.3],
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Tune TravelPlanner ACO hyperparameters on the train split only."
    )
    parser.add_argument("--base-config", type=Path, required=True)
    parser.add_argument("--split", type=str, default="train")
    parser.add_argument("--n-queries", type=int, default=30)
    parser.add_argument("--seeds", type=int, nargs="+", default=[42, 43])
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--apply", action="store_true", default=False)
    return parser.parse_args(argv)


def validate_args(args: argparse.Namespace) -> None:
    if str(args.split).strip().lower() != "train":
        raise ValueError("scripts/tune_aco_travelplanner.py only supports --split train")
    if int(args.n_queries) <= 0:
        raise ValueError("--n-queries must be >= 1")
    if not args.seeds:
        raise ValueError("--seeds must contain at least one seed")


def build_grid() -> list[dict[str, float]]:
    return [
        {
            "alpha": float(alpha),
            "beta": float(beta),
            "temperature": float(temperature),
        }
        for alpha, beta, temperature in itertools.product(
            GRID["alpha"],
            GRID["beta"],
            GRID["temperature"],
        )
    ]


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Config must deserialize to a mapping: {path}")
    return payload


def combo_slug(combo: dict[str, float]) -> str:
    return (
        f"a{combo['alpha']:.1f}_"
        f"b{combo['beta']:.1f}_"
        f"t{combo['temperature']:.1f}"
    ).replace(".", "p")


def build_override_config(
    base_config: dict[str, Any],
    *,
    combo: dict[str, float],
    split: str,
) -> dict[str, Any]:
    config = copy.deepcopy(base_config)
    config.setdefault("travelplanner", {})
    config.setdefault("agents", {})
    config.setdefault("pressures", {})
    config.setdefault("markers", {})

    config["travelplanner"]["dataset_split"] = split
    config["agents"]["selection_temperature"] = float(combo["temperature"])
    config["pressures"]["alpha"] = float(combo["alpha"])
    config["pressures"]["beta"] = float(combo["beta"])
    config["markers"]["session_isolation"] = True
    return config


def write_override_config(
    *,
    base_config: dict[str, Any],
    combo: dict[str, float],
    split: str,
    config_dir: Path,
) -> Path:
    config_dir.mkdir(parents=True, exist_ok=True)
    override_config = build_override_config(
        base_config,
        combo=combo,
        split=split,
    )
    config_path = config_dir / f"{combo_slug(combo)}.yaml"
    config_path.write_text(
        yaml.safe_dump(
            override_config,
            sort_keys=False,
            allow_unicode=False,
        ),
        encoding="utf-8",
    )
    return config_path


def build_benchmark_command(
    *,
    config_path: Path,
    split: str,
    n_queries: int,
    seed: int,
    out_dir: Path,
) -> list[str]:
    return [
        sys.executable,
        "scripts/run_travelplanner_framework_benchmark.py",
        "--framework",
        "stigmergic",
        "--config",
        str(config_path),
        "--split",
        split,
        "--start",
        "0",
        "--end",
        str(int(n_queries) - 1),
        "--seed",
        str(seed),
        "--out-dir",
        str(out_dir),
    ]


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object at {path}")
    return payload


def run_benchmark(
    *,
    config_path: Path,
    split: str,
    n_queries: int,
    seed: int,
    out_dir: Path,
) -> dict[str, Any]:
    command = build_benchmark_command(
        config_path=config_path,
        split=split,
        n_queries=n_queries,
        seed=seed,
        out_dir=out_dir,
    )
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        stdout_tail = "\n".join((completed.stdout or "").splitlines()[-20:])
        stderr_tail = "\n".join((completed.stderr or "").splitlines()[-20:])
        raise RuntimeError(
            "TravelPlanner tuning benchmark failed.\n"
            f"command={' '.join(command)}\n"
            f"stdout_tail={stdout_tail}\n"
            f"stderr_tail={stderr_tail}"
        )

    official_eval = read_json(out_dir / "official_eval.json")
    benchmark_summary = read_json(out_dir / "benchmark_summary.json")
    scores = official_eval.get("scores", {})
    if not isinstance(scores, dict):
        raise ValueError(f"official_eval.json is missing a scores mapping: {out_dir}")

    return {
        "seed": int(seed),
        "final_pass_rate": float(scores.get("final_pass_rate", 0.0)),
        "delivery_rate": float(scores.get("delivery_rate", 0.0)),
        "official_eval_json": str((out_dir / "official_eval.json").resolve()),
        "benchmark_summary_json": str((out_dir / "benchmark_summary.json").resolve()),
        "command": command,
        "failure_reasons": benchmark_summary.get("failure_reasons", {}),
    }


def aggregate_seed_results(seed_results: list[dict[str, Any]]) -> dict[str, float]:
    return {
        "final_pass_rate": mean(
            float(result["final_pass_rate"]) for result in seed_results
        ),
        "delivery_rate": mean(
            float(result["delivery_rate"]) for result in seed_results
        ),
    }


def select_best_result(results: list[dict[str, Any]]) -> dict[str, Any]:
    if not results:
        raise ValueError("No tuning results available")
    return max(
        results,
        key=lambda result: (
            float(result["final_pass_rate"]),
            float(result["delivery_rate"]),
        ),
    )


def _update_scalar_in_section(
    *,
    lines: list[str],
    section: str,
    key: str,
    value: float,
) -> tuple[list[str], bool]:
    rendered_value = repr(float(value))
    current_section = ""
    updated_lines: list[str] = []
    replaced = False
    for line in lines:
        stripped = line.strip()
        if stripped.endswith(":") and not line.startswith((" ", "\t", "#")):
            current_section = stripped[:-1]
        if current_section == section and re.match(rf"^\s*{re.escape(key)}\s*:", line):
            indent = re.match(r"^(\s*)", line).group(1)
            updated_lines.append(f"{indent}{key}: {rendered_value}")
            replaced = True
            continue
        updated_lines.append(line)
    return updated_lines, replaced


def apply_best_params_to_config(
    *,
    config_path: Path,
    combo: dict[str, float],
) -> None:
    lines = config_path.read_text(encoding="utf-8").splitlines()
    lines, replaced_temp = _update_scalar_in_section(
        lines=lines,
        section="agents",
        key="selection_temperature",
        value=combo["temperature"],
    )
    lines, replaced_alpha = _update_scalar_in_section(
        lines=lines,
        section="pressures",
        key="alpha",
        value=combo["alpha"],
    )
    lines, replaced_beta = _update_scalar_in_section(
        lines=lines,
        section="pressures",
        key="beta",
        value=combo["beta"],
    )
    if not all((replaced_temp, replaced_alpha, replaced_beta)):
        raise ValueError(
            "Unable to update one or more hyperparameters in "
            f"{config_path}"
        )
    config_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_tuning(argv: list[str] | None = None) -> dict[str, Any]:
    args = parse_args(argv)
    validate_args(args)

    base_config_path = args.base_config.expanduser().resolve()
    out_dir = args.out_dir.expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    base_config = load_yaml(base_config_path)
    timestamp = utc_timestamp()
    config_dir = out_dir / f"generated_configs_{timestamp}"
    results: list[dict[str, Any]] = []

    for combo in build_grid():
        config_path = write_override_config(
            base_config=base_config,
            combo=combo,
            split="train",
            config_dir=config_dir,
        )
        seed_results: list[dict[str, Any]] = []
        for seed in args.seeds:
            run_dir = out_dir / f"{timestamp}_{combo_slug(combo)}_seed{seed}"
            seed_results.append(
                run_benchmark(
                    config_path=config_path,
                    split="train",
                    n_queries=args.n_queries,
                    seed=seed,
                    out_dir=run_dir,
                )
            )
        aggregate = aggregate_seed_results(seed_results)
        results.append(
            {
                "combo": combo,
                "final_pass_rate": aggregate["final_pass_rate"],
                "delivery_rate": aggregate["delivery_rate"],
                "seed_results": seed_results,
                "config_path": str(config_path.resolve()),
            }
        )

    best_result = select_best_result(results)
    output = {
        "timestamp": timestamp,
        "base_config": str(base_config_path),
        "split": "train",
        "n_queries": int(args.n_queries),
        "seeds": [int(seed) for seed in args.seeds],
        "comment": 'Hyperparameter tuning executed on split="train" ONLY.',
        "results": results,
        "best": best_result,
        "applied": bool(args.apply),
    }

    if args.apply:
        apply_best_params_to_config(
            config_path=base_config_path,
            combo=best_result["combo"],
        )

    results_path = out_dir / f"tuning_results_{timestamp}.json"
    output["results_path"] = str(results_path.resolve())
    results_path.write_text(
        json.dumps(output, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return output


def main(argv: list[str] | None = None) -> int:
    output = run_tuning(argv)
    print(
        json.dumps(
            {
                "results_path": output["results_path"],
                "best": output["best"],
                "applied": output["applied"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
