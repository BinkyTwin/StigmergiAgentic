"""Create a dedicated notebook for strict full SwarmAgentic scientific comparison."""

from __future__ import annotations

import json
from pathlib import Path


NOTEBOOK_PATH = (
    Path(__file__).resolve().parents[1]
    / "output"
    / "jupyter-notebook"
    / "travelplanner-swarmagentic-full-scientific-comparison-openrouter-qwen35-9b.ipynb"
)


def markdown_cell(text: str) -> dict:
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": [line + "\n" for line in text.rstrip("\n").split("\n")],
    }


def code_cell(text: str) -> dict:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [line + "\n" for line in text.rstrip("\n").split("\n")],
    }


CELL_0 = """# Experiment: SwarmAgentic Full Scientific Comparison on OpenRouter Qwen3.5-9B

This notebook is a **strict full-evaluation notebook** dedicated to SwarmAgentic only.

It is designed to compare one new **SwarmAgentic full run** against two already-produced reference evaluations:
- **Solo**
- **StigmergiAgentic**

The comparison is scientifically strict in the following sense:
- same provider: **OpenRouter**
- same backbone: **`qwen/qwen3.5-9b`**
- same split: **`validation`**
- same official scorer: the local TravelPlanner official evaluator
- same query count for the final table: **180**

This notebook does **not** treat provider `504` outages as model score `0`. If SwarmAgentic fails because of provider/infrastructure instability, the notebook surfaces that as a reproducibility failure and blocks the final scientific comparison table.
"""


CELL_1 = """## Protocol

The SwarmAgentic run launched here is fixed to the full protocol:
- training file: `train_45.jsonl`
- effective train subset: `sample_step=5` -> 9 examples
- PSO iterations: `10`
- validation queries: `180`
- evaluation mode: full split
- worker count: `1` by default to reduce provider pressure on Qwen/OpenRouter

Reference runs are loaded from a previous completed comparison run by default:
- `output/travelplanner_framework_compare/20260326_132646/solo`
- `output/travelplanner_framework_compare/20260326_132646/stigmergiagentic`

You can override those paths through environment variables if needed.
"""


CELL_2 = """from __future__ import annotations

import json
import math
import os
import re
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from IPython.display import Markdown, display


def find_repo_root() -> Path:
    candidate = Path.cwd().resolve()
    for _ in range(6):
        if (candidate / 'main.py').exists():
            return candidate
        candidate = candidate.parent
    raise RuntimeError(f'Cannot find repository root from {Path.cwd()}')


REPO_ROOT = find_repo_root()
os.chdir(REPO_ROOT)


def merge_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(os.environ)
    if extra:
        env.update({key: str(value) for key, value in extra.items()})
    return env


def command_output(
    cmd: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> tuple[int, str]:
    proc = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd is not None else None,
        env=merge_env(env),
        text=True,
        capture_output=True,
        check=False,
    )
    combined = proc.stdout
    if proc.stderr:
        combined += ('\\n' if combined else '') + proc.stderr
    return proc.returncode, combined


def resolve_repo_python(required_modules: list[str]) -> Path:
    candidates: list[Path] = []
    seen: set[str] = set()
    raw_candidates = [
        Path(sys.executable).resolve(),
        REPO_ROOT / '.venv' / 'bin' / 'python',
        Path('/opt/miniconda3/bin/python'),
        Path('/usr/bin/python3'),
    ]
    for candidate in raw_candidates:
        text = str(candidate)
        if text in seen:
            continue
        seen.add(text)
        if candidate.exists():
            code = 'import ' + ', '.join(required_modules) + '; print("OK")'
            returncode, output = command_output([text, '-c', code], cwd=REPO_ROOT)
            if returncode == 0 and 'OK' in output:
                return candidate
    raise RuntimeError(
        'Could not find a Python interpreter with required modules: '
        + ', '.join(required_modules)
    )


REPO_PYTHON = resolve_repo_python(['datasets', 'yaml', 'pydantic'])
print('REPO_PYTHON:', REPO_PYTHON)


def run_command(
    cmd: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    check: bool = True,
    log_path: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    merged_env = merge_env(env)
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
        print(combined.strip()[:12000])
    if check and proc.returncode != 0:
        raise RuntimeError(f'Command failed with exit={proc.returncode}: {shlex.join(cmd)}')
    return proc


def run_command_live(
    cmd: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    check: bool = True,
    log_path: Path | None = None,
    tag: str = '',
) -> subprocess.CompletedProcess[str]:
    merged_env = merge_env(env)
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
    progress = re.compile(
        r'(\\[INFO\\]|\\[WARN\\]|\\[HEARTBEAT\\]|\\[WATCHDOG\\]|\\[WATCH\\]|\\[PSO\\]|\\[SWARM-TEST\\]|Mode:|Evaluating shard|Iteration|Particles Evaluate|'
        r'Update Velocity|Update Position|Loaded \\d|status=|Optimization completed|'
        r'Error|Traceback|Provider-like|\\d+%\\|█)',
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
        raise RuntimeError(f'Command failed with exit={proc.returncode}: {shlex.join(cmd)}')
    return subprocess.CompletedProcess(cmd, proc.returncode, stdout=combined, stderr='')


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding='utf-8'))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\\n', encoding='utf-8')


def tail_text_file(path: Path, lines: int = 40) -> str:
    if not path.exists():
        return f'{path} does not exist.'
    content = path.read_text(encoding='utf-8', errors='replace').splitlines()
    return '\\n'.join(content[-lines:])


def render_markdown_table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = [
        '| ' + ' | '.join(headers) + ' |',
        '| ' + ' | '.join(['---'] * len(headers)) + ' |',
    ]
    for row in rows:
        lines.append('| ' + ' | '.join(str(item) for item in row) + ' |')
    return '\\n'.join(lines) + '\\n'


def pct(value: Any) -> str:
    try:
        return f'{float(value) * 100:.1f}'
    except Exception:
        return '0.0'


def load_runs_by_query(path: Path) -> dict[int, dict[str, Any]]:
    payload = load_json(path, {})
    runs = payload.get('runs', []) if isinstance(payload, dict) else []
    result: dict[int, dict[str, Any]] = {}
    if not isinstance(runs, list):
        return result
    for item in runs:
        if not isinstance(item, dict):
            continue
        try:
            query_idx = int(item.get('query_idx', -1))
        except Exception:
            continue
        if query_idx >= 0:
            result[query_idx] = item
    return result


def exact_mcnemar_pvalue(wins: int, losses: int) -> float:
    discordant = wins + losses
    if discordant == 0:
        return 1.0
    tail = sum(math.comb(discordant, k) for k in range(0, min(wins, losses) + 1)) / (2 ** discordant)
    return min(1.0, 2.0 * tail)


def pairwise_final_pass_summary(
    left_name: str,
    left_runs_path: Path,
    right_name: str,
    right_runs_path: Path,
) -> dict[str, Any]:
    left = load_runs_by_query(left_runs_path)
    right = load_runs_by_query(right_runs_path)
    common = sorted(set(left) & set(right))
    wins = 0
    losses = 0
    both_pass = 0
    both_fail = 0
    for query_idx in common:
        left_pass = bool(left[query_idx].get('final_pass', False))
        right_pass = bool(right[query_idx].get('final_pass', False))
        if left_pass and not right_pass:
            wins += 1
        elif not left_pass and right_pass:
            losses += 1
        elif left_pass and right_pass:
            both_pass += 1
        else:
            both_fail += 1
    return {
        'left': left_name,
        'right': right_name,
        'paired_queries': len(common),
        'left_only_successes': wins,
        'right_only_successes': losses,
        'both_pass': both_pass,
        'both_fail': both_fail,
        'exact_mcnemar_pvalue': exact_mcnemar_pvalue(wins, losses),
    }


print('REPO_ROOT:', REPO_ROOT)
"""


CELL_3 = """RUN_TAG = os.environ.get('TRAVELPLANNER_SWARM_STRICT_RUN_TAG') or datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
MODEL_NAME = os.environ.get('TRAVELPLANNER_COMPARE_MODEL', 'qwen/qwen3.5-9b')
OPENROUTER_BASE_URL = os.environ.get('TRAVELPLANNER_COMPARE_BASE_URL', 'https://openrouter.ai/api/v1')
SPLIT = 'validation'
MAX_QUERIES = 180

SWARM_MAX_ITERATION = int(os.environ.get('TRAVELPLANNER_COMPARE_SWARM_MAX_ITERATION', '10'))
SWARM_SAMPLE_STEP = int(os.environ.get('TRAVELPLANNER_COMPARE_SWARM_SAMPLE_STEP', '5'))
SWARM_MAX_WORKERS = int(os.environ.get('TRAVELPLANNER_COMPARE_SWARM_MAX_WORKERS', '1'))
SWARM_EVAL_SHARD_SIZE = int(os.environ.get('TRAVELPLANNER_COMPARE_SWARM_EVAL_SHARD_SIZE', '20'))
SWARM_EXTRACT_MODEL = os.environ.get('TRAVELPLANNER_COMPARE_SWARM_EXTRACT_MODEL', MODEL_NAME)
SWARM_HEARTBEAT_INTERVAL_SECONDS = int(os.environ.get('TRAVELPLANNER_COMPARE_SWARM_HEARTBEAT_INTERVAL_SECONDS', '30'))
SWARM_IDLE_TIMEOUT_SECONDS = int(os.environ.get('TRAVELPLANNER_COMPARE_SWARM_IDLE_TIMEOUT_SECONDS', '600'))
SWARM_RESUME = os.environ.get('TRAVELPLANNER_COMPARE_SWARM_RESUME', '1') == '1'
CLONE_SWARM = os.environ.get('TRAVELPLANNER_COMPARE_CLONE_SWARM', '0') == '1'
INSTALL_SWARM_DEPS = os.environ.get('TRAVELPLANNER_COMPARE_INSTALL_SWARM_DEPS', '0') == '1'
STRICT_REQUIRE_SUCCESS = os.environ.get('TRAVELPLANNER_SWARM_STRICT_REQUIRE_SUCCESS', '1') == '1'

REFERENCE_RUN_TAG = os.environ.get('TRAVELPLANNER_REFERENCE_RUN_TAG', '20260326_132646')
REFERENCE_ROOT = REPO_ROOT / 'output' / 'travelplanner_framework_compare' / REFERENCE_RUN_TAG

SOLO_REF_OFFICIAL_JSON = Path(
    os.environ.get(
        'TRAVELPLANNER_REFERENCE_SOLO_OFFICIAL_JSON',
        str(REFERENCE_ROOT / 'solo' / 'official_eval.json'),
    )
)
OUR_REF_OFFICIAL_JSON = Path(
    os.environ.get(
        'TRAVELPLANNER_REFERENCE_OUR_OFFICIAL_JSON',
        str(REFERENCE_ROOT / 'stigmergiagentic' / 'official_eval.json'),
    )
)
SOLO_REF_RUNS_JSON = Path(
    os.environ.get(
        'TRAVELPLANNER_REFERENCE_SOLO_RUNS_JSON',
        str(REFERENCE_ROOT / 'solo' / 'runs.json'),
    )
)
OUR_REF_RUNS_JSON = Path(
    os.environ.get(
        'TRAVELPLANNER_REFERENCE_OUR_RUNS_JSON',
        str(REFERENCE_ROOT / 'stigmergiagentic' / 'runs.json'),
    )
)

COMPARE_ROOT = REPO_ROOT / 'output' / 'travelplanner_framework_compare' / RUN_TAG
SWARM_ROOT = COMPARE_ROOT / 'swarmagentic'
SWARM_MODE_ROOT = SWARM_ROOT / 'benchmark' / 'full'
TABLE_ROOT = COMPARE_ROOT / 'comparison_scientific'

SWARM_STATUS_JSON = SWARM_MODE_ROOT / 'benchmark_status.json'
SWARM_REPRO_MD = SWARM_MODE_ROOT / 'reproducibility.md'
SWARM_CONTEXT_MD = SWARM_MODE_ROOT / 'context.md'
SWARM_RUNS_JSON = SWARM_MODE_ROOT / 'runs.json'
SWARM_OFFICIAL_JSON = SWARM_MODE_ROOT / 'official_eval.json'
SWARM_LIVE_MONITOR_JSON = SWARM_MODE_ROOT / 'live_monitor.json'
SWARM_HEARTBEAT_LOG = SWARM_MODE_ROOT / 'logs' / 'heartbeat.log'
SWARM_TRAIN_LOG = SWARM_MODE_ROOT / 'logs' / 'pso_train.log'
TABLE_MD = TABLE_ROOT / 'scientific_comparison_table.md'
TABLE_CSV = TABLE_ROOT / 'scientific_comparison_table.csv'
TABLE_JSON = TABLE_ROOT / 'scientific_comparison_table.json'
PAIRWISE_JSON = TABLE_ROOT / 'pairwise_final_pass.json'
NOTEBOOK_SUMMARY = COMPARE_ROOT / 'swarmagentic_scientific_full_summary.json'

for directory in [COMPARE_ROOT, SWARM_ROOT, SWARM_MODE_ROOT, TABLE_ROOT]:
    directory.mkdir(parents=True, exist_ok=True)

summary = {
    'run_tag': RUN_TAG,
    'reference_run_tag': REFERENCE_RUN_TAG,
    'model_name': MODEL_NAME,
    'split': SPLIT,
    'max_queries': MAX_QUERIES,
    'swarm_max_iteration': SWARM_MAX_ITERATION,
    'swarm_sample_step': SWARM_SAMPLE_STEP,
    'swarm_max_workers': SWARM_MAX_WORKERS,
    'swarm_eval_shard_size': SWARM_EVAL_SHARD_SIZE,
    'paths': {
        'compare_root': str(COMPARE_ROOT),
        'solo_reference_official_json': str(SOLO_REF_OFFICIAL_JSON),
        'our_reference_official_json': str(OUR_REF_OFFICIAL_JSON),
        'swarm_status_json': str(SWARM_STATUS_JSON),
        'swarm_official_json': str(SWARM_OFFICIAL_JSON),
        'swarm_live_monitor_json': str(SWARM_LIVE_MONITOR_JSON),
        'swarm_heartbeat_log': str(SWARM_HEARTBEAT_LOG),
        'swarm_train_log': str(SWARM_TRAIN_LOG),
        'table_md': str(TABLE_MD),
        'pairwise_json': str(PAIRWISE_JSON),
    },
}
summary
"""


CELL_4 = """if not os.environ.get('OPENROUTER_API_KEY'):
    raise EnvironmentError('OPENROUTER_API_KEY is missing in the notebook environment.')

required_reference_paths = [
    SOLO_REF_OFFICIAL_JSON,
    OUR_REF_OFFICIAL_JSON,
    SOLO_REF_RUNS_JSON,
    OUR_REF_RUNS_JSON,
]
missing_reference_paths = [str(path) for path in required_reference_paths if not path.exists()]
if missing_reference_paths:
    raise FileNotFoundError(
        'Missing reference evaluation artifacts:\\n' + '\\n'.join(missing_reference_paths)
    )

print('OPENROUTER_API_KEY detected')
print(json.dumps(summary, indent=2))
"""


CELL_5 = """reference_rows = []
for method_name, official_path in [
    ('Solo', SOLO_REF_OFFICIAL_JSON),
    ('StigmergiAgentic', OUR_REF_OFFICIAL_JSON),
]:
    payload = load_json(official_path, {})
    scores = payload.get('scores', {}) if isinstance(payload, dict) else {}
    reference_rows.append([
        method_name,
        pct(scores.get('delivery_rate', 0.0)),
        pct(scores.get('commonsense_micro', 0.0)),
        pct(scores.get('commonsense_macro', 0.0)),
        pct(scores.get('hard_constraint_micro', 0.0)),
        pct(scores.get('hard_constraint_macro', 0.0)),
        pct(scores.get('final_pass_rate', 0.0)),
        official_path,
    ])

display(Markdown(render_markdown_table(
    ['Method', 'Delivery', 'Commonsense Micro', 'Commonsense Macro', 'Hard Constraint Micro', 'Hard Constraint Macro', 'Final', 'Official Eval JSON'],
    reference_rows,
)))
"""


CELL_6 = """run_command([str(REPO_PYTHON), 'scripts/setup_travelplanner.py'], cwd=REPO_ROOT, check=True, log_path=COMPARE_ROOT / 'setup_data.log')

count_proc = run_command(
    [str(REPO_PYTHON), '-c', "from datasets import load_dataset; ds = load_dataset('osunlp/TravelPlanner', 'validation'); print(len(ds['validation']))"],
    cwd=REPO_ROOT,
    check=True,
    log_path=COMPARE_ROOT / 'dataset_count.log',
)
print('validation_count=', count_proc.stdout.strip().splitlines()[-1])
"""


CELL_7 = """swarm_cmd = [
    str(REPO_PYTHON), 'scripts/run_swarmagentic_benchmark.py',
    '--swarm-root', str(SWARM_ROOT),
    '--mode', 'full',
    '--model', MODEL_NAME,
    '--base-url', OPENROUTER_BASE_URL,
    '--split', SPLIT,
    '--database-root', 'data/travelplanner/database',
    '--sample-step', str(SWARM_SAMPLE_STEP),
    '--max-queries', str(MAX_QUERIES),
    '--max-iteration', str(SWARM_MAX_ITERATION),
    '--eval-shard-size', str(SWARM_EVAL_SHARD_SIZE),
    '--max-workers', str(SWARM_MAX_WORKERS),
    '--heartbeat-interval-seconds', str(SWARM_HEARTBEAT_INTERVAL_SECONDS),
    '--idle-timeout-seconds', str(SWARM_IDLE_TIMEOUT_SECONDS),
    '--extract-model', SWARM_EXTRACT_MODEL,
]
if SWARM_RESUME:
    swarm_cmd.append('--resume')
if CLONE_SWARM:
    swarm_cmd.append('--clone-swarm')
if INSTALL_SWARM_DEPS:
    swarm_cmd.append('--install-swarm-deps')

run_command_live(
    swarm_cmd,
    cwd=REPO_ROOT,
    env={'OPENROUTER_API_KEY': os.environ['OPENROUTER_API_KEY']},
    check=True,
    log_path=SWARM_MODE_ROOT / 'orchestrate_full.log',
    tag='SWARM-FULL',
)

swarm_status = load_json(SWARM_STATUS_JSON, {})
swarm_scores_payload = load_json(SWARM_OFFICIAL_JSON, {}) if SWARM_OFFICIAL_JSON.exists() else {}

if SWARM_CONTEXT_MD.exists():
    display(Markdown(SWARM_CONTEXT_MD.read_text(encoding='utf-8')))
if SWARM_REPRO_MD.exists():
    display(Markdown(SWARM_REPRO_MD.read_text(encoding='utf-8')))

print(json.dumps(swarm_status, indent=2))

for label, path in [
    ('Live monitor JSON', SWARM_LIVE_MONITOR_JSON),
    ('Heartbeat log', SWARM_HEARTBEAT_LOG),
    ('Training log', SWARM_TRAIN_LOG),
]:
    print(f'{label}: {path} exists={path.exists()}')

if SWARM_LIVE_MONITOR_JSON.exists():
    print(json.dumps(load_json(SWARM_LIVE_MONITOR_JSON, {}), indent=2)[:12000])

for path in [SWARM_HEARTBEAT_LOG, SWARM_TRAIN_LOG]:
    if path.exists():
        print(f'===== tail {path.name} =====')
        print(tail_text_file(path, 40))

if STRICT_REQUIRE_SUCCESS and swarm_status.get('status') != 'success':
    raise RuntimeError(
        f\"SwarmAgentic full benchmark ended with status={swarm_status.get('status')} \"
        f\"phase={swarm_status.get('failed_phase')}. Scientific comparison table is gated.\"
    )

swarm_scores_payload.get('scores', {}) if isinstance(swarm_scores_payload, dict) else {}
"""


CELL_8 = """comparison_rows = [
    f'Solo={SOLO_REF_OFFICIAL_JSON}',
    f'StigmergiAgentic={OUR_REF_OFFICIAL_JSON}',
]
if SWARM_OFFICIAL_JSON.exists():
    comparison_rows.append(f'SwarmAgentic={SWARM_OFFICIAL_JSON}')

cmd = [str(REPO_PYTHON), 'scripts/render_travelplanner_comparison_table.py']
for item in comparison_rows:
    cmd.extend(['--run', item])
cmd.extend([
    '--out-md', str(TABLE_MD),
    '--out-csv', str(TABLE_CSV),
    '--out-json', str(TABLE_JSON),
])
run_command(cmd, cwd=REPO_ROOT, check=True, log_path=TABLE_ROOT / 'render_table.log')

display(Markdown(TABLE_MD.read_text(encoding='utf-8')))
"""


CELL_9 = """pairwise_rows = []
pairwise_payload: dict[str, Any] = {'comparisons': []}

if SWARM_RUNS_JSON.exists():
    comparisons = [
        pairwise_final_pass_summary('SwarmAgentic', SWARM_RUNS_JSON, 'Solo', SOLO_REF_RUNS_JSON),
        pairwise_final_pass_summary('SwarmAgentic', SWARM_RUNS_JSON, 'StigmergiAgentic', OUR_REF_RUNS_JSON),
    ]
    pairwise_payload['comparisons'] = comparisons
    for item in comparisons:
        pairwise_rows.append([
            item['left'],
            item['right'],
            item['paired_queries'],
            item['left_only_successes'],
            item['right_only_successes'],
            item['both_pass'],
            item['both_fail'],
            f\"{item['exact_mcnemar_pvalue']:.6f}\",
        ])

write_json(PAIRWISE_JSON, pairwise_payload)

if pairwise_rows:
    display(Markdown(render_markdown_table(
        ['Left', 'Right', 'Paired Queries', 'Left Only Successes', 'Right Only Successes', 'Both Pass', 'Both Fail', 'Exact McNemar p'],
        pairwise_rows,
    )))
else:
    print('Swarm runs.json is not available, so pairwise final-pass analysis was skipped.')
"""


CELL_10 = """notebook_summary = {
    **summary,
    'solo_reference_scores': load_json(SOLO_REF_OFFICIAL_JSON, {}).get('scores', {}),
    'our_reference_scores': load_json(OUR_REF_OFFICIAL_JSON, {}).get('scores', {}),
    'swarm_status': load_json(SWARM_STATUS_JSON, {}),
    'swarm_scores': load_json(SWARM_OFFICIAL_JSON, {}).get('scores', {}),
    'pairwise_final_pass': load_json(PAIRWISE_JSON, {}),
    'table_md': str(TABLE_MD) if TABLE_MD.exists() else None,
    'table_csv': str(TABLE_CSV) if TABLE_CSV.exists() else None,
    'table_json': str(TABLE_JSON) if TABLE_JSON.exists() else None,
}
write_json(NOTEBOOK_SUMMARY, notebook_summary)
NOTEBOOK_SUMMARY
"""


def main() -> int:
    notebook = {
        "cells": [
            markdown_cell(CELL_0),
            markdown_cell(CELL_1),
            code_cell(CELL_2),
            code_cell(CELL_3),
            code_cell(CELL_4),
            code_cell(CELL_5),
            code_cell(CELL_6),
            code_cell(CELL_7),
            code_cell(CELL_8),
            code_cell(CELL_9),
            code_cell(CELL_10),
        ],
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {
                "name": "python",
                "version": "3.12",
            },
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    NOTEBOOK_PATH.parent.mkdir(parents=True, exist_ok=True)
    NOTEBOOK_PATH.write_text(json.dumps(notebook, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {NOTEBOOK_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
