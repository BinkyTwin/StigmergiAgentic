"""Built-in candidate / repair providers for the V10 bench harness.

These providers are deterministic and LLM-free. They exist so the harness
can be smoked end-to-end (and used in CI integration tests) without
incurring API costs. LLM-backed providers will live alongside them once
the strategy ladder reaches the StigmergicBlackboard phase.
"""

from __future__ import annotations

from typing import Any, Iterable, Sequence

from core_v10.contracts import (
    Candidate,
    CandidateKind,
    Observation,
    RunInstance,
)


JAVA17_POM_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    ("<maven.compiler.source>1.8</maven.compiler.source>",
     "<maven.compiler.source>17</maven.compiler.source>"),
    ("<maven.compiler.target>1.8</maven.compiler.target>",
     "<maven.compiler.target>17</maven.compiler.target>"),
    ("<maven.compiler.release>8</maven.compiler.release>",
     "<maven.compiler.release>17</maven.compiler.release>"),
    ("<source>1.8</source>", "<source>17</source>"),
    ("<target>1.8</target>", "<target>17</target>"),
    ("<release>8</release>", "<release>17</release>"),
    ("<java.version>1.8</java.version>", "<java.version>17</java.version>"),
    ("<java.version>8</java.version>", "<java.version>17</java.version>"),
)


def deterministic_pom17_edits(pom_paths: Iterable[str], pom_texts: dict[str, str]) -> list[dict[str, Any]]:
    """Build a list of typed-edit dicts for conservative POM Java 17 updates.

    ``pom_texts`` maps the repository-relative path to the raw content of
    the corresponding ``pom.xml`` file. Only paths that actually contain
    one of the known Java 8 declarations contribute edits; that keeps the
    candidate strictly minimal even on multi-module repos.
    """

    edits: list[dict[str, Any]] = []
    for rel_path in pom_paths:
        text = pom_texts.get(rel_path, "")
        if not text:
            continue
        for old, new in JAVA17_POM_REPLACEMENTS:
            count = text.count(old)
            if count <= 0:
                continue
            edits.append(
                {
                    "type": "replace_text",
                    "path": rel_path,
                    "old": old,
                    "new": new,
                    "expected_replacements": count,
                    "allow_multiple": True,
                }
            )
    return edits


def make_migrationbench_deterministic_provider(adapter, _extras: dict[str, Any]):
    """Return a candidate provider that emits the deterministic Java 17 POM edits.

    The provider walks the active workspace, reads every ``pom.xml`` file,
    and produces *one* candidate carrying a :class:`TypedEditSet` with the
    minimum edits needed to flip Java 8 declarations to Java 17.
    """

    from adapters_v10.migrationbench.adapter import MigrationBenchAdapterV10

    if not isinstance(adapter, MigrationBenchAdapterV10):
        raise TypeError(
            "deterministic provider requires MigrationBenchAdapterV10, got "
            f"{type(adapter).__name__}"
        )

    def provide(observation: Observation, instance: RunInstance) -> Sequence[Candidate]:
        workspace = adapter._require_base_workspace()  # type: ignore[attr-defined]
        pom_paths = [t for t in workspace.list_targets() if t.endswith("pom.xml")]
        pom_texts: dict[str, str] = {}
        for rel in pom_paths:
            try:
                pom_texts[rel] = workspace.read_file(rel, max_bytes=2_000_000)
            except Exception:  # noqa: BLE001
                continue
        edit_dicts = deterministic_pom17_edits(pom_paths, pom_texts)
        if not edit_dicts:
            # No Java 8 declarations were found; emit an empty candidate so the
            # adapter can record the "no migration needed" outcome cleanly.
            return []
        return [
            Candidate(
                candidate_id=f"{instance.instance_id}-pom17",
                kind=CandidateKind.PATCH,
                payload={
                    "branch_id": "pom17",
                    "edit_set": {
                        "edits": edit_dicts,
                        "rationale": "Conservative Java 17 source/target/release POM updates.",
                        "expected_build_command": "mvn clean verify",
                    },
                },
                origin="builtin_deterministic_pom17",
            )
        ]

    return provide


def make_migrationbench_noop_repair_provider(_adapter, _extras: dict[str, Any]):
    """Repair provider that gives up — the deterministic patch already failed."""

    def provide(feedback, original, observation, instance):
        return []

    return provide


def make_toy_exact_answer_operator_provider(_adapter, _extras: dict[str, Any]):
    """Return a V11 toy operator provider that writes the expected answer."""

    def provide(feedback, original, observation, instance, affordance):
        if feedback.failure_type != "answer_mismatch":
            return []
        expected = str(observation.data.get("expected", ""))
        source_affordance_id = (
            affordance.affordance_id if affordance is not None else None
        )
        return [
            Candidate(
                candidate_id=f"{original.candidate_id}-exact-answer",
                kind=CandidateKind.TEXT,
                payload={"answer": expected},
                origin="v11_exact_answer_operator",
                metadata={
                    "operator_invocation": {
                        "operator_id": "ExactAnswerWrite",
                        "params": {"expected": expected},
                        "target_files": ["answer.txt"],
                        "rationale": "Verifier reported answer_mismatch.",
                        "source_affordance_id": source_affordance_id,
                    },
                    "source_affordance_id": source_affordance_id,
                    "worker_id": "exact_edit_guard",
                },
            )
        ]

    return provide


def make_migrationbench_operator_provider(_adapter, _extras: dict[str, Any]):
    """Return a V11 MigrationBench typed-operator provider."""

    from adapters_v10.migrationbench.operators import (
        migrationbench_operator_candidates,
    )

    def provide(feedback, original, observation, instance, affordance):
        return migrationbench_operator_candidates(
            feedback=feedback,
            original=original,
            observation=observation,
            instance=instance,
            affordance=affordance,
        )

    return provide


__all__ = [
    "JAVA17_POM_REPLACEMENTS",
    "deterministic_pom17_edits",
    "make_migrationbench_deterministic_provider",
    "make_migrationbench_noop_repair_provider",
    "make_migrationbench_operator_provider",
    "make_toy_exact_answer_operator_provider",
]
