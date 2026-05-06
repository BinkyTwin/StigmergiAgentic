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

from adapters_v10.migrationbench.context import (
    MigrationContext,
    migration_context_from_observation,
)
from adapters_v10.migrationbench.operators import target_java_replacements


def deterministic_maven_target_java_edits(
    pom_paths: Iterable[str],
    pom_texts: dict[str, str],
    context: MigrationContext,
) -> list[dict[str, Any]]:
    """Build typed-edit dicts for conservative target-Java POM updates.

    ``pom_texts`` maps the repository-relative path to the raw content of
    the corresponding ``pom.xml`` file. Only paths that actually contain a
    source-version declaration from ``context`` contribute edits; that keeps
    the candidate strictly minimal even on multi-module repos.
    """

    edits: list[dict[str, Any]] = []
    for rel_path in pom_paths:
        text = pom_texts.get(rel_path, "")
        if not text:
            continue
        for old, new in target_java_replacements(context):
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
    """Return a provider that emits deterministic target-Java POM edits.

    The provider walks the active workspace, reads every ``pom.xml`` file,
    and produces *one* candidate carrying a :class:`TypedEditSet` with the
    minimum edits needed to flip source declarations to the target Java.
    """

    from adapters_v10.migrationbench.adapter import MigrationBenchAdapterV10

    if not isinstance(adapter, MigrationBenchAdapterV10):
        raise TypeError(
            "deterministic provider requires MigrationBenchAdapterV10, got "
            f"{type(adapter).__name__}"
        )

    def provide(observation: Observation, instance: RunInstance) -> Sequence[Candidate]:
        context = migration_context_from_observation(observation, instance)
        workspace = adapter._require_base_workspace()  # type: ignore[attr-defined]
        pom_paths = [t for t in workspace.list_targets() if t.endswith("pom.xml")]
        pom_texts: dict[str, str] = {}
        for rel in pom_paths:
            try:
                pom_texts[rel] = workspace.read_file(rel, max_bytes=2_000_000)
            except Exception:  # noqa: BLE001
                continue
        edit_dicts = deterministic_maven_target_java_edits(
            pom_paths,
            pom_texts,
            context,
        )
        if not edit_dicts:
            # No matching source declarations were found; the strategy can
            # record the no-candidate path cleanly.
            return []
        branch_id = f"target_java_{context.target_java}"
        return [
            Candidate(
                candidate_id=f"{instance.instance_id}-{branch_id}",
                kind=CandidateKind.PATCH,
                payload={
                    "branch_id": branch_id,
                    "edit_set": {
                        "edits": edit_dicts,
                        "rationale": (
                            "Conservative target-Java source/target/release "
                            f"POM updates for Java {context.target_java}."
                        ),
                        "expected_build_command": context.expected_build_command,
                    },
                },
                origin="builtin_deterministic_maven_target_java",
                metadata={"migration_context": context.to_dict()},
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
    "deterministic_maven_target_java_edits",
    "make_migrationbench_deterministic_provider",
    "make_migrationbench_noop_repair_provider",
    "make_migrationbench_operator_provider",
    "make_toy_exact_answer_operator_provider",
]
