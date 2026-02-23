# ADR-008: Sprint 6 Guardrail Hardening for Non-Python Pipeline

- **Date**: 2026-02-23
- **Statut**: Accepte
- **Contexte**: Sprint 6 a etendu le pipeline aux fichiers texte non-Python avec guardrails stricts. Une revue a releve trois risques: references `.py` resolues hors repo, dependance `bash` pouvant casser des environnements sans bash, et incoherence de prompt systeme en mode non-Python.

## Decision

1. **Securite references `.py` non-Python**
   - Rejeter les references absolues (`/path`, `C:\path`) et les traversals (`..`).
   - Resoudre uniquement dans le scope du repo via index des fichiers Python connus.

2. **Portabilite guardrail `.sh`**
   - Si `bash` est indisponible, ne pas faire echouer le test strict.
   - Emettre une metadata non-bloquante: `guardrail_tool_unavailable:bash`.

3. **Alignement prompt mode non-Python**
   - Utiliser un role prompt dedie non-Python pour le Transformer au lieu du prompt Python-only.

## Consequences

### Positives
- Reduit les faux positifs de references Python en dehors du repo.
- Ameliore la portabilite multi-environnements des guardrails non-Python.
- Ameliore la coherence system/user prompt en transformation de texte.

### Trade-offs
- Cout mineur de maintenance: index des references Python par evaluation.
- Besoin de suivi metadonnees non-bloquantes cote qualite.

## Validation

- `uv run pytest tests/test_capabilities.py tests/test_transformer.py -v`
- `uv run pytest tests/ -v`
- `uv run ruff check agents/capabilities/test.py agents/capabilities/transform.py agents/transformer.py tests/test_capabilities.py tests/test_transformer.py`
- `uv run mypy agents/capabilities/test.py agents/capabilities/transform.py agents/transformer.py --ignore-missing-imports`

## Suite planifiee

- Sprint 7.1 hardening: cache tick-level de l'index des references Python pour execution parallele (reduction CPU sur gros repos).
