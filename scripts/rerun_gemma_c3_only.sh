#!/bin/bash
# Re-run ONLY the C3 eval phase for Gemma stigmergie, reusing existing skills/protocols DBs.
# Called from inside the gemma-stigmergie Docker container.

set -euo pipefail

SEED=${SEED:-42}
EVAL_START=${EVAL_START:-90}
EVAL_QUERIES=${EVAL_QUERIES:-90}
EVAL_END=$((EVAL_START + EVAL_QUERIES - 1))

echo "=== RE-RUN GEMMA × STIGMERGIE C3 ONLY ==="
echo "Seed: $SEED | Eval: $EVAL_START → $EVAL_END"

if [[ -z "${OPENROUTER_API_KEY:-}" ]]; then
    echo "FATAL: OPENROUTER_API_KEY is empty." >&2
    exit 2
fi
python -c "import main" || { echo "FATAL: main import failed." >&2; exit 2; }

mkdir -p campaign_results/c3

# Ensure DBs are in a clean (non-WAL) state before read-only C3 reads
for db in pheromones/skills.db pheromones/protocols.db; do
    [ -f "$db" ] || { echo "FATAL: $db missing. Run adapt phase first." >&2; exit 2; }
    python -c "import sqlite3; c=sqlite3.connect('$db'); c.execute('PRAGMA wal_checkpoint(TRUNCATE);'); c.execute('PRAGMA journal_mode=DELETE;'); c.close()" || true
done
rm -f pheromones/*.db-shm pheromones/*.db-wal

for i in $(seq $EVAL_START $EVAL_END); do
    target="campaign_results/c3/query_${i}.json"
    if [ -s "$target" ]; then
        echo "[C3] Q$i already done, skip"
        continue
    fi
    echo "[C3] Q$i"
    python main.py \
        --adapter travelplanner \
        --objective "Query $i" \
        --config config/travelplanner_eval_c3_gemma.yaml \
        --query-idx "$i" \
        --seed "$SEED" \
        > "$target" 2>"campaign_results/c3/query_${i}.err" || true
    if [ ! -s "$target" ]; then
        echo "  WARN: empty output, err tail:" >&2
        tail -20 "campaign_results/c3/query_${i}.err" >&2
    fi
done

echo ""
echo "=== RE-RUN GEMMA C3 TERMINÉE ==="
