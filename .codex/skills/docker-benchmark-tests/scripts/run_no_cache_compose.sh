#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Run a Docker Compose service after a mandatory no-cache image build.

Usage:
  run_no_cache_compose.sh [--compose-file FILE] --service SERVICE [--no-run]

Defaults:
  --compose-file docker-compose.yml

Examples:
  .codex/skills/docker-benchmark-tests/scripts/run_no_cache_compose.sh --service test
  .codex/skills/docker-benchmark-tests/scripts/run_no_cache_compose.sh \
    --compose-file docker-compose.campaign.yml \
    --service v11-migrationbench-smoke

Environment:
  Pass non-secret campaign knobs as environment variables before this script.
  Keep secrets in the environment or ignored .env files; do not pass secrets as CLI args.
EOF
}

compose_file="docker-compose.yml"
service=""
no_run=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --compose-file|-f)
      compose_file="${2:-}"
      shift 2
      ;;
    --service|-s)
      service="${2:-}"
      shift 2
      ;;
    --no-run)
      no_run=1
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ -z "${service}" ]]; then
  echo "Missing required --service value." >&2
  usage >&2
  exit 2
fi

if [[ ! -f "${compose_file}" ]]; then
  echo "Compose file not found: ${compose_file}" >&2
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker CLI is required." >&2
  exit 1
fi

docker compose version >/dev/null

echo "Building ${service} from ${compose_file} with no Docker cache..."
docker compose -f "${compose_file}" build --no-cache --pull --progress=plain "${service}"

if [[ "${no_run}" == "1" ]]; then
  echo "No-run requested; build completed."
  exit 0
fi

echo "Running ${service} from ${compose_file}..."
docker compose -f "${compose_file}" run --rm "${service}"
