"""Create the principal scientific notebook for TravelPlanner organization philosophies."""

from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK_PATH = (
    REPO_ROOT
    / "output"
    / "jupyter-notebook"
    / "travelplanner-organization-philosophy-scientific-comparison-openrouter-qwen35-9b.ipynb"
)


def markdown_cell(text: str) -> dict:
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": [line + "\n" for line in text.strip().splitlines()],
    }


def code_cell(text: str) -> dict:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [line + "\n" for line in text.strip().splitlines()],
    }


INTRO = """
# Experiment: TravelPlanner Organization-Philosophy Scientific Comparison on OpenRouter Qwen3.5-9B

This notebook is the **principal publication-oriented benchmark notebook** for the thesis.

## Research question

At backbone-constant conditions and under the official TravelPlanner scorer, does the stigmergic organization outperform reproducible centralized or monolithic organizations, and at what operational cost?

## Compared organization philosophies

- **Direct Solo**
- **CoT Solo**
- **Self-Refine Solo**
- **Central Planner-Executor**
- **Central Graph Supervisor**
- **StigmergiAgentic**

## Controlled dimensions

- provider: **OpenRouter**
- model: **`qwen/qwen3.5-9b`**
- split: **`validation`**
- scorer: **official TravelPlanner scorer** from this repository
- output contract: `query_XXX.json -> runs.json -> official_eval.json`
- execution mode: **Docker-first**

## Scientific protocol

- primary endpoint: **Final Pass Rate**
- secondary endpoints: delivery, commonsense micro/macro, hard-constraint micro/macro, cost, time, coordination overhead, reproducibility
- replications: **3 seeds** (`42`, `43`, `44`)
- gating: **preflight -> pilot -> full**
- invalid runs are classified as `infra_failure`, `framework_failure`, or `partial_success`; they are **not** converted into score `0`
"""


HELPERS = """
from __future__ import annotations

import hashlib
import json
import os
import shlex
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from IPython.display import Markdown, display


def _find_repo_root() -> Path:
    candidate = Path.cwd().resolve()
    for _ in range(6):
        if (candidate / 'main.py').exists():
            return candidate
        candidate = candidate.parent
    raise RuntimeError(f'Cannot find repository root from {Path.cwd()}')


REPO_ROOT = _find_repo_root()
os.chdir(REPO_ROOT)


def run_command(
    cmd: list[str],
    *,
    cwd: Path = REPO_ROOT,
    check: bool = True,
    log_path: Path | None = None,
    env: dict[str, str] | None = None,
    live: bool = False,
) -> subprocess.CompletedProcess[str]:
    merged_env = os.environ.copy()
    if env:
        merged_env.update({key: str(value) for key, value in env.items()})
    print('$', shlex.join(cmd))
    if live:
        process = subprocess.Popen(
            cmd,
            cwd=str(cwd),
            env=merged_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        chunks: list[str] = []
        assert process.stdout is not None
        for line in process.stdout:
            chunks.append(line)
            print(line, end='')
        process.wait()
        stdout = ''.join(chunks)
        stderr = ''
        returncode = int(process.returncode or 0)
    else:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            env=merged_env,
            capture_output=True,
            text=True,
            check=False,
        )
        stdout = proc.stdout
        stderr = proc.stderr
        returncode = proc.returncode
    combined = stdout + ('' if not stderr else ('\\n' + stderr))
    if log_path is not None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(combined, encoding='utf-8')
    if (not live) and combined.strip():
        print(combined.strip()[:16000])
    if check and returncode != 0:
        raise RuntimeError(f'Command failed with exit={returncode}: {shlex.join(cmd)}')
    return subprocess.CompletedProcess(cmd, returncode, stdout, stderr)


def run_docker_python(
    python_args: list[str],
    *,
    log_path: Path | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    cmd = ['docker', 'compose', 'run', '--rm', '-e', 'PYTHONUNBUFFERED=1', 'travelplanner-smoke', 'python', *python_args]
    return run_command(cmd, cwd=REPO_ROOT, check=check, log_path=log_path, live=True)


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding='utf-8'))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\\n', encoding='utf-8')


def require_path(path: Path) -> Path:
    if not path.exists():
        raise FileNotFoundError(path)
    return path


def render_markdown_file(path: Path) -> None:
    require_path(path)
    display(Markdown(path.read_text(encoding='utf-8')))


def git_sha() -> str:
    return run_command(['git', 'rev-parse', 'HEAD'], cwd=REPO_ROOT).stdout.strip()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def ensure_travelplanner_smoke_image(
    *,
    log_path: Path,
    force_build: bool = False,
    skip_build: bool = False,
) -> dict[str, Any]:
    if shutil.which('docker') is None:
        raise RuntimeError(
            'Docker CLI is not available in the current environment. '
            'Install Docker Desktop or relaunch Jupyter from a shell where `docker` is on PATH.'
        )
    tracked_inputs = [
        REPO_ROOT / 'Dockerfile',
        REPO_ROOT / 'docker-compose.yml',
        REPO_ROOT / 'requirements.txt',
    ]
    signature = {
        path.name: sha256_file(path)
        for path in tracked_inputs
        if path.exists()
    }
    cache_path = REPO_ROOT / 'output' / 'docker_cache' / 'travelplanner_scientific_build_state.json'
    cached = load_json(cache_path, {})

    if skip_build:
        print('Skipping Docker build because TRAVELPLANNER_COMPARE_SKIP_DOCKER_BUILD=1.')
        return {'skipped': True, 'reason': 'env_skip'}
    if (not force_build) and isinstance(cached, dict) and cached.get('signature') == signature:
        print('Skipping Docker build: cached image inputs are unchanged.')
        return {'skipped': True, 'reason': 'cached'}

    run_command(
        ['docker', 'compose', 'build', '--progress=plain', 'travelplanner-smoke'],
        cwd=REPO_ROOT,
        log_path=log_path,
        live=True,
    )
    write_json(
        cache_path,
        {
            'signature': signature,
            'updated_at_utc': datetime.now(timezone.utc).isoformat(),
        },
    )
    return {'skipped': False}
"""


CONFIG = """
RUN_TAG = os.environ.get('TRAVELPLANNER_COMPARE_RUN_TAG') or datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
MODEL_NAME = os.environ.get('TRAVELPLANNER_COMPARE_MODEL', 'qwen/qwen3.5-9b')
OPENROUTER_BASE_URL = os.environ.get('TRAVELPLANNER_COMPARE_BASE_URL', 'https://openrouter.ai/api/v1')
SPLIT = os.environ.get('TRAVELPLANNER_COMPARE_SPLIT', 'validation')
SEEDS = os.environ.get('TRAVELPLANNER_COMPARE_SEEDS', '42,43,44')
STUDY_ARMS = os.environ.get(
    'TRAVELPLANNER_COMPARE_ARMS',
    'solo_direct,solo_cot,solo_self_refine,planner_executor,langgraph_supervisor,stigmergiagentic',
)
PREFLIGHT_COUNT = int(os.environ.get('TRAVELPLANNER_COMPARE_PREFLIGHT_COUNT', '3'))
PILOT_COUNT = int(os.environ.get('TRAVELPLANNER_COMPARE_PILOT_COUNT', '20'))
FULL_COUNT = int(os.environ.get('TRAVELPLANNER_COMPARE_FULL_COUNT', '180'))
DOCKER_FORCE_BUILD = os.environ.get('TRAVELPLANNER_COMPARE_FORCE_DOCKER_BUILD', '0') == '1'
DOCKER_SKIP_BUILD = os.environ.get('TRAVELPLANNER_COMPARE_SKIP_DOCKER_BUILD', '0') == '1'
RUN_PREFLIGHT = os.environ.get('TRAVELPLANNER_COMPARE_RUN_PREFLIGHT', '1') == '1'
RUN_PILOT = os.environ.get('TRAVELPLANNER_COMPARE_RUN_PILOT', '1') == '1'
RUN_FULL = os.environ.get('TRAVELPLANNER_COMPARE_RUN_FULL', '1') == '1'
BUILD_PACK = os.environ.get('TRAVELPLANNER_COMPARE_BUILD_PACK', '1') == '1'

SOLO_DIRECT_BUDGET = float(os.environ.get('TRAVELPLANNER_COMPARE_SOLO_DIRECT_BUDGET_USD', '20'))
SOLO_COT_BUDGET = float(os.environ.get('TRAVELPLANNER_COMPARE_SOLO_COT_BUDGET_USD', '20'))
SOLO_SELF_REFINE_BUDGET = float(os.environ.get('TRAVELPLANNER_COMPARE_SOLO_SELF_REFINE_BUDGET_USD', '20'))
PLANNER_EXECUTOR_BUDGET = float(os.environ.get('TRAVELPLANNER_COMPARE_PLANNER_EXECUTOR_BUDGET_USD', '20'))
LANGGRAPH_BUDGET = float(os.environ.get('TRAVELPLANNER_COMPARE_LANGGRAPH_BUDGET_USD', '20'))
OUR_BUDGET = float(os.environ.get('TRAVELPLANNER_COMPARE_OUR_BUDGET_USD', '20'))
LANGGRAPH_MAX_VALIDATION_RETRIES = int(os.environ.get('TRAVELPLANNER_COMPARE_LANGGRAPH_MAX_VALIDATION_RETRIES', '2'))
OUR_MAX_TICKS = int(os.environ.get('TRAVELPLANNER_COMPARE_OUR_MAX_TICKS', '30'))
OUR_AGENTS = int(os.environ.get('TRAVELPLANNER_COMPARE_OUR_AGENTS', '3'))

COMPARE_ROOT = REPO_ROOT / 'output' / 'travelplanner_framework_compare' / RUN_TAG
PACK_ROOT = COMPARE_ROOT / 'scientific_pack'
NOTEBOOK_ENV_JSON = PACK_ROOT / 'environment_summary.json'
MAIN_TABLE_MD = PACK_ROOT / 'paper_table_main.md'
MAIN_TABLE_CSV = PACK_ROOT / 'paper_table_main.csv'
SECONDARY_CSV = PACK_ROOT / 'paper_table_secondary.csv'
PAIRWISE_MD = PACK_ROOT / 'pairwise_final_pass_stats.md'
PAIRWISE_JSON = PACK_ROOT / 'pairwise_final_pass_stats.json'
PARETO_CSV = PACK_ROOT / 'pareto_summary.csv'
REPRO_MD = PACK_ROOT / 'reproducibility_report.md'
THREATS_MD = PACK_ROOT / 'threats_to_validity.md'
DSR_MD = PACK_ROOT / 'dsr_episode1_summary.md'

COMPARE_ROOT.mkdir(parents=True, exist_ok=True)
PACK_ROOT.mkdir(parents=True, exist_ok=True)
{
    'run_tag': RUN_TAG,
    'study_root': str(COMPARE_ROOT),
    'pack_root': str(PACK_ROOT),
    'model_name': MODEL_NAME,
    'split': SPLIT,
    'arms': STUDY_ARMS,
    'seeds': SEEDS,
}
"""


ENVIRONMENT = """
environment_payload = {
    'run_tag': RUN_TAG,
    'study_root': str(COMPARE_ROOT),
    'repo_root': str(REPO_ROOT),
    'git_sha': git_sha(),
    'utc_started_at': datetime.now(timezone.utc).isoformat(),
    'docker_inputs': {
        'Dockerfile': sha256_file(REPO_ROOT / 'Dockerfile'),
        'docker-compose.yml': sha256_file(REPO_ROOT / 'docker-compose.yml'),
        'requirements.txt': sha256_file(REPO_ROOT / 'requirements.txt'),
    },
    'controlled_dimensions': {
        'provider': 'openrouter',
        'model': MODEL_NAME,
        'base_url': OPENROUTER_BASE_URL,
        'split': SPLIT,
        'temperature': 0.0,
        'request_timeout_seconds': 120,
        'retry_attempts': 2,
        'max_response_tokens': 512,
        'reasoning': {'effort': 'none', 'exclude': True},
    },
    'arms': [
        {'id': 'solo_direct', 'label': 'Direct Solo', 'budget_usd': SOLO_DIRECT_BUDGET},
        {'id': 'solo_cot', 'label': 'CoT Solo', 'budget_usd': SOLO_COT_BUDGET},
        {'id': 'solo_self_refine', 'label': 'Self-Refine Solo', 'budget_usd': SOLO_SELF_REFINE_BUDGET},
        {'id': 'planner_executor', 'label': 'Central Planner-Executor', 'budget_usd': PLANNER_EXECUTOR_BUDGET},
        {'id': 'langgraph_supervisor', 'label': 'Central Graph Supervisor', 'budget_usd': LANGGRAPH_BUDGET},
        {'id': 'stigmergiagentic', 'label': 'StigmergiAgentic', 'budget_usd': OUR_BUDGET},
    ],
    'seeds': [int(item) for item in SEEDS.split(',') if item.strip()],
}
write_json(NOTEBOOK_ENV_JSON, environment_payload)
display(pd.DataFrame(environment_payload['arms']))
environment_payload
"""


DATASET = """
ensure_travelplanner_smoke_image(
    log_path=COMPARE_ROOT / 'docker_build.log',
    force_build=DOCKER_FORCE_BUILD,
    skip_build=DOCKER_SKIP_BUILD,
)

run_docker_python(
    ['scripts/setup_travelplanner.py'],
    log_path=COMPARE_ROOT / 'setup_data.log',
)

count_proc = run_docker_python(
    ['-c', "from datasets import load_dataset; ds = load_dataset('osunlp/TravelPlanner', 'validation'); print(len(ds['validation']))"],
    log_path=COMPARE_ROOT / 'dataset_count.log',
)
validation_count = int(count_proc.stdout.strip().splitlines()[-1])
assert validation_count == 180, validation_count
print('validation_count=', validation_count)
"""


STUDY_MATRIX = """
matrix_rows = []
for arm in [item.strip() for item in STUDY_ARMS.split(',') if item.strip()]:
    for seed in [int(item) for item in SEEDS.split(',') if item.strip()]:
        matrix_rows.append(
            {
                'arm': arm,
                'seed': seed,
                'preflight_queries': PREFLIGHT_COUNT,
                'pilot_queries': PILOT_COUNT,
                'full_queries': FULL_COUNT,
            }
        )
pd.DataFrame(matrix_rows)
"""


PREFLIGHT = """
if RUN_PREFLIGHT:
    run_docker_python(
        [
            'scripts/run_travelplanner_scientific_study.py',
            '--study-root', f'/app/{COMPARE_ROOT.relative_to(REPO_ROOT).as_posix()}',
            '--provider', 'openrouter',
            '--model', MODEL_NAME,
            '--base-url', OPENROUTER_BASE_URL,
            '--split', SPLIT,
            '--arms', STUDY_ARMS,
            '--seeds', SEEDS,
            '--stage', 'preflight',
            '--preflight-count', str(PREFLIGHT_COUNT),
            '--pilot-count', str(PILOT_COUNT),
            '--full-count', str(FULL_COUNT),
            '--solo-direct-budget-usd', str(SOLO_DIRECT_BUDGET),
            '--solo-cot-budget-usd', str(SOLO_COT_BUDGET),
            '--solo-self-refine-budget-usd', str(SOLO_SELF_REFINE_BUDGET),
            '--planner-executor-budget-usd', str(PLANNER_EXECUTOR_BUDGET),
            '--langgraph-budget-usd', str(LANGGRAPH_BUDGET),
            '--stigmergiagentic-budget-usd', str(OUR_BUDGET),
            '--max-validation-retries', str(LANGGRAPH_MAX_VALIDATION_RETRIES),
            '--our-max-ticks', str(OUR_MAX_TICKS),
            '--our-agents', str(OUR_AGENTS),
        ],
        log_path=COMPARE_ROOT / 'preflight.log',
    )

registry_df = pd.read_csv(PACK_ROOT / 'run_registry.csv')
registry_df[registry_df['stage'] == 'preflight']
"""


PILOT = """
if RUN_PILOT:
    run_docker_python(
        [
            'scripts/run_travelplanner_scientific_study.py',
            '--study-root', f'/app/{COMPARE_ROOT.relative_to(REPO_ROOT).as_posix()}',
            '--provider', 'openrouter',
            '--model', MODEL_NAME,
            '--base-url', OPENROUTER_BASE_URL,
            '--split', SPLIT,
            '--arms', STUDY_ARMS,
            '--seeds', SEEDS,
            '--stage', 'pilot',
            '--preflight-count', str(PREFLIGHT_COUNT),
            '--pilot-count', str(PILOT_COUNT),
            '--full-count', str(FULL_COUNT),
            '--solo-direct-budget-usd', str(SOLO_DIRECT_BUDGET),
            '--solo-cot-budget-usd', str(SOLO_COT_BUDGET),
            '--solo-self-refine-budget-usd', str(SOLO_SELF_REFINE_BUDGET),
            '--planner-executor-budget-usd', str(PLANNER_EXECUTOR_BUDGET),
            '--langgraph-budget-usd', str(LANGGRAPH_BUDGET),
            '--stigmergiagentic-budget-usd', str(OUR_BUDGET),
            '--max-validation-retries', str(LANGGRAPH_MAX_VALIDATION_RETRIES),
            '--our-max-ticks', str(OUR_MAX_TICKS),
            '--our-agents', str(OUR_AGENTS),
        ],
        log_path=COMPARE_ROOT / 'pilot.log',
    )

registry_df = pd.read_csv(PACK_ROOT / 'run_registry.csv')
registry_df[registry_df['stage'] == 'pilot']
"""


FULL = """
if RUN_FULL:
    run_docker_python(
        [
            'scripts/run_travelplanner_scientific_study.py',
            '--study-root', f'/app/{COMPARE_ROOT.relative_to(REPO_ROOT).as_posix()}',
            '--provider', 'openrouter',
            '--model', MODEL_NAME,
            '--base-url', OPENROUTER_BASE_URL,
            '--split', SPLIT,
            '--arms', STUDY_ARMS,
            '--seeds', SEEDS,
            '--stage', 'full',
            '--preflight-count', str(PREFLIGHT_COUNT),
            '--pilot-count', str(PILOT_COUNT),
            '--full-count', str(FULL_COUNT),
            '--solo-direct-budget-usd', str(SOLO_DIRECT_BUDGET),
            '--solo-cot-budget-usd', str(SOLO_COT_BUDGET),
            '--solo-self-refine-budget-usd', str(SOLO_SELF_REFINE_BUDGET),
            '--planner-executor-budget-usd', str(PLANNER_EXECUTOR_BUDGET),
            '--langgraph-budget-usd', str(LANGGRAPH_BUDGET),
            '--stigmergiagentic-budget-usd', str(OUR_BUDGET),
            '--max-validation-retries', str(LANGGRAPH_MAX_VALIDATION_RETRIES),
            '--our-max-ticks', str(OUR_MAX_TICKS),
            '--our-agents', str(OUR_AGENTS),
        ],
        log_path=COMPARE_ROOT / 'full.log',
    )

registry_df = pd.read_csv(PACK_ROOT / 'run_registry.csv')
registry_df[registry_df['stage'] == 'full']
"""


PACK = """
if BUILD_PACK:
    run_docker_python(
        [
            'scripts/build_travelplanner_scientific_pack.py',
            '--study-root', f'/app/{COMPARE_ROOT.relative_to(REPO_ROOT).as_posix()}',
            '--canonical-seed', '42',
        ],
        log_path=COMPARE_ROOT / 'build_scientific_pack.log',
    )

for path in [
    MAIN_TABLE_MD,
    MAIN_TABLE_CSV,
    SECONDARY_CSV,
    PAIRWISE_MD,
    PAIRWISE_JSON,
    PARETO_CSV,
    REPRO_MD,
    THREATS_MD,
    DSR_MD,
]:
    require_path(path)
"""


SHOW_MAIN = """
render_markdown_file(MAIN_TABLE_MD)
pd.read_csv(MAIN_TABLE_CSV)
"""


SHOW_PAIRWISE = """
render_markdown_file(PAIRWISE_MD)
load_json(PAIRWISE_JSON)
"""


SHOW_OPERATIONS = """
pd.read_csv(PARETO_CSV)
"""


SHOW_REPRO = """
render_markdown_file(REPRO_MD)
"""


SHOW_DSR = """
render_markdown_file(DSR_MD)
render_markdown_file(THREATS_MD)
"""


def main() -> int:
    cells = [
        markdown_cell(INTRO),
        code_cell(HELPERS),
        markdown_cell("## Environment and Reproducibility"),
        code_cell(CONFIG),
        code_cell(ENVIRONMENT),
        markdown_cell("## Dataset Sanity Checks"),
        code_cell(DATASET),
        markdown_cell("## Study Matrix"),
        code_cell(STUDY_MATRIX),
        markdown_cell("## Preflight Gate"),
        code_cell(PREFLIGHT),
        markdown_cell("## Pilot Gate"),
        code_cell(PILOT),
        markdown_cell("## Full Benchmark"),
        code_cell(FULL),
        markdown_cell("## Official Scores"),
        code_cell(PACK),
        code_cell(SHOW_MAIN),
        markdown_cell("## Paired Statistical Analysis"),
        code_cell(SHOW_PAIRWISE),
        markdown_cell("## Operational Analysis"),
        code_cell(SHOW_OPERATIONS),
        markdown_cell("## Reproducibility and Failures"),
        code_cell(SHOW_REPRO),
        markdown_cell("## DSR / FEDS Pack"),
        code_cell(SHOW_DSR),
    ]

    notebook = {
        "cells": cells,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {
                "name": "python",
                "version": "3.11",
            },
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }

    NOTEBOOK_PATH.parent.mkdir(parents=True, exist_ok=True)
    NOTEBOOK_PATH.write_text(json.dumps(notebook, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {NOTEBOOK_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
