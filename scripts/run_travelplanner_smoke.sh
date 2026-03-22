#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Run the TravelPlanner smoke workflow through Docker Compose.

Optional environment variables:
  REPO_DIR     Repository root (default: parent of this script)
  QUERY_IDX    TravelPlanner query index (default: 0)
  SEED         Runtime seed (default: 42)
  OBJECTIVE    Objective text (default: Query <QUERY_IDX>)
  OUTPUT_DIR   Output directory (default: <repo>/output/travelplanner_smoke)
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

require_env() {
  local name="$1"
  if [[ -z "${!name:-}" ]]; then
    echo "Missing required environment variable: $name" >&2
    exit 1
  fi
}

load_env_file() {
  local path="$1"
  if [[ ! -f "${path}" ]]; then
    return
  fi
  set -a
  # shellcheck disable=SC1090
  source "${path}"
  set +a
}

extract_summary_json() {
  local log_path="$1"
  local json_path="$2"
  python3 - "$log_path" "$json_path" <<'PY'
import json
import sys
from pathlib import Path

log_path = Path(sys.argv[1])
json_path = Path(sys.argv[2])
lines = log_path.read_text(encoding="utf-8").splitlines()

for index in range(len(lines) - 1, -1, -1):
    if not lines[index].lstrip().startswith("{"):
        continue
    candidate = "\n".join(lines[index:]).strip()
    if not candidate:
        continue
    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError:
        continue
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if payload.get("adapter") != "travelplanner":
        raise SystemExit("Unexpected adapter in summary JSON")
    if payload.get("llm_provider") != "openrouter":
        raise SystemExit("Unexpected llm_provider in summary JSON")
    if payload.get("llm_model") != "qwen/qwen3.5-9b":
        raise SystemExit("Unexpected llm_model in summary JSON")
    evaluation = payload.get("evaluation", {})
    if not isinstance(evaluation, dict) or "final_pass_rate" not in evaluation:
        raise SystemExit("Missing evaluation.final_pass_rate in summary JSON")
    print(
        json.dumps(
            {
                "adapter": payload.get("adapter"),
                "llm_provider": payload.get("llm_provider"),
                "llm_model": payload.get("llm_model"),
                "final_pass_rate": evaluation.get("final_pass_rate"),
                "session_id": payload.get("session_id"),
                "summary_json": str(json_path),
            }
        )
    )
    raise SystemExit(0)

raise SystemExit(1)
PY
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="${REPO_DIR:-$(cd "${SCRIPT_DIR}/.." && pwd)}"
QUERY_IDX="${QUERY_IDX:-0}"
SEED="${SEED:-42}"
OBJECTIVE="${OBJECTIVE:-Query ${QUERY_IDX}}"
OUTPUT_DIR="${OUTPUT_DIR:-${REPO_DIR}/output/travelplanner_smoke}"
RUN_STAMP="$(date +%Y%m%d_%H%M%S)"
PYTEST_LOG="${OUTPUT_DIR}/travelplanner_pytest_${RUN_STAMP}.log"
RUN_LOG="${OUTPUT_DIR}/travelplanner_query${QUERY_IDX}_${RUN_STAMP}.log"
SUMMARY_JSON="${OUTPUT_DIR}/travelplanner_query${QUERY_IDX}_${RUN_STAMP}.json"

if [[ "${TRAVELPLANNER_SMOKE_IN_CONTAINER:-0}" != "1" ]]; then
  if ! command -v docker >/dev/null 2>&1; then
    echo "Docker is required to run the TravelPlanner smoke workflow." >&2
    exit 1
  fi

  cd "${REPO_DIR}"
  exec docker compose run --rm \
    -e TRAVELPLANNER_SMOKE_IN_CONTAINER=1 \
    -e QUERY_IDX="${QUERY_IDX}" \
    -e SEED="${SEED}" \
    -e OBJECTIVE="${OBJECTIVE}" \
    -e OUTPUT_DIR="/app/output/travelplanner_smoke" \
    travelplanner-smoke
fi

PYTEST_BIN="${PYTEST_BIN:-pytest}"
PYTHON_BIN="${PYTHON_BIN:-python}"

load_env_file "${REPO_DIR}/.env"
load_env_file "${REPO_DIR}/.env.local"
require_env OPENROUTER_API_KEY

if [[ ! -d "${REPO_DIR}" ]]; then
  echo "Repository directory not found: ${REPO_DIR}" >&2
  exit 1
fi

cd "${REPO_DIR}"
mkdir -p "${OUTPUT_DIR}"

echo "Running TravelPlanner integration smoke test"
"${PYTEST_BIN}" tests/integration/test_travelplanner.py -q 2>&1 | tee "${PYTEST_LOG}"

echo
echo "Running TravelPlanner objective against OpenRouter"
"${PYTHON_BIN}" main.py \
  --adapter travelplanner \
  --objective "${OBJECTIVE}" \
  --query-idx "${QUERY_IDX}" \
  --seed "${SEED}" 2>&1 | tee "${RUN_LOG}"

if extract_summary_json "${RUN_LOG}" "${SUMMARY_JSON}" >/tmp/travelplanner_smoke_extract.json; then
  echo
  echo "Summary extracted:"
  cat /tmp/travelplanner_smoke_extract.json
else
  echo "Warning: unable to extract the final JSON summary from ${RUN_LOG}" >&2
fi

echo
echo "Artifacts:"
echo "  pytest_log=${PYTEST_LOG}"
echo "  run_log=${RUN_LOG}"
echo "  summary_json=${SUMMARY_JSON}"
