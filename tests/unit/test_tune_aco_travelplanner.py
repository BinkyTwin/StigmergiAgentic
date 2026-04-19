"""Unit tests for TravelPlanner ACO tuning helpers."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

import scripts.tune_aco_travelplanner as tuning_script


def _write_base_config(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "# V5-full preset",
                "travelplanner:",
                '  dataset_split: "validation"',
                "agents:",
                "  num_agents: 6",
                "  selection_temperature: 0.1",
                "pressures:",
                "  alpha: 1.0",
                "  beta: 2.0",
                "markers:",
                "  session_isolation: true",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_build_grid_returns_expected_18_combinations() -> None:
    grid = tuning_script.build_grid()

    assert len(grid) == 18
    assert {"alpha": 0.5, "beta": 1.0, "temperature": 0.1} in grid
    assert {"alpha": 1.5, "beta": 3.0, "temperature": 0.3} in grid


def test_apply_best_params_to_config_preserves_header_and_updates_values(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "v5_full.yaml"
    _write_base_config(config_path)

    tuning_script.apply_best_params_to_config(
        config_path=config_path,
        combo={"alpha": 1.5, "beta": 3.0, "temperature": 0.3},
    )

    rendered = config_path.read_text(encoding="utf-8")
    loaded = yaml.safe_load(rendered)

    assert rendered.startswith("# V5-full preset")
    assert loaded["agents"]["selection_temperature"] == 0.3
    assert loaded["pressures"]["alpha"] == 1.5
    assert loaded["pressures"]["beta"] == 3.0


def test_run_tuning_writes_results_and_applies_best_combo(
    tmp_path: Path,
    monkeypatch,
) -> None:
    base_config_path = tmp_path / "v5_full.yaml"
    _write_base_config(base_config_path)
    out_dir = tmp_path / "tuning"

    monkeypatch.setattr(
        tuning_script,
        "build_grid",
        lambda: [
            {"alpha": 0.5, "beta": 1.0, "temperature": 0.1},
            {"alpha": 1.5, "beta": 3.0, "temperature": 0.3},
        ],
    )
    monkeypatch.setattr(tuning_script, "utc_timestamp", lambda: "20260416T120000Z")

    def fake_run_benchmark(*, config_path, split, n_queries, seed, out_dir):  # type: ignore[no-untyped-def]
        del split, n_queries, out_dir
        config = yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))
        alpha = float(config["pressures"]["alpha"])
        beta = float(config["pressures"]["beta"])
        temperature = float(config["agents"]["selection_temperature"])
        return {
            "seed": int(seed),
            "final_pass_rate": alpha + beta + temperature,
            "delivery_rate": alpha + beta,
            "official_eval_json": "/tmp/official_eval.json",
            "benchmark_summary_json": "/tmp/benchmark_summary.json",
            "command": ["python"],
            "failure_reasons": {"ok": 5},
        }

    monkeypatch.setattr(tuning_script, "run_benchmark", fake_run_benchmark)

    output = tuning_script.run_tuning(
        [
            "--base-config",
            str(base_config_path),
            "--split",
            "train",
            "--n-queries",
            "5",
            "--seeds",
            "42",
            "43",
            "--out-dir",
            str(out_dir),
            "--apply",
        ]
    )

    results_path = Path(output["results_path"])
    rendered = json.loads(results_path.read_text(encoding="utf-8"))
    updated_config = yaml.safe_load(base_config_path.read_text(encoding="utf-8"))

    assert results_path.exists()
    assert rendered["comment"] == 'Hyperparameter tuning executed on split="train" ONLY.'
    assert rendered["best"]["combo"] == {
        "alpha": 1.5,
        "beta": 3.0,
        "temperature": 0.3,
    }
    assert updated_config["agents"]["selection_temperature"] == 0.3
    assert updated_config["pressures"]["alpha"] == 1.5
    assert updated_config["pressures"]["beta"] == 3.0


def test_validate_args_rejects_non_train_split() -> None:
    args = tuning_script.parse_args(
        [
            "--base-config",
            "config/ablation/v5_full.yaml",
            "--split",
            "validation",
            "--out-dir",
            "output/tuning",
        ]
    )

    try:
        tuning_script.validate_args(args)
    except ValueError as exc:
        assert "only supports --split train" in str(exc)
    else:
        raise AssertionError("validate_args should reject non-train split")
