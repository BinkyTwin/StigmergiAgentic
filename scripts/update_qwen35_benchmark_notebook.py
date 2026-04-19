"""Refresh the Qwen TravelPlanner benchmark notebook with the current orchestrator cells."""

from __future__ import annotations

import json
from pathlib import Path


NOTEBOOK_PATH = (
    Path(__file__).resolve().parents[1]
    / "output"
    / "jupyter-notebook"
    / "travelplanner-framework-comparison-openrouter-qwen35-9b.ipynb"
)


CELL_0 = """# Experiment: TravelPlanner 3-Way Comparison on OpenRouter Qwen3.5-9B

This notebook prepares a **same-provider / same-model / same-scorer** comparison between three setups:
- **Solo model**: one direct planning call, no swarm, no multi-agent orchestration
- **StigmergiAgentic V3**: this repository
- **SwarmAgentic**: external framework from [YaoZ720/SwarmAgenticCode](https://github.com/YaoZ720/SwarmAgenticCode/tree/main)

## Controlled dimensions

All three arms are evaluated with:
- provider: **OpenRouter**
- model: **`qwen/qwen3.5-9b`**
- split: **`validation`**
- scorer: **official TravelPlanner scorer** from this repository
- same evaluated query range (`MAX_QUERIES`) for the **full** benchmark

## Benchmark modes

SwarmAgentic can be launched in three modes through `TRAVELPLANNER_COMPARE_SWARM_MODE` (or `TRAVELPLANNER_COMPARE_MODE`):
- `preflight`: verify `team.init()` and a 1-iteration PSO smoke test without running the full comparison
- `pilot`: reduced Swarm run plus a 20-query validation shard
- `full`: thesis-grade benchmark (`5` particles, `10` iterations, `180` validation queries)

Only **full** mode is intended for the final thesis comparison table. Preflight and pilot are reproducibility/debugging stages.

## Important caveat

This notebook controls model/provider/scorer/split, but it does **not** automatically equalize optimization budget between methods. In particular, SwarmAgentic includes a PSO phase before evaluation. So the result is a strong **framework comparison under a shared model**, but not yet a fully cost-matched study.
"""


CELL_5 = """run_command(['python', 'scripts/setup_travelplanner.py'], cwd=REPO_ROOT, check=True, log_path=COMPARE_ROOT / 'setup_data.log')

count_proc = run_command(
    ['python', '-c', "from datasets import load_dataset; ds = load_dataset('osunlp/TravelPlanner', 'validation'); print(len(ds['validation']))"],
    cwd=REPO_ROOT,
    check=True,
    log_path=COMPARE_ROOT / 'dataset_count.log',
)
print('validation_count=', count_proc.stdout.strip().splitlines()[-1])
"""


CELL_3 = """RUN_TAG = os.environ.get('TRAVELPLANNER_COMPARE_RUN_TAG') or datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
MODEL_NAME = os.environ.get('TRAVELPLANNER_COMPARE_MODEL', 'qwen/qwen3.5-9b')
OPENROUTER_BASE_URL = os.environ.get('TRAVELPLANNER_COMPARE_BASE_URL', 'https://openrouter.ai/api/v1')
SPLIT = os.environ.get('TRAVELPLANNER_COMPARE_SPLIT', 'validation')
MAX_QUERIES = int(os.environ.get('TRAVELPLANNER_COMPARE_MAX_QUERIES', '180'))
SOLO_MAX_BUDGET_USD = float(os.environ.get('TRAVELPLANNER_COMPARE_SOLO_BUDGET_USD', '20'))
OUR_MAX_TICKS = int(os.environ.get('TRAVELPLANNER_COMPARE_OUR_MAX_TICKS', '30'))
OUR_AGENT_COUNT = int(os.environ.get('TRAVELPLANNER_COMPARE_OUR_AGENTS', '3'))
OUR_MAX_BUDGET_USD = float(os.environ.get('TRAVELPLANNER_COMPARE_OUR_BUDGET_USD', '20'))

SWARM_BENCHMARK_MODE = os.environ.get(
    'TRAVELPLANNER_COMPARE_SWARM_MODE',
    os.environ.get('TRAVELPLANNER_COMPARE_MODE', 'full'),
).strip().lower()
if SWARM_BENCHMARK_MODE not in {'preflight', 'pilot', 'full'}:
    raise ValueError(f'Unsupported Swarm benchmark mode: {SWARM_BENCHMARK_MODE}')

SWARM_MAX_ITERATION = int(os.environ.get('TRAVELPLANNER_COMPARE_SWARM_MAX_ITERATION', '10'))
SWARM_PREFLIGHT_ITERATION = int(os.environ.get('TRAVELPLANNER_COMPARE_SWARM_PREFLIGHT_ITERATION', '1'))
SWARM_PILOT_ITERATION = int(os.environ.get('TRAVELPLANNER_COMPARE_SWARM_PILOT_ITERATION', '2'))
SWARM_PILOT_QUERIES = int(os.environ.get('TRAVELPLANNER_COMPARE_SWARM_PILOT_QUERIES', '20'))
SWARM_SAMPLE_STEP = int(os.environ.get('TRAVELPLANNER_COMPARE_SWARM_SAMPLE_STEP', '5'))
SWARM_EVAL_SHARD_SIZE = int(os.environ.get('TRAVELPLANNER_COMPARE_SWARM_EVAL_SHARD_SIZE', '20'))
SWARM_MAX_WORKERS = int(os.environ.get('TRAVELPLANNER_COMPARE_SWARM_MAX_WORKERS', '1'))
SWARM_EXTRACT_MODEL = os.environ.get('TRAVELPLANNER_COMPARE_SWARM_EXTRACT_MODEL', MODEL_NAME)
SWARM_RESUME = os.environ.get('TRAVELPLANNER_COMPARE_SWARM_RESUME', '1') == '1'

RUN_SOLO = os.environ.get(
    'TRAVELPLANNER_COMPARE_RUN_SOLO',
    '1' if SWARM_BENCHMARK_MODE == 'full' else '0',
) == '1'
RUN_OUR = os.environ.get(
    'TRAVELPLANNER_COMPARE_RUN_OUR',
    '1' if SWARM_BENCHMARK_MODE == 'full' else '0',
) == '1'
RUN_SWARM = os.environ.get('TRAVELPLANNER_COMPARE_RUN_SWARM', '1') == '1'
TRAIN_SWARM = os.environ.get('TRAVELPLANNER_COMPARE_TRAIN_SWARM', '1') == '1'
INSTALL_SWARM_DEPS = os.environ.get('TRAVELPLANNER_COMPARE_INSTALL_SWARM_DEPS', '0') == '1'
CLONE_SWARM = os.environ.get('TRAVELPLANNER_COMPARE_CLONE_SWARM', '0') == '1'

COMPARE_ROOT = REPO_ROOT / 'output' / 'travelplanner_framework_compare' / RUN_TAG
SOLO_ROOT = COMPARE_ROOT / 'solo'
OUR_ROOT = COMPARE_ROOT / 'stigmergiagentic'
SWARM_ROOT = COMPARE_ROOT / 'swarmagentic'
SWARM_MODE_ROOT = SWARM_ROOT / 'benchmark' / SWARM_BENCHMARK_MODE
SWARM_CLONE = SWARM_ROOT / 'repo'
TABLE_ROOT = COMPARE_ROOT / 'comparison'

SOLO_RUNS_JSON = SOLO_ROOT / 'runs.json'
SOLO_OFFICIAL_JSON = SOLO_ROOT / 'official_eval.json'
SOLO_CONFIG_PATH = SOLO_ROOT / 'config_qwen35_9b_openrouter.yaml'
OUR_RUNS_JSON = OUR_ROOT / 'runs.json'
OUR_OFFICIAL_JSON = OUR_ROOT / 'official_eval.json'
OUR_CONFIG_PATH = OUR_ROOT / 'config_qwen35_9b_openrouter.yaml'
SWARM_RESULTS_JSONL = SWARM_MODE_ROOT / 'evaluation' / 'aggregate' / 'results.jsonl'
SWARM_RUNS_JSON = SWARM_MODE_ROOT / 'runs.json'
SWARM_OFFICIAL_JSON = SWARM_MODE_ROOT / 'official_eval.json'
SWARM_STATUS_JSON = SWARM_MODE_ROOT / 'benchmark_status.json'
SWARM_REPRO_MD = SWARM_MODE_ROOT / 'reproducibility.md'
SWARM_CONTEXT_MD = SWARM_MODE_ROOT / 'context.md'
SWARM_CONTEXT_JSON = SWARM_MODE_ROOT / 'context.json'
TABLE_MD = TABLE_ROOT / 'comparison_table.md'
TABLE_CSV = TABLE_ROOT / 'comparison_table.csv'
TABLE_JSON = TABLE_ROOT / 'comparison_table.json'
NOTEBOOK_SUMMARY = COMPARE_ROOT / 'notebook_summary.json'

for directory in [COMPARE_ROOT, SOLO_ROOT, OUR_ROOT, SWARM_ROOT, SWARM_MODE_ROOT, TABLE_ROOT]:
    directory.mkdir(parents=True, exist_ok=True)

summary = {
    'run_tag': RUN_TAG,
    'model_name': MODEL_NAME,
    'split': SPLIT,
    'max_queries': MAX_QUERIES,
    'our_max_ticks': OUR_MAX_TICKS,
    'our_agents': OUR_AGENT_COUNT,
    'swarm_benchmark_mode': SWARM_BENCHMARK_MODE,
    'swarm_max_iteration': SWARM_MAX_ITERATION,
    'swarm_preflight_iteration': SWARM_PREFLIGHT_ITERATION,
    'swarm_pilot_iteration': SWARM_PILOT_ITERATION,
    'swarm_pilot_queries': SWARM_PILOT_QUERIES,
    'swarm_sample_step': SWARM_SAMPLE_STEP,
    'swarm_eval_shard_size': SWARM_EVAL_SHARD_SIZE,
    'swarm_max_workers': SWARM_MAX_WORKERS,
    'paths': {
        'compare_root': str(COMPARE_ROOT),
        'solo_official_json': str(SOLO_OFFICIAL_JSON),
        'our_official_json': str(OUR_OFFICIAL_JSON),
        'swarm_status_json': str(SWARM_STATUS_JSON),
        'swarm_official_json': str(SWARM_OFFICIAL_JSON),
        'swarm_repro_md': str(SWARM_REPRO_MD),
        'swarm_context_md': str(SWARM_CONTEXT_MD),
        'table_md': str(TABLE_MD),
    },
}
summary
"""


CELL_11 = """def run_stigmergiagentic_validation() -> dict[str, Any]:
    runs: list[dict[str, Any]] = []
    query_dir = OUR_ROOT / 'queries'
    query_dir.mkdir(parents=True, exist_ok=True)

    for query_idx in range(MAX_QUERIES):
        result_path = query_dir / f'query_{query_idx:03d}.json'
        if result_path.exists():
            print(f'\\n=== StigmergiAgentic Query {query_idx + 1}/{MAX_QUERIES} === SKIP (already done)')
            runs.append(json.loads(result_path.read_text(encoding='utf-8')))
            continue

        print(f'\\n=== StigmergiAgentic Query {query_idx + 1}/{MAX_QUERIES} ===')
        cmd = [
            'python', 'scripts/run_travelplanner_query_export.py',
            '--objective', f'Query {query_idx}',
            '--query-idx', str(query_idx),
            '--config', str(OUR_CONFIG_PATH),
            '--max-ticks', str(OUR_MAX_TICKS),
            '--agents', str(OUR_AGENT_COUNT),
            '--seed', '42',
        ]
        proc = run_command(
            cmd,
            cwd=REPO_ROOT,
            check=True,
            log_path=query_dir / f'query_{query_idx:03d}.log',
        )
        payload = extract_last_json(proc.stdout)
        passed = bool(payload.get('final_pass', False))
        print(f'  -> {"PASS" if passed else "FAIL"}')
        result_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + '\\n',
            encoding='utf-8',
        )
        runs.append(payload)

    write_json(OUR_RUNS_JSON, {'runs': runs})
    run_command(
        [
            'python', 'scripts/eval_travelplanner_official.py',
            '--runs-json', str(OUR_RUNS_JSON),
            '--database-root', 'data/travelplanner/database',
            '--split', SPLIT,
            '--out', str(OUR_OFFICIAL_JSON),
        ],
        cwd=REPO_ROOT,
        check=True,
        log_path=OUR_ROOT / 'official_eval.log',
    )
    official_payload = load_json(OUR_OFFICIAL_JSON, {})
    return official_payload.get('scores', {}) if isinstance(official_payload, dict) else {}


our_scores = None
if RUN_OUR:
    our_scores = run_stigmergiagentic_validation()
our_scores
"""


CELL_12 = """## Arm 3: SwarmAgentic

This arm now delegates orchestration to [run_swarmagentic_benchmark.py](/Users/lotfi/Documents/EMLV/Memoire/StigmergiAgentic/scripts/run_swarmagentic_benchmark.py).

It supports three modes:
1. **Preflight**: verify `team.init()` and a 1-iteration PSO smoke test
2. **Pilot**: reduced PSO + a 20-query validation shard
3. **Full**: `5` particles, `10` iterations, `180` validation queries

Artifacts written per mode:
- `benchmark_status.json`
- `reproducibility.md`
- `context.md`
- `runs.json`
- `official_eval.json` when evaluation succeeds
"""


CELL_13 = """from __future__ import annotations

import json
import os
import re as _re
import shlex
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _find_repo_root() -> Path:
    candidate = Path.cwd().resolve()
    for _ in range(6):
        if (candidate / 'main.py').exists():
            return candidate
        candidate = candidate.parent
    raise RuntimeError(f'Cannot find repository root (main.py) from {Path.cwd()}')


REPO_ROOT = globals().get('REPO_ROOT') or _find_repo_root()
os.chdir(REPO_ROOT)


def _merge_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(os.environ)
    if extra:
        env.update({key: str(value) for key, value in extra.items()})
    return env


def run_command(
    cmd: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    check: bool = True,
    log_path: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    merged_env = _merge_env(env)
    print('$', shlex.join(cmd))
    proc = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd is not None else None,
        env=merged_env,
        text=True,
        capture_output=True,
        check=False,
    )
    combined = proc.stdout
    if proc.stderr:
        combined += ('\\n' if combined else '') + proc.stderr
    if log_path is not None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(combined, encoding='utf-8')
    if combined.strip():
        print(combined.strip()[:8000])
    if check and proc.returncode != 0:
        raise RuntimeError(f'Command failed with exit={proc.returncode}: {shlex.join(cmd)}')
    return proc


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding='utf-8'))


_existing_runs_root = REPO_ROOT / 'output' / 'travelplanner_framework_compare'
_existing_runs = sorted((p.name for p in _existing_runs_root.iterdir() if p.is_dir()), reverse=True) if _existing_runs_root.exists() else []
RUN_TAG = globals().get('RUN_TAG') or os.environ.get('TRAVELPLANNER_COMPARE_RUN_TAG') or (_existing_runs[0] if _existing_runs else datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S'))
if 'RUN_TAG' not in globals() and 'TRAVELPLANNER_COMPARE_RUN_TAG' not in os.environ and _existing_runs:
    print(f'RUN_TAG not initialized; using latest existing run tag: {RUN_TAG}')

MODEL_NAME = globals().get('MODEL_NAME', os.environ.get('TRAVELPLANNER_COMPARE_MODEL', 'qwen/qwen3.5-9b'))
OPENROUTER_BASE_URL = globals().get('OPENROUTER_BASE_URL', os.environ.get('TRAVELPLANNER_COMPARE_BASE_URL', 'https://openrouter.ai/api/v1'))
SPLIT = globals().get('SPLIT', os.environ.get('TRAVELPLANNER_COMPARE_SPLIT', 'validation'))
MAX_QUERIES = globals().get('MAX_QUERIES', int(os.environ.get('TRAVELPLANNER_COMPARE_MAX_QUERIES', '180')))
SWARM_BENCHMARK_MODE = globals().get(
    'SWARM_BENCHMARK_MODE',
    os.environ.get('TRAVELPLANNER_COMPARE_SWARM_MODE', os.environ.get('TRAVELPLANNER_COMPARE_MODE', 'full')),
).strip().lower()
if SWARM_BENCHMARK_MODE not in {'preflight', 'pilot', 'full'}:
    raise ValueError(f'Unsupported Swarm benchmark mode: {SWARM_BENCHMARK_MODE}')

SWARM_MAX_ITERATION = globals().get('SWARM_MAX_ITERATION', int(os.environ.get('TRAVELPLANNER_COMPARE_SWARM_MAX_ITERATION', '10')))
SWARM_PREFLIGHT_ITERATION = globals().get('SWARM_PREFLIGHT_ITERATION', int(os.environ.get('TRAVELPLANNER_COMPARE_SWARM_PREFLIGHT_ITERATION', '1')))
SWARM_PILOT_ITERATION = globals().get('SWARM_PILOT_ITERATION', int(os.environ.get('TRAVELPLANNER_COMPARE_SWARM_PILOT_ITERATION', '2')))
SWARM_PILOT_QUERIES = globals().get('SWARM_PILOT_QUERIES', int(os.environ.get('TRAVELPLANNER_COMPARE_SWARM_PILOT_QUERIES', '20')))
SWARM_SAMPLE_STEP = globals().get('SWARM_SAMPLE_STEP', int(os.environ.get('TRAVELPLANNER_COMPARE_SWARM_SAMPLE_STEP', '5')))
SWARM_EVAL_SHARD_SIZE = globals().get('SWARM_EVAL_SHARD_SIZE', int(os.environ.get('TRAVELPLANNER_COMPARE_SWARM_EVAL_SHARD_SIZE', '20')))
SWARM_MAX_WORKERS = globals().get('SWARM_MAX_WORKERS', int(os.environ.get('TRAVELPLANNER_COMPARE_SWARM_MAX_WORKERS', '1')))
SWARM_EXTRACT_MODEL = globals().get('SWARM_EXTRACT_MODEL', os.environ.get('TRAVELPLANNER_COMPARE_SWARM_EXTRACT_MODEL', MODEL_NAME))
SWARM_RESUME = globals().get('SWARM_RESUME', os.environ.get('TRAVELPLANNER_COMPARE_SWARM_RESUME', '1') == '1')
RUN_SWARM = globals().get('RUN_SWARM', os.environ.get('TRAVELPLANNER_COMPARE_RUN_SWARM', '1') == '1')
TRAIN_SWARM = globals().get('TRAIN_SWARM', os.environ.get('TRAVELPLANNER_COMPARE_TRAIN_SWARM', '1') == '1')
INSTALL_SWARM_DEPS = globals().get('INSTALL_SWARM_DEPS', os.environ.get('TRAVELPLANNER_COMPARE_INSTALL_SWARM_DEPS', '0') == '1')
CLONE_SWARM = globals().get('CLONE_SWARM', os.environ.get('TRAVELPLANNER_COMPARE_CLONE_SWARM', '0') == '1')

COMPARE_ROOT = globals().get('COMPARE_ROOT', REPO_ROOT / 'output' / 'travelplanner_framework_compare' / RUN_TAG)
SWARM_ROOT = globals().get('SWARM_ROOT', COMPARE_ROOT / 'swarmagentic')
SWARM_MODE_ROOT = globals().get('SWARM_MODE_ROOT', SWARM_ROOT / 'benchmark' / SWARM_BENCHMARK_MODE)
SWARM_CLONE = globals().get('SWARM_CLONE', SWARM_ROOT / 'repo')
SWARM_RESULTS_JSONL = globals().get('SWARM_RESULTS_JSONL', SWARM_MODE_ROOT / 'evaluation' / 'aggregate' / 'results.jsonl')
SWARM_RUNS_JSON = globals().get('SWARM_RUNS_JSON', SWARM_MODE_ROOT / 'runs.json')
SWARM_OFFICIAL_JSON = globals().get('SWARM_OFFICIAL_JSON', SWARM_MODE_ROOT / 'official_eval.json')
SWARM_STATUS_JSON = globals().get('SWARM_STATUS_JSON', SWARM_MODE_ROOT / 'benchmark_status.json')
SWARM_REPRO_MD = globals().get('SWARM_REPRO_MD', SWARM_MODE_ROOT / 'reproducibility.md')
SWARM_CONTEXT_MD = globals().get('SWARM_CONTEXT_MD', SWARM_MODE_ROOT / 'context.md')
SWARM_CONTEXT_JSON = globals().get('SWARM_CONTEXT_JSON', SWARM_MODE_ROOT / 'context.json')

for directory in [COMPARE_ROOT, SWARM_ROOT, SWARM_MODE_ROOT]:
    directory.mkdir(parents=True, exist_ok=True)

if not os.environ.get('OPENROUTER_API_KEY'):
    raise EnvironmentError('OPENROUTER_API_KEY is missing in the notebook environment.')


def run_command_live(
    cmd: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    check: bool = True,
    log_path: Path | None = None,
    tag: str = '',
) -> subprocess.CompletedProcess[str]:
    merged_env = _merge_env(env)
    print('$', shlex.join(cmd))
    proc = subprocess.Popen(
        cmd,
        cwd=str(cwd) if cwd is not None else None,
        env=merged_env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    lines: list[str] = []
    prefix = f'[{tag}] ' if tag else ''
    progress = _re.compile(
        r'(\\[INFO\\]|\\[WARN\\]|Mode:|Evaluating shard|Iteration|Particles Evaluate|Update Velocity|'
        r'Update Position|Loaded \\d|scores|status=|Optimization completed|Error|Traceback|'
        r'Provider-like|\\d+%\\|█)',
    )
    assert proc.stdout is not None
    for raw in proc.stdout:
        lines.append(raw)
        stripped = raw.rstrip('\\n\\r')
        if progress.search(stripped):
            print(f'{prefix}{stripped}', flush=True)
    proc.wait()
    combined = ''.join(lines)
    if log_path is not None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(combined, encoding='utf-8')
    if check and proc.returncode != 0:
        tail = combined.strip().split('\\n')[-20:]
        print('\\n'.join(tail))
        raise RuntimeError(f'Command failed (exit={proc.returncode}): {shlex.join(cmd)}')
    return subprocess.CompletedProcess(cmd, proc.returncode, stdout=combined, stderr='')


def run_swarmagentic_validation() -> dict[str, Any]:
    cmd = [
        'python', 'scripts/run_swarmagentic_benchmark.py',
        '--swarm-root', str(SWARM_ROOT),
        '--mode', SWARM_BENCHMARK_MODE,
        '--model', MODEL_NAME,
        '--base-url', OPENROUTER_BASE_URL,
        '--split', SPLIT,
        '--database-root', 'data/travelplanner/database',
        '--sample-step', str(SWARM_SAMPLE_STEP),
        '--max-queries', str(MAX_QUERIES),
        '--max-iteration', str(SWARM_MAX_ITERATION),
        '--preflight-iteration', str(SWARM_PREFLIGHT_ITERATION),
        '--pilot-iteration', str(SWARM_PILOT_ITERATION),
        '--pilot-queries', str(SWARM_PILOT_QUERIES),
        '--eval-shard-size', str(SWARM_EVAL_SHARD_SIZE),
        '--max-workers', str(SWARM_MAX_WORKERS),
        '--extract-model', SWARM_EXTRACT_MODEL,
    ]
    if SWARM_RESUME:
        cmd.append('--resume')
    if not TRAIN_SWARM:
        cmd.append('--skip-train')
    if CLONE_SWARM:
        cmd.append('--clone-swarm')
    if INSTALL_SWARM_DEPS:
        cmd.append('--install-swarm-deps')

    run_command_live(
        cmd,
        cwd=REPO_ROOT,
        env={'OPENROUTER_API_KEY': os.environ['OPENROUTER_API_KEY']},
        check=True,
        log_path=SWARM_MODE_ROOT / 'orchestrate.log',
        tag='SWARM',
    )

    status_payload = load_json(SWARM_STATUS_JSON, {})
    official_payload = load_json(SWARM_OFFICIAL_JSON, {}) if SWARM_OFFICIAL_JSON.exists() else {}
    return {
        'mode': SWARM_BENCHMARK_MODE,
        'status': status_payload.get('status', 'missing'),
        'failed_phase': status_payload.get('failed_phase'),
        'scores': official_payload.get('scores', {}) if isinstance(official_payload, dict) else {},
        'status_json': str(SWARM_STATUS_JSON),
        'official_json': str(SWARM_OFFICIAL_JSON) if SWARM_OFFICIAL_JSON.exists() else None,
        'repro_md': str(SWARM_REPRO_MD) if SWARM_REPRO_MD.exists() else None,
        'context_md': str(SWARM_CONTEXT_MD) if SWARM_CONTEXT_MD.exists() else None,
    }


swarm_result = None
swarm_scores = None
if RUN_SWARM:
    swarm_result = run_swarmagentic_validation()
    swarm_scores = swarm_result.get('scores', {})
swarm_result if swarm_result is not None else swarm_scores
"""


CELL_14 = """## Final report

The next cell renders:
1. the main comparison table from whichever official scorer outputs are available
2. the SwarmAgentic paper-context note (non-comparable reference scores)
3. the Swarm reproducibility log for the selected mode
"""


CELL_15 = """comparison_rows = []
if SOLO_OFFICIAL_JSON.exists():
    comparison_rows.append(f'Solo={SOLO_OFFICIAL_JSON}')
if OUR_OFFICIAL_JSON.exists():
    comparison_rows.append(f'StigmergiAgentic={OUR_OFFICIAL_JSON}')
if SWARM_OFFICIAL_JSON.exists():
    comparison_rows.append(f'SwarmAgentic={SWARM_OFFICIAL_JSON}')

if comparison_rows:
    cmd = ['python', 'scripts/render_travelplanner_comparison_table.py']
    for item in comparison_rows:
        cmd.extend(['--run', item])
    cmd.extend([
        '--out-md', str(TABLE_MD),
        '--out-csv', str(TABLE_CSV),
        '--out-json', str(TABLE_JSON),
    ])
    run_command(cmd, cwd=REPO_ROOT, check=True, log_path=TABLE_ROOT / 'render_table.log')
    table_md = TABLE_MD.read_text(encoding='utf-8')
    display(Markdown(table_md))
else:
    print('No official eval JSON files available yet; skipping comparison table rendering.')

if SWARM_CONTEXT_MD.exists():
    display(Markdown(SWARM_CONTEXT_MD.read_text(encoding='utf-8')))

if SWARM_REPRO_MD.exists():
    display(Markdown(SWARM_REPRO_MD.read_text(encoding='utf-8')))

notebook_summary = {
    **summary,
    'comparison_rows_rendered': len(comparison_rows),
    'solo_official_scores': load_json(SOLO_OFFICIAL_JSON, {}).get('scores', {}),
    'our_official_scores': load_json(OUR_OFFICIAL_JSON, {}).get('scores', {}),
    'swarm_official_scores': load_json(SWARM_OFFICIAL_JSON, {}).get('scores', {}),
    'swarm_status': load_json(SWARM_STATUS_JSON, {}),
    'table_md': str(TABLE_MD) if TABLE_MD.exists() else None,
    'table_csv': str(TABLE_CSV) if TABLE_CSV.exists() else None,
    'table_json': str(TABLE_JSON) if TABLE_JSON.exists() else None,
    'swarm_reproducibility_md': str(SWARM_REPRO_MD) if SWARM_REPRO_MD.exists() else None,
    'swarm_context_md': str(SWARM_CONTEXT_MD) if SWARM_CONTEXT_MD.exists() else None,
}
write_json(NOTEBOOK_SUMMARY, notebook_summary)
NOTEBOOK_SUMMARY
"""


CELL_9 = """def run_solo_validation() -> dict[str, Any]:
    runs: list[dict[str, Any]] = []
    query_dir = SOLO_ROOT / 'queries'
    query_dir.mkdir(parents=True, exist_ok=True)

    for query_idx in range(MAX_QUERIES):
        result_path = query_dir / f'query_{query_idx:03d}.json'
        if result_path.exists():
            print(f'\\n=== Solo Query {query_idx + 1}/{MAX_QUERIES} === SKIP (already done)')
            runs.append(json.loads(result_path.read_text(encoding='utf-8')))
            continue

        print(f'\\n=== Solo Query {query_idx + 1}/{MAX_QUERIES} ===')
        cmd = [
            'python', 'scripts/run_travelplanner_solo_query_export.py',
            '--objective', f'Query {query_idx}',
            '--query-idx', str(query_idx),
            '--config', str(SOLO_CONFIG_PATH),
        ]
        proc = run_command(
            cmd,
            cwd=REPO_ROOT,
            check=True,
            log_path=query_dir / f'query_{query_idx:03d}.log',
        )
        payload = extract_last_json(proc.stdout)
        passed = bool(payload.get('final_pass', False))
        print(f'  -> {"PASS" if passed else "FAIL"}')
        result_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + '\\n',
            encoding='utf-8',
        )
        runs.append(payload)

    write_json(SOLO_RUNS_JSON, {'runs': runs})
    run_command(
        [
            'python', 'scripts/eval_travelplanner_official.py',
            '--runs-json', str(SOLO_RUNS_JSON),
            '--database-root', 'data/travelplanner/database',
            '--split', SPLIT,
            '--out', str(SOLO_OFFICIAL_JSON),
        ],
        cwd=REPO_ROOT,
        check=True,
        log_path=SOLO_ROOT / 'official_eval.log',
    )
    official_payload = load_json(SOLO_OFFICIAL_JSON, {})
    return official_payload.get('scores', {}) if isinstance(official_payload, dict) else {}


solo_scores = None
if RUN_SOLO:
    solo_scores = run_solo_validation()
solo_scores
"""


def as_source(text: str) -> list[str]:
    return [line + "\n" for line in text.rstrip("\n").split("\n")]


def main() -> int:
    notebook = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))
    updates = {
        0: CELL_0,
        3: CELL_3,
        5: CELL_5,
        9: CELL_9,
        11: CELL_11,
        12: CELL_12,
        13: CELL_13,
        14: CELL_14,
        15: CELL_15,
    }
    for index, text in updates.items():
        notebook["cells"][index]["source"] = as_source(text)
    NOTEBOOK_PATH.write_text(json.dumps(notebook, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"updated {NOTEBOOK_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
