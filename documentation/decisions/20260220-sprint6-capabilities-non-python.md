# 007 Sprint 6 Capability Extraction with Non-Python Text Pipeline

**Date**: 2026-02-20  
**Status**: Accepted  
**Context**: Lotfi + Codex

---

## Context

Sprint 6 required two aligned outcomes:
1. Extract specialized agent logic into reusable capabilities for V0.2 generalist agents.
2. Extend migration scope beyond `.py` files, because Python 2 references also live in docs, scripts, and configuration artifacts.

The existing system already had robust Python checks and confidence-based validation, but no reusable capability layer and no strict non-Python guardrails.

## Alternatives Considered

### Alternative A: Refactor only (Python-only parity)

**Pros**
- Minimal risk.
- Lowest implementation effort.

**Cons**
- Does not satisfy the expanded Sprint 6 scope.
- Leaves migration inconsistencies in non-Python files unresolved.

### Alternative B: Refactor + non-Python discovery only

**Pros**
- Adds visibility on non-Python impacts.
- Lower risk than full pipeline support.

**Cons**
- No execution path for remediation.
- Requires immediate follow-up sprint to become actionable.

### Alternative C: Refactor + full non-Python strict pipeline (chosen)

**Pros**
- End-to-end migration coverage across code + text artifacts.
- Reusable capabilities ready for Sprint 7 generalist orchestration.
- Keeps safety through strict tester guardrails and existing validator thresholds.

**Cons**
- Higher implementation surface in Sprint 6.
- More edge cases in non-Python validation.

## Decision

**Chosen**: Alternative C.

Implemented `agents/capabilities/{discover,transform,test,validate}.py`, refactored specialized agents into thin wrappers, and enabled strict non-Python text handling via `capabilities.non_python`.

## Consequences

### Positive
- Capability layer is now reusable by future `StigmergicAgent`.
- `.py` behavior remains backward-compatible.
- Non-Python migration traces are now discoverable, transformable, and testable.

### Negative / Risks
- Non-Python strict checks may produce more `retry`/`needs_review` on ambiguous references.
- Additional config surface requires careful defaults.

### Code Impact
- New modules: `agents/capabilities/*.py`
- Refactored wrappers: `agents/scout.py`, `agents/transformer.py`, `agents/tester.py`, `agents/validator.py`
- New tests: `tests/test_capabilities.py`
- Config extension: `stigmergy/config.yaml` (`capabilities.non_python`)

## Validation

Executed and passed:

```bash
uv run pytest tests/test_capabilities.py -v
uv run pytest tests/test_scout.py tests/test_transformer.py tests/test_tester.py tests/test_validator.py -v
uv run pytest tests/test_agents_integration.py -v
uv run pytest tests/ -v
```

Result: **100 passed, 1 skipped** on the full suite.

## Metadata

- ADR created by: Codex
- ADR validated by: execution evidence (green test suite)
- Version: 1.0
- Last modified: 2026-02-20

