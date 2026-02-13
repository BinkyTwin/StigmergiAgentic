#!/bin/bash
# Script de vérification de migration stigmergique

echo "=== Vérification Migration Stigmergique ==="
echo ""

# 1. Statuts des fichiers
echo "📊 Statuts des fichiers (status.json):"
if [ -f "pheromones/status.json" ]; then
    cat pheromones/status.json | jq -r '[.[] | .status] | group_by(.) | map({status: .[0], count: length}) | .[]' | jq -r '"\(.status): \(.count)"'
else
    echo "❌ status.json introuvable"
fi
echo ""

# 2. Confiance moyenne
echo "📈 Confiance moyenne (quality.json):"
if [ -f "pheromones/quality.json" ]; then
    cat pheromones/quality.json | jq '[.[] | .confidence] | add / length'
else
    echo "❌ quality.json introuvable"
fi
echo ""

# 3. Commits stigmergiques
echo "🔧 Commits Git (target_repo/):"
if [ -d "target_repo/.git" ]; then
    cd target_repo/
    echo "Total commits stigmergiques: $(git log --all --grep='stigmergic' --oneline | wc -l | tr -d ' ')"
    echo "Derniers commits:"
    git log --all --grep='stigmergic' --oneline | head -5
    cd ..
else
    echo "❌ Git repo introuvable dans target_repo/"
fi
echo ""

# 4. Taux de réussite
echo "✅ Taux de réussite:"
if [ -f "pheromones/status.json" ]; then
    total=$(cat pheromones/status.json | jq 'length')
    validated=$(cat pheromones/status.json | jq '[.[] | select(.status == "validated")] | length')
    if [ "$total" -gt 0 ]; then
        success_rate=$(echo "scale=2; $validated * 100 / $total" | bc)
        echo "  $validated/$total fichiers validés (${success_rate}%)"
    else
        echo "  Aucune donnée disponible"
    fi
else
    echo "❌ status.json introuvable"
fi
echo ""

# 5. Tests Python 3
echo "🧪 Validation Python 3 (target_repo/):"
if [ -d "target_repo" ]; then
    cd target_repo/
    py3_files=$(find . -name "*.py" -exec python3 -m py_compile {} \; 2>&1 | grep -c "SyntaxError" || echo "0")
    if [ "$py3_files" -eq 0 ]; then
        echo "  ✅ Tous les .py compilent en Python 3"
    else
        echo "  ⚠️  $py3_files fichiers avec erreurs de syntaxe"
    fi
    cd ..
else
    echo "❌ target_repo/ introuvable"
fi
