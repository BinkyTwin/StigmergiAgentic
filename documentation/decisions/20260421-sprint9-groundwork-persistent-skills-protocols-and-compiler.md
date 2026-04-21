# ADR 016 — Sprint 9 Groundwork for Persistent Skills, Protocol Artifacts, and Objective-Conditioned Protocol Compilation

- Date: 2026-04-21
- Status: Accepted

## Context

Sprint 9 aims to validate three thesis-facing claims:

1. C1 — objective-conditioned protocol generation over a fixed substrate
2. C2 — cross-run skill accumulation through persistent medium-level artifacts
3. C3 — cross-run coordination improvement through persistent protocol artifacts

The Sprint 8 runtime already provides the substrate: markers, SQLite/WAL persistence, DAG validation, reinforcement, emergence metrics, and opt-in adaptive controls. What was missing was a safe entry point for Sprint 9 without immediately entangling the full runtime with unfinished persistence or protocol-learning behavior.

## Decision

Introduce a first Sprint 9 groundwork layer with four architectural choices:

1. Add explicit config surfaces for `skill_library`, `protocol`, `emergence.cross_run`, `reinforcement.promotion_min_uses`, and `agents.protocol_compiler`, all disabled by default.
2. Add structured protocol-compilation primitives (`ProtocolSpec`, protocol-compiler prompt, optional `DomainAdapter.compile_protocol()`).
3. Wire `main.py` to prefer compiled protocols only when the compiler is enabled and returns a valid DAG; otherwise fall back to `initial_markers()` with no behavior change.
4. Make `llm/__init__.py` and `adapters/__init__.py` lazy-import based so prompt-only or adapter-local code paths do not pay the cost of loading the full OpenAI/httpx-heavy stack during unit tests or protocol-compilation scaffolding.

## Consequences

### Positive

- Sprint 9 can now proceed incrementally without breaking Sprint 8 defaults.
- The repo has a stable contract for future `lesson -> skill` promotion and `coordination_protocol` persistence.
- Objective-conditioned protocol generation can be tested in the assistant domain before TravelPlanner-specific persistence work lands.
- Import-time overhead is reduced for prompt/schema-only paths, which improves unit-test ergonomics around the new compiler surface.

### Negative

- The persistent stores themselves are not yet wired into the runtime.
- `compile_protocol()` is currently implemented only on the assistant side, and only as an opt-in scaffold.
- The new train/eval presets are structural scaffolds, not validated benchmark evidence for C1/C2/C3 yet.

## Alternatives Considered

### Full runtime wiring immediately

Rejected because it would couple store design, persistence semantics, benchmark methodology, and protocol compilation in one large change, making regression analysis harder.

### Keep Sprint 9 purely at design-doc level

Rejected because the next implementation step would still lack stable config, prompt, schema, and adapter/runtime seams.

## Validation

- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest tests/unit/test_config.py tests/unit/test_emergence.py tests/unit/test_protocol_compiler.py -q`
