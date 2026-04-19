"""Create the principal TravelPlanner comparison notebook without SwarmAgentic."""

from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK_PATH = (
    REPO_ROOT
    / "output"
    / "jupyter-notebook"
    / "travelplanner-framework-comparison-openrouter-qwen35-9b.ipynb"
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
# Experiment: TravelPlanner Scientific Comparison on OpenRouter Qwen3.5-9B

This notebook is the **principal evaluation notebook** for the thesis benchmark on TravelPlanner.

## Compared arms

- **Solo**
- **LangGraph Supervisor**
- **StigmergiAgentic**

## Controlled dimensions

All three arms are evaluated with:

- provider: **OpenRouter**
- model: **`qwen/qwen3.5-9b`**
- split: **`validation`**
- scorer: **official TravelPlanner scorer** from this repository
- output contract: `runs.json -> official_eval.json`

## Execution protocol

- **Docker-first**: the notebook only pilots repository scripts or Docker commands
- **SwarmAgentic is retired from the principal protocol**
- `Solo` and `StigmergiAgentic` can either be rerun or loaded from a prior reference run
- `LangGraph Supervisor` is the new centralized reproducible baseline

## Scientific note

If you reuse prior `Solo` / `StigmergiAgentic` artifacts instead of rerunning them, the official score comparison remains valid, but runtime-level metrics such as wall-clock time may be partially unavailable for those reused arms.
"""


HELPERS = """
from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import shlex
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yaml
from IPython.display import display


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
        output_chunks: list[str] = []
        assert process.stdout is not None
        for line in process.stdout:
            output_chunks.append(line)
            print(line, end='')
        process.wait()
        stdout = ''.join(output_chunks)
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


def to_container_path(path: Path) -> str:
    relative = path.resolve().relative_to(REPO_ROOT.resolve())
    return '/app/' + relative.as_posix()


def run_docker_python(
    python_args: list[str],
    *,
    log_path: Path | None = None,
    check: bool = True,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    cmd = ['docker', 'compose', 'run', '--rm', '-e', 'PYTHONUNBUFFERED=1']
    for key, value in (env or {}).items():
        cmd.extend(['-e', f'{key}={value}'])
    cmd.extend(['travelplanner-smoke', 'python', *python_args])
    return run_command(cmd, cwd=REPO_ROOT, check=check, log_path=log_path, env=None, live=True)


def _sha256_file(path: Path) -> str:
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
        path.name: _sha256_file(path)
        for path in tracked_inputs
        if path.exists()
    }
    cache_path = REPO_ROOT / 'output' / 'docker_cache' / 'travelplanner_smoke_build_state.json'
    cached = load_json(cache_path, {})

    if skip_build:
        print('Skipping Docker build because TRAVELPLANNER_COMPARE_SKIP_DOCKER_BUILD=1.')
        return {'skipped': True, 'reason': 'env_skip', 'cache_path': str(cache_path)}

    if (not force_build) and isinstance(cached, dict) and cached.get('signature') == signature:
        print('Skipping Docker build: cached image inputs are unchanged.')
        return {'skipped': True, 'reason': 'cached', 'cache_path': str(cache_path)}

    build_cmd = ['docker', 'compose', 'build', '--progress=plain', 'travelplanner-smoke']
    run_command(build_cmd, cwd=REPO_ROOT, check=True, log_path=log_path, live=True)
    write_json(
        cache_path,
        {
            'signature': signature,
            'updated_at': datetime.now(timezone.utc).isoformat(),
        },
    )
    return {'skipped': False, 'cache_path': str(cache_path)}


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
"""


CONFIG = """
RUN_TAG = os.environ.get('TRAVELPLANNER_COMPARE_RUN_TAG') or datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
REFERENCE_RUN_TAG = os.environ.get('TRAVELPLANNER_REFERENCE_RUN_TAG', '20260326_132646')
MODEL_NAME = os.environ.get('TRAVELPLANNER_COMPARE_MODEL', 'qwen/qwen3.5-9b')
OPENROUTER_BASE_URL = os.environ.get('TRAVELPLANNER_COMPARE_BASE_URL', 'https://openrouter.ai/api/v1')
SPLIT = os.environ.get('TRAVELPLANNER_COMPARE_SPLIT', 'validation')
MAX_QUERIES = int(os.environ.get('TRAVELPLANNER_COMPARE_MAX_QUERIES', '180'))
DOCKER_FORCE_BUILD = os.environ.get('TRAVELPLANNER_COMPARE_FORCE_DOCKER_BUILD', '0') == '1'
DOCKER_SKIP_BUILD = os.environ.get('TRAVELPLANNER_COMPARE_SKIP_DOCKER_BUILD', '0') == '1'

RUN_SOLO = os.environ.get('TRAVELPLANNER_COMPARE_RUN_SOLO', '0') == '1'
RUN_LANGGRAPH = os.environ.get('TRAVELPLANNER_COMPARE_RUN_LANGGRAPH', '1') == '1'
RUN_OUR = os.environ.get('TRAVELPLANNER_COMPARE_RUN_OUR', '0') == '1'

SOLO_MAX_BUDGET_USD = float(os.environ.get('TRAVELPLANNER_COMPARE_SOLO_BUDGET_USD', '20'))
LANGGRAPH_MAX_BUDGET_USD = float(os.environ.get('TRAVELPLANNER_COMPARE_LANGGRAPH_BUDGET_USD', '20'))
LANGGRAPH_MAX_VALIDATION_RETRIES = int(os.environ.get('TRAVELPLANNER_COMPARE_LANGGRAPH_MAX_VALIDATION_RETRIES', '2'))
OUR_MAX_BUDGET_USD = float(os.environ.get('TRAVELPLANNER_COMPARE_OUR_BUDGET_USD', '20'))
OUR_MAX_TICKS = int(os.environ.get('TRAVELPLANNER_COMPARE_OUR_MAX_TICKS', '30'))
OUR_AGENT_COUNT = int(os.environ.get('TRAVELPLANNER_COMPARE_OUR_AGENTS', '3'))

COMPARE_ROOT = REPO_ROOT / 'output' / 'travelplanner_framework_compare' / RUN_TAG
REFERENCE_ROOT = REPO_ROOT / 'output' / 'travelplanner_framework_compare' / REFERENCE_RUN_TAG
SOLO_ROOT = COMPARE_ROOT / 'solo'
LANGGRAPH_ROOT = COMPARE_ROOT / 'langgraph_supervisor'
OUR_ROOT = COMPARE_ROOT / 'stigmergiagentic'
TABLE_ROOT = COMPARE_ROOT / 'comparison_langgraph'

SOLO_CONFIG_PATH = SOLO_ROOT / 'config_qwen35_9b_openrouter.yaml'
LANGGRAPH_CONFIG_PATH = LANGGRAPH_ROOT / 'config_qwen35_9b_openrouter.yaml'
OUR_CONFIG_PATH = OUR_ROOT / 'config_qwen35_9b_openrouter.yaml'

ACTIVE_SOLO_RUNS_JSON = SOLO_ROOT / 'runs.json'
ACTIVE_SOLO_OFFICIAL_JSON = SOLO_ROOT / 'official_eval.json'
ACTIVE_LANGGRAPH_RUNS_JSON = LANGGRAPH_ROOT / 'runs.json'
ACTIVE_LANGGRAPH_OFFICIAL_JSON = LANGGRAPH_ROOT / 'official_eval.json'
ACTIVE_OUR_RUNS_JSON = OUR_ROOT / 'runs.json'
ACTIVE_OUR_OFFICIAL_JSON = OUR_ROOT / 'official_eval.json'

SOLO_RUNS_JSON = ACTIVE_SOLO_RUNS_JSON if RUN_SOLO else REFERENCE_ROOT / 'solo' / 'runs.json'
SOLO_OFFICIAL_JSON = ACTIVE_SOLO_OFFICIAL_JSON if RUN_SOLO else REFERENCE_ROOT / 'solo' / 'official_eval.json'
LANGGRAPH_RUNS_JSON = ACTIVE_LANGGRAPH_RUNS_JSON
LANGGRAPH_OFFICIAL_JSON = ACTIVE_LANGGRAPH_OFFICIAL_JSON
OUR_RUNS_JSON = ACTIVE_OUR_RUNS_JSON if RUN_OUR else REFERENCE_ROOT / 'stigmergiagentic' / 'runs.json'
OUR_OFFICIAL_JSON = ACTIVE_OUR_OFFICIAL_JSON if RUN_OUR else REFERENCE_ROOT / 'stigmergiagentic' / 'official_eval.json'

TABLE_MD = TABLE_ROOT / 'comparison_table.md'
TABLE_CSV = TABLE_ROOT / 'comparison_table.csv'
TABLE_JSON = TABLE_ROOT / 'comparison_table.json'
PAIRWISE_JSON = TABLE_ROOT / 'paired_final_pass.json'
RESOURCE_SUMMARY_JSON = TABLE_ROOT / 'resource_summary.json'
COMPARISON_SUMMARY_JSON = TABLE_ROOT / 'comparison_summary.json'

for directory in [COMPARE_ROOT, SOLO_ROOT, LANGGRAPH_ROOT, OUR_ROOT, TABLE_ROOT]:
    directory.mkdir(parents=True, exist_ok=True)

summary = {
    'run_tag': RUN_TAG,
    'reference_run_tag': REFERENCE_RUN_TAG,
    'model_name': MODEL_NAME,
    'split': SPLIT,
    'max_queries': MAX_QUERIES,
    'run_solo': RUN_SOLO,
    'run_langgraph': RUN_LANGGRAPH,
    'run_our': RUN_OUR,
    'paths': {
        'compare_root': str(COMPARE_ROOT),
        'solo_official_json': str(SOLO_OFFICIAL_JSON),
        'langgraph_official_json': str(LANGGRAPH_OFFICIAL_JSON),
        'our_official_json': str(OUR_OFFICIAL_JSON),
        'table_md': str(TABLE_MD),
    },
}
summary
"""


WRITE_CONFIGS = """
BASE_TRAVELPLANNER_CONFIG = yaml.safe_load((REPO_ROOT / 'config' / 'travelplanner.yaml').read_text(encoding='utf-8'))


def build_openrouter_config(max_budget_usd: float) -> dict[str, Any]:
    cfg = copy.deepcopy(BASE_TRAVELPLANNER_CONFIG)
    cfg.setdefault('travelplanner', {})
    cfg['travelplanner']['database_path'] = 'data/travelplanner/database'
    cfg['travelplanner']['dataset_split'] = SPLIT
    cfg.setdefault('llm', {})
    cfg['llm'].update(
        {
            'provider': 'openrouter',
            'model': MODEL_NAME,
            'base_url': OPENROUTER_BASE_URL,
            'max_budget_usd': max_budget_usd,
            'retry_attempts': 2,
            'request_timeout_seconds': 120,
            'max_response_tokens': 512,
            'reasoning': {'effort': 'none', 'exclude': True},
        }
    )
    return cfg


solo_cfg = build_openrouter_config(SOLO_MAX_BUDGET_USD)
langgraph_cfg = build_openrouter_config(LANGGRAPH_MAX_BUDGET_USD)
our_cfg = build_openrouter_config(OUR_MAX_BUDGET_USD)
our_cfg.setdefault('agents', {})
our_cfg['agents']['num_agents'] = OUR_AGENT_COUNT
our_cfg.setdefault('orchestrator', {})
our_cfg['orchestrator']['max_ticks'] = OUR_MAX_TICKS

for path, payload in [
    (SOLO_CONFIG_PATH, solo_cfg),
    (LANGGRAPH_CONFIG_PATH, langgraph_cfg),
    (OUR_CONFIG_PATH, our_cfg),
]:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding='utf-8')

{
    'solo_config': str(SOLO_CONFIG_PATH),
    'langgraph_config': str(LANGGRAPH_CONFIG_PATH),
    'our_config': str(OUR_CONFIG_PATH),
}
"""


SETUP = """
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
print('validation_count=', count_proc.stdout.strip().splitlines()[-1])
"""


RUN_BENCHMARKS = """
def run_framework_benchmark(
    *,
    framework: str,
    out_dir: Path,
    config_path: Path,
    extra_args: list[str] | None = None,
) -> dict[str, Any]:
    args = [
        'scripts/run_travelplanner_framework_benchmark.py',
        '--framework',
        framework,
        '--out-dir',
        to_container_path(out_dir),
        '--config',
        to_container_path(config_path),
        '--database-root',
        '/app/data/travelplanner/database',
        '--split',
        SPLIT,
        '--max-queries',
        str(MAX_QUERIES),
        '--seed',
        '42',
    ]
    if extra_args:
        args.extend(extra_args)
    run_docker_python(
        args,
        log_path=out_dir / 'benchmark.log',
    )
    summary_path = out_dir / 'benchmark_summary.json'
    return load_json(summary_path, {})


if RUN_SOLO:
    solo_benchmark = run_framework_benchmark(
        framework='solo',
        out_dir=SOLO_ROOT,
        config_path=SOLO_CONFIG_PATH,
    )
else:
    solo_benchmark = {'mode': 'reference', 'runs_json': str(SOLO_RUNS_JSON), 'official_eval_json': str(SOLO_OFFICIAL_JSON)}

if RUN_LANGGRAPH:
    langgraph_benchmark = run_framework_benchmark(
        framework='langgraph_supervisor',
        out_dir=LANGGRAPH_ROOT,
        config_path=LANGGRAPH_CONFIG_PATH,
        extra_args=['--max-validation-retries', str(LANGGRAPH_MAX_VALIDATION_RETRIES)],
    )
else:
    langgraph_benchmark = {'mode': 'reference', 'runs_json': str(LANGGRAPH_RUNS_JSON), 'official_eval_json': str(LANGGRAPH_OFFICIAL_JSON)}

if RUN_OUR:
    our_benchmark = run_framework_benchmark(
        framework='stigmergiagentic',
        out_dir=OUR_ROOT,
        config_path=OUR_CONFIG_PATH,
        extra_args=['--max-ticks', str(OUR_MAX_TICKS), '--agents', str(OUR_AGENT_COUNT)],
    )
else:
    our_benchmark = {'mode': 'reference', 'runs_json': str(OUR_RUNS_JSON), 'official_eval_json': str(OUR_OFFICIAL_JSON)}

for path in [
    SOLO_RUNS_JSON,
    SOLO_OFFICIAL_JSON,
    LANGGRAPH_RUNS_JSON,
    LANGGRAPH_OFFICIAL_JSON,
    OUR_RUNS_JSON,
    OUR_OFFICIAL_JSON,
]:
    require_path(path)

{
    'solo': solo_benchmark,
    'langgraph': langgraph_benchmark,
    'stigmergiagentic': our_benchmark,
}
"""


TABLE_AND_SCORES = """
comparison_runs = [
    ('Solo', SOLO_OFFICIAL_JSON),
    ('LangGraph Supervisor', LANGGRAPH_OFFICIAL_JSON),
    ('StigmergiAgentic', OUR_OFFICIAL_JSON),
]

cmd = ['python', 'scripts/render_travelplanner_comparison_table.py']
for label, path in comparison_runs:
    cmd.extend(['--run', f'{label}={path}'])
cmd.extend([
    '--out-md', str(TABLE_MD),
    '--out-csv', str(TABLE_CSV),
    '--out-json', str(TABLE_JSON),
])
run_command(cmd, cwd=REPO_ROOT, log_path=TABLE_ROOT / 'render_table.log')
print(TABLE_MD.read_text(encoding='utf-8'))
"""


PAIRED_ANALYSIS = """
def load_runs_by_query_idx(path: Path) -> dict[int, dict[str, Any]]:
    payload = load_json(path, {})
    runs = payload.get('runs', []) if isinstance(payload, dict) else []
    result: dict[int, dict[str, Any]] = {}
    for item in runs:
        if not isinstance(item, dict):
            continue
        try:
            query_idx = int(item.get('query_idx'))
        except Exception:
            continue
        result[query_idx] = item
    return result


solo_runs = load_runs_by_query_idx(SOLO_RUNS_JSON)
langgraph_runs = load_runs_by_query_idx(LANGGRAPH_RUNS_JSON)
our_runs = load_runs_by_query_idx(OUR_RUNS_JSON)
common_query_idx = sorted(set(solo_runs) & set(langgraph_runs) & set(our_runs))

paired_rows = []
for query_idx in common_query_idx:
    paired_rows.append(
        {
            'query_idx': query_idx,
            'solo_pass': bool(solo_runs[query_idx].get('final_pass', False)),
            'langgraph_pass': bool(langgraph_runs[query_idx].get('final_pass', False)),
            'stigmergiagentic_pass': bool(our_runs[query_idx].get('final_pass', False)),
        }
    )

paired_df = pd.DataFrame(paired_rows).sort_values('query_idx').reset_index(drop=True)

pairwise_rows = []
for left_label, right_label, left_col, right_col in [
    ('StigmergiAgentic', 'Solo', 'stigmergiagentic_pass', 'solo_pass'),
    ('StigmergiAgentic', 'LangGraph Supervisor', 'stigmergiagentic_pass', 'langgraph_pass'),
    ('LangGraph Supervisor', 'Solo', 'langgraph_pass', 'solo_pass'),
]:
    wins = int(((paired_df[left_col]) & (~paired_df[right_col])).sum())
    losses = int(((~paired_df[left_col]) & (paired_df[right_col])).sum())
    ties = int((paired_df[left_col] == paired_df[right_col]).sum())
    pairwise_rows.append(
        {
            'left': left_label,
            'right': right_label,
            'wins': wins,
            'losses': losses,
            'ties': ties,
            'paired_queries': int(len(paired_df)),
        }
    )

write_json(
    PAIRWISE_JSON,
    {
        'paired_queries': len(paired_df),
        'rows': pairwise_rows,
    },
)

display(paired_df.head())
pd.DataFrame(pairwise_rows)
"""


RESOURCE_ANALYSIS = """
def summarize_arm(label: str, runs_path: Path, official_path: Path) -> dict[str, Any]:
    payload = load_json(runs_path, {})
    runs = payload.get('runs', []) if isinstance(payload, dict) else []
    official = load_json(official_path, {})
    scores = official.get('scores', {}) if isinstance(official, dict) else {}

    tokens_values: list[int] = []
    cost_values: list[float] = []
    runtime_values: list[float] = []
    overhead_values: list[float] = []
    for run in runs:
        summary = run.get('summary', {})
        if not isinstance(summary, dict):
            continue
        tokens_values.append(int(summary.get('tokens_used', 0) or 0))
        cost_values.append(float(summary.get('cost_used', 0.0) or 0.0))
        if summary.get('runtime_seconds') is not None:
            runtime_values.append(float(summary.get('runtime_seconds', 0.0) or 0.0))
        if summary.get('coordination_overhead') is not None:
            overhead_values.append(float(summary.get('coordination_overhead', 0.0) or 0.0))
        elif label == 'Solo':
            overhead_values.append(1.0)
        elif label == 'StigmergiAgentic':
            overhead_values.append(float(summary.get('total_ticks', 0) or 0.0))
        elif label == 'LangGraph Supervisor':
            trace = summary.get('step_trace', [])
            overhead_values.append(float(len(trace) if isinstance(trace, list) else 0.0))

    def avg(values: list[float]) -> float | None:
        if not values:
            return None
        return round(sum(values) / len(values), 4)

    return {
        'method': label,
        'queries': len(runs),
        'official_final_pass_rate': scores.get('final_pass_rate'),
        'official_delivery_rate': scores.get('delivery_rate'),
        'tokens_total': sum(tokens_values),
        'cost_total_usd': round(sum(cost_values), 6),
        'avg_tokens_per_query': avg([float(value) for value in tokens_values]),
        'avg_cost_per_query_usd': avg(cost_values),
        'avg_runtime_seconds': avg(runtime_values),
        'avg_coordination_overhead': avg(overhead_values),
        'runtime_queries_with_data': len(runtime_values),
    }


resource_rows = [
    summarize_arm('Solo', SOLO_RUNS_JSON, SOLO_OFFICIAL_JSON),
    summarize_arm('LangGraph Supervisor', LANGGRAPH_RUNS_JSON, LANGGRAPH_OFFICIAL_JSON),
    summarize_arm('StigmergiAgentic', OUR_RUNS_JSON, OUR_OFFICIAL_JSON),
]
resource_df = pd.DataFrame(resource_rows)
write_json(RESOURCE_SUMMARY_JSON, {'rows': resource_rows})
write_json(
    COMPARISON_SUMMARY_JSON,
    {
        'run_tag': RUN_TAG,
        'reference_run_tag': REFERENCE_RUN_TAG,
        'model_name': MODEL_NAME,
        'split': SPLIT,
        'comparison_runs': [
            {'label': 'Solo', 'official_eval_json': str(SOLO_OFFICIAL_JSON), 'runs_json': str(SOLO_RUNS_JSON)},
            {'label': 'LangGraph Supervisor', 'official_eval_json': str(LANGGRAPH_OFFICIAL_JSON), 'runs_json': str(LANGGRAPH_RUNS_JSON)},
            {'label': 'StigmergiAgentic', 'official_eval_json': str(OUR_OFFICIAL_JSON), 'runs_json': str(OUR_RUNS_JSON)},
        ],
        'resource_rows': resource_rows,
    },
)
resource_df
"""


ARTIFACTS = """
{
    'table_md': str(TABLE_MD),
    'table_csv': str(TABLE_CSV),
    'table_json': str(TABLE_JSON),
    'paired_final_pass_json': str(PAIRWISE_JSON),
    'resource_summary_json': str(RESOURCE_SUMMARY_JSON),
    'comparison_summary_json': str(COMPARISON_SUMMARY_JSON),
}
"""


def main() -> int:
    NOTEBOOK_PATH.parent.mkdir(parents=True, exist_ok=True)
    notebook = {
        "cells": [
            markdown_cell(INTRO),
            code_cell(HELPERS),
            code_cell(CONFIG),
            code_cell(WRITE_CONFIGS),
            code_cell(SETUP),
            markdown_cell("## Benchmark Runs\\n\\nEach arm is executed through the repository's Docker service or loaded from reference artifacts."),
            code_cell(RUN_BENCHMARKS),
            markdown_cell("## Official Comparison Table"),
            code_cell(TABLE_AND_SCORES),
            markdown_cell("## Paired Final-Pass Analysis"),
            code_cell(PAIRED_ANALYSIS),
            markdown_cell("## Cost, Time, and Coordination Overhead"),
            code_cell(RESOURCE_ANALYSIS),
            markdown_cell("## Artifact Paths"),
            code_cell(ARTIFACTS),
        ],
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
    NOTEBOOK_PATH.write_text(json.dumps(notebook, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {NOTEBOOK_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
