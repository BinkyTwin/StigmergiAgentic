#!/bin/bash
# Sprint 9 — Campagne 1 seed : C2 (skills) vs C3 (skills + cross_run)
#
# Usage:
#   SEED=42 API_KEY=$(grep OPENROUTER_API_KEY .env | cut -d= -f2) bash scripts/run_sprint9_campaign_1seed.sh

set -euo pipefail

SEED=${SEED:-42}
QUERIES=${QUERIES:-10}
QUERY_START=${QUERY_START:-0}
API_KEY=${API_KEY:-}

if [ -z "$API_KEY" ]; then
    echo "ERREUR: exporte API_KEY avant de lancer"
    exit 1
fi

echo "========================================"
echo "SPRINT 9 CAMPAGNE — 1 SEED"
echo "Seed: $SEED | Queries: $QUERY_START → $((QUERY_START + QUERIES - 1))"
echo "========================================"

# ==========================================
# PHASE 1 : C2 — Skills sans cross_run
# ==========================================
echo ""
echo "=== PHASE 1 : C2 (skills sans cross_run) ==="
echo "Config: config/travelplanner_adapt_nocross.yaml"

# Nettoyage propre
rm -f pheromones/skills.db pheromones/protocols.db
mkdir -p campaign_results/c2 campaign_results/c3

for i in $(seq $QUERY_START $((QUERY_START + QUERIES - 1))); do
    echo "[C2] Query $i ..."
    OPENROUTER_API_KEY="$API_KEY" \
        uv run python main.py \
        --adapter travelplanner \
        --objective "Query $i" \
        --config config/travelplanner_adapt_nocross.yaml \
        --query-idx "$i" \
        --seed "$SEED" \
        > "campaign_results/c2/query_${i}.json" 2>/dev/null || true
    echo "  done"
done

# ==========================================
# PHASE 2 : C3 — Skills + cross_run
# ==========================================
echo ""
echo "=== PHASE 2 : C3 (skills + cross_run) ==="
echo "Config: config/travelplanner_adapt_cross.yaml"
echo "Note: garde skills.db accumulés en Phase 1"

# On garde skills.db (accumulation cross-campagne)
# On vide protocols.db pour repartir propre sur le cross_run
rm -f pheromones/protocols.db

for i in $(seq $QUERY_START $((QUERY_START + QUERIES - 1))); do
    echo "[C3] Query $i ..."
    OPENROUTER_API_KEY="$API_KEY" \
        uv run python main.py \
        --adapter travelplanner \
        --objective "Query $i" \
        --config config/travelplanner_adapt_cross.yaml \
        --query-idx "$i" \
        --seed "$SEED" \
        > "campaign_results/c3/query_${i}.json" 2>/dev/null || true
    echo "  done"
done

# ==========================================
# ANALYSE
# ==========================================
echo ""
echo "=== ANALYSE ==="

python3 - << 'PYEOF'
import json
from pathlib import Path

def parse_results(phase_dir):
    results = []
    for f in sorted(Path(phase_dir).glob("query_*.json")):
        text = f.read_text()
        for idx in range(text.rfind("}"), -1, -1):
            if text[idx] == "{":
                try:
                    data = json.loads(text[idx:])
                    q = int(f.stem.split("_")[1])
                    results.append((q, data))
                    break
                except:
                    continue
    return results

def summarize(results, label):
    if not results:
        print(f"{label}: Aucun résultat")
        return
    
    passed = sum(1 for _, d in results if d.get("evaluation", {}).get("passed", False))
    total = len(results)
    scores = [d.get("evaluation", {}).get("score", 0.0) for _, d in results]
    avg_score = sum(scores) / len(scores) if scores else 0
    
    stop_reasons = {}
    for _, d in results:
        sr = d.get("stop_reason", "unknown")
        stop_reasons[sr] = stop_reasons.get(sr, 0) + 1
    
    print(f"\n{label}:")
    print(f"  Pass rate: {passed}/{total} ({100*passed/total:.1f}%)")
    print(f"  Avg score: {avg_score:.3f}")
    print(f"  Stop reasons: {stop_reasons}")
    
    # Émergence moyenne
    pu = [d.get("emergence_summary", {}).get("parallel_utilization", 0) for _, d in results]
    ct = [d.get("emergence_summary", {}).get("convergence_tick", 0) for _, d in results]
    if pu:
        print(f"  Avg parallel_utilization: {sum(pu)/len(pu):.3f}")
    if ct:
        print(f"  Avg convergence_tick: {sum(ct)/len(ct):.1f}")

c2 = parse_results("campaign_results/c2")
c3 = parse_results("campaign_results/c3")

summarize(c2, "C2 (skills sans cross_run)")
summarize(c3, "C3 (skills + cross_run)")

# Comparaison par query
print("\n--- Comparaison par query ---")
for q in sorted(set([q for q, _ in c2 + c3])):
    c2_data = next((d for qq, d in c2 if qq == q), None)
    c3_data = next((d for qq, d in c3 if qq == q), None)
    c2_pass = c2_data.get("evaluation", {}).get("passed", False) if c2_data else "N/A"
    c3_pass = c3_data.get("evaluation", {}).get("passed", False) if c3_data else "N/A"
    print(f"  Query {q}: C2={c2_pass} vs C3={c3_pass}")

# Skills accumulés
print("\n--- Skills accumulés ---")
try:
    sys.path.insert(0, str(Path(".").resolve()))
    from core.marker_store import MarkerStore
    store = MarkerStore(db_path=Path("pheromones/skills.db"), session_isolation=False, traceability=False)
    skills = store.query_markers(marker_type="skill")
    print(f"Total skills: {len(skills)}")
    for sk in skills[:10]:
        print(f"  - {sk.id} (intensity={sk.intensity:.3f}, uses={sk.payload.get('usage_count', 0)})")
except Exception as e:
    print(f"Erreur lecture skills: {e}")

# Protocols C3
print("\n--- Protocols C3 ---")
try:
    store = MarkerStore(db_path=Path("pheromones/protocols.db"), session_isolation=False, traceability=False)
    protocols = store.query_markers(marker_type="coordination_protocol")
    print(f"Total protocols: {len(protocols)}")
    for p in protocols:
        print(f"  - {p.id} (score={p.payload.get('score', 'N/A')})")
except Exception as e:
    print(f"Erreur lecture protocols: {e}")

PYEOF

echo ""
echo "=== CAMPAGNE TERMINÉE ==="
echo "Résultats bruts dans campaign_results/c2/ et campaign_results/c3/"
