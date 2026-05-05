from __future__ import annotations

import argparse
import copy
import importlib.util
from pathlib import Path
from types import ModuleType

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
RUNNER_PATH = REPO_ROOT / "scripts" / "run_travelplanner_c3_refactor_campaign.py"


def _load_runner() -> ModuleType:
    spec = importlib.util.spec_from_file_location("c3_refactor_runner", RUNNER_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _config(
    *,
    provider: str = "openrouter",
    model: str = "google/gemma-4-31b-it",
    namespace: str = "travelplanner_c3_gemma_seed42_v1",
    compiler_enabled: bool = True,
    protocol_enabled: bool = True,
) -> dict:
    return {
        "llm": {"provider": provider, "model": model},
        "protocol": {"enabled": protocol_enabled, "namespace": namespace},
        "emergence": {"cross_run": {"enabled": protocol_enabled}},
        "agents": {"protocol_compiler": {"enabled": compiler_enabled}},
    }


def _args(**overrides: object) -> argparse.Namespace:
    values = {
        "expected_provider": "openrouter",
        "expected_model": "google/gemma-4-31b-it",
        "expected_namespace": (
            "coordination_protocol::travelplanner::"
            "travelplanner_c3_gemma_seed42_v1"
        ),
        "expect_compiler": "enabled",
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_apply_arm_overrides_sets_expected_c3_modes() -> None:
    runner = _load_runner()
    cases = {
        "full_c3": (True, True, True, True),
        "protocol_only": (False, True, True, False),
        "skills_only": (True, False, False, False),
        "compiler_only": (False, False, False, True),
    }

    for arm, expected in cases.items():
        config: dict = {}
        runner.apply_arm_overrides(config, arm=arm)
        actual = (
            config["skill_library"]["enabled"],
            config["protocol"]["enabled"],
            config["emergence"]["cross_run"]["enabled"],
            config["agents"]["protocol_compiler"]["enabled"],
        )
        assert actual == expected


def test_preflight_accepts_matching_effective_config(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = _load_runner()
    effective = _config()
    monkeypatch.setattr(
        runner,
        "effective_config",
        lambda _path: copy.deepcopy(effective),
    )
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    manifest = runner.preflight(_args(), Path("adapt.yaml"), Path("eval.yaml"))

    assert manifest["provider"] == "openrouter"
    assert manifest["model"] == "google/gemma-4-31b-it"
    assert manifest["api_key_env"] == "OPENROUTER_API_KEY"
    assert manifest["namespace_adapt"] == manifest["namespace_eval"]
    assert manifest["compiler_enabled"] is True


@pytest.mark.parametrize(
    ("effective", "args_overrides", "env", "message"),
    [
        (_config(model="wrong-model"), {}, {"OPENROUTER_API_KEY": "x"}, "model mismatch"),
        (
            _config(namespace="wrong_namespace"),
            {},
            {"OPENROUTER_API_KEY": "x"},
            "namespace mismatch",
        ),
        (
            _config(compiler_enabled=False),
            {},
            {"OPENROUTER_API_KEY": "x"},
            "protocol compiler expected enabled",
        ),
        (_config(), {}, {}, "missing API key"),
    ],
)
def test_preflight_rejects_invalid_campaign_contract(
    monkeypatch: pytest.MonkeyPatch,
    effective: dict,
    args_overrides: dict,
    env: dict[str, str],
    message: str,
) -> None:
    runner = _load_runner()
    monkeypatch.setattr(
        runner,
        "effective_config",
        lambda _path: copy.deepcopy(effective),
    )
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    with pytest.raises(RuntimeError, match=message):
        runner.preflight(_args(**args_overrides), Path("adapt.yaml"), Path("eval.yaml"))


def test_preflight_rejects_adapt_eval_namespace_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = _load_runner()

    def fake_effective_config(path: Path) -> dict:
        namespace = "adapt_namespace" if "adapt" in str(path) else "eval_namespace"
        return _config(namespace=namespace)

    monkeypatch.setattr(runner, "effective_config", fake_effective_config)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    with pytest.raises(RuntimeError, match="adapt/eval namespace mismatch"):
        runner.preflight(
            _args(expected_namespace="coordination_protocol::travelplanner::eval_namespace"),
            Path("adapt.yaml"),
            Path("eval.yaml"),
        )
