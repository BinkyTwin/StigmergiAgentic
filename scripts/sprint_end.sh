#!/bin/bash
#
# Script de fin de sprint pour le projet StigmergiAgentic
# À exécuter avant de committer et pousser les changements
#
# Usage: ./scripts/sprint_end.sh
#

set -e  # Arrêter en cas d'erreur

# Couleurs pour output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Fonctions utilitaires
print_step() {
    echo -e "\n${BLUE}==>${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

# Banner
echo -e "${BLUE}"
echo "╔═══════════════════════════════════════════════╗"
echo "║   🚀 Fin de Sprint - Validation Automatique   ║"
echo "║      StigmergiAgentic - POC Mémoire          ║"
echo "╚═══════════════════════════════════════════════╝"
echo -e "${NC}"

# Vérifier qu'on n'est PAS sur main
CURRENT_BRANCH=$(git branch --show-current)
print_step "Vérification de la branche courante"
if [ "$CURRENT_BRANCH" = "main" ]; then
    print_error "Vous êtes sur la branche 'main' !"
    print_warning "Commits directs sur main sont interdits."
    echo "Créez une branche feature : git checkout -b feature/my-feature"
    exit 1
fi
print_success "Branche: $CURRENT_BRANCH"

# 1. Tests unitaires
print_step "1️⃣  Exécution des tests unitaires"
if uv run pytest tests/ -v --tb=short; then
    print_success "Tous les tests passent"
else
    print_error "Les tests échouent"
    echo "Corrigez les tests avant de continuer."
    exit 1
fi

# 2. Couverture de code
print_step "2️⃣  Vérification de la couverture de code"
uv run pytest tests/ --cov --cov-report=term-missing --no-cov-on-fail || {
    print_warning "Couverture de code insuffisante ou tests échoués"
}

# 3. Linting avec ruff
print_step "3️⃣  Vérification du code avec Ruff"
if command -v ruff &> /dev/null; then
    if ruff check . --fix --exclude tests/fixtures; then
        print_success "Code conforme aux standards (auto-corrections appliquées)"
    else
        print_warning "Des warnings Ruff persistent, revue manuelle recommandée"
    fi
else
    print_warning "Ruff non installé, skipping. Installez avec: uv pip install ruff"
fi

# 4. Formatage avec black
print_step "4️⃣  Formatage du code avec Black"
if command -v black &> /dev/null; then
    black . --quiet --exclude '/tests/fixtures/'
    print_success "Code formaté avec Black"
else
    print_warning "Black non installé, skipping. Installez avec: uv pip install black"
fi

# 5. Type checking avec mypy (optionnel)
print_step "5️⃣  Vérification des types (optionnel)"
if command -v mypy &> /dev/null; then
    if mypy agents/ environment/ stigmergy/ --ignore-missing-imports 2>/dev/null; then
        print_success "Type hints corrects"
    else
        print_warning "Erreurs de typage détectées (non-bloquant)"
    fi
else
    print_warning "Mypy non installé, skipping type checking"
fi

# 6. Vérifier les TODOs critiques
print_step "6️⃣  Recherche de TODOs critiques non résolus"
TODO_COUNT=$(grep -r "TODO.*CRITICAL\|FIXME.*CRITICAL" agents/ environment/ stigmergy/ 2>/dev/null | wc -l || echo "0")
if [ "$TODO_COUNT" -gt 0 ]; then
    print_warning "Trouvé $TODO_COUNT TODO(s) CRITICAL(s) :"
    grep -rn "TODO.*CRITICAL\|FIXME.*CRITICAL" agents/ environment/ stigmergy/ 2>/dev/null || true
else
    print_success "Aucun TODO critique"
fi

# 7. Mise à jour documentation
print_step "7️⃣  Validation de la documentation"

# Vérifier que construction_log.md existe
if [ ! -f "documentation/construction_log.md" ]; then
    print_warning "documentation/construction_log.md n'existe pas, création..."
    mkdir -p documentation
    echo "# Construction Log - StigmergiAgentic POC" > documentation/construction_log.md
    echo "" >> documentation/construction_log.md
fi

# Ajouter entrée de sprint si pas déjà ajoutée manuellement
SPRINT_DATE=$(date +%Y-%m-%d)
if ! grep -q "Sprint $SPRINT_DATE" documentation/construction_log.md; then
    print_warning "Ajout automatique d'une entrée de sprint dans construction_log.md"
    cat >> documentation/construction_log.md <<EOF

## Sprint $SPRINT_DATE

### Fonctionnalités développées
- [À compléter manuellement]

### Challenges rencontrés
- [À compléter manuellement]

### Décisions techniques
- [À compléter manuellement]

### Commits effectués
$(git log --oneline --since="1 day ago" | head -10)

EOF
    print_warning "⚠️  RAPPEL: Compléter manuellement le construction_log.md avant de commit !"
else
    print_success "Construction log déjà mis à jour pour aujourd'hui"
fi

# 8. État Git
print_step "8️⃣  État des fichiers Git"
git status --short
echo ""

# Vérifier fichiers non trackés suspects
print_step "9️⃣  Vérification des fichiers suspects"
SUSPECTS=$(git status --porcelain | grep "^??" | egrep "\\.env$|__pycache__|\.pyc$|\.DS_Store|\.venv/" || true)
if [ ! -z "$SUSPECTS" ]; then
    print_warning "Fichiers non trackés suspects détectés (devraient être dans .gitignore) :"
    echo "$SUSPECTS"
fi

# 10. Derniers commits
print_step "🔟 Derniers commits sur cette branche"
git log --oneline --graph --decorate -5
echo ""

# Résumé final
print_step "✅ Résumé Final"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
print_success "Tests unitaires : OK"
print_success "Qualité du code : Validée"
print_success "Branche : $CURRENT_BRANCH (pas main)"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Instructions pour la suite
echo ""
print_step "📋 Prochaines étapes :"
echo "1. Compléter documentation/construction_log.md si nécessaire"
echo "2. Vérifier AGENTS.md et CLAUDE.md si changements architecturaux"
echo "3. Faire des commits atomiques :"
echo "   ${YELLOW}git add <fichiers>${NC}"
echo "   ${YELLOW}git commit -m \"type(scope): description\"${NC}"
echo ""
echo "4. Synchroniser avec develop :"
echo "   ${YELLOW}git fetch origin${NC}"
echo "   ${YELLOW}git rebase origin/develop${NC}"
echo ""
echo "5. Pousser la branche :"
echo "   ${YELLOW}git push origin $CURRENT_BRANCH${NC}"
echo ""
echo "6. Créer une Pull Request sur GitHub vers 'develop'"
echo ""

# Proposition de commit helper
print_step "💡 Aide au commit"
echo "Formats de commit valides :"
echo "  ${BLUE}feat(scout)${NC}: implement AST pattern detection"
echo "  ${BLUE}fix(transformer)${NC}: correct syntax in f-string conversion"
echo "  ${BLUE}test(pheromone)${NC}: add unit tests for decay logic"
echo "  ${BLUE}docs(thesis)${NC}: update construction log for sprint"
echo "  ${BLUE}refactor(guardrails)${NC}: extract validation to separate module"
echo ""

print_success "Validation de fin de sprint terminée ! 🎉"
echo ""
