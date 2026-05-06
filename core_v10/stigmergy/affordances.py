"""Deterministic feedback-to-affordance policy for V11."""

from __future__ import annotations

from typing import Iterable

from core_v10.contracts import FeedbackDigest, JsonDict
from core_v10.signals import SignalRecord
from core_v10.stigmergy.records import Affordance, stable_v11_id


def affordances_from_feedback(
    *,
    feedback: FeedbackDigest,
    signals: Iterable[SignalRecord],
    source_event_ids: tuple[str, ...] = (),
    now_seq: int = 0,
) -> tuple[Affordance, ...]:
    """Create actionable affordances from verifier feedback and active signals."""

    source_signal_ids = tuple(record.signal_id for record in signals)
    base_priority = _severity_priority(feedback.severity)
    items: list[Affordance] = []

    def add(
        *,
        action_type: str,
        target: str,
        reason: str,
        worker: str,
        priority: float = 0.0,
        metadata: JsonDict | None = None,
        ttl: int | None = 12,
    ) -> None:
        payload = {
            "action_type": action_type,
            "target": target,
            "reason": reason,
            "worker": worker,
            "source_event_ids": source_event_ids,
            "source_signal_ids": source_signal_ids,
        }
        items.append(
            Affordance(
                affordance_id=stable_v11_id("aff", payload),
                action_type=action_type,
                target=target,
                reason=reason,
                priority=max(0.0, min(1.0, base_priority + priority)),
                source_event_ids=source_event_ids,
                source_signal_ids=source_signal_ids,
                expected_worker_kind=worker,
                expires_at_seq=(now_seq + ttl if ttl is not None else None),
                metadata=dict(metadata or {}),
            )
        )

    failure_type = str(feedback.failure_type or "")
    summary = str(feedback.summary or "")
    evidence_text = "\n".join(str(x) for x in feedback.evidence)
    full_text = f"{failure_type}\n{summary}\n{evidence_text}".lower()

    if failure_type == "answer_mismatch":
        add(
            action_type="replace_answer",
            target="answer.txt",
            reason="answer_mismatch",
            worker="exact_edit_guard",
            priority=0.15,
        )

    if "replacement_count_too_low" in full_text or "replacement_count_mismatch" in full_text:
        target = _first_location_path(feedback) or "current_file"
        add(
            action_type="inspect_current_file",
            target=target,
            reason="replacement_count_too_low",
            worker="exact_edit_guard",
            priority=0.2,
        )
        add(
            action_type="derive_exact_old_span",
            target=target,
            reason="replacement_count_too_low",
            worker="exact_edit_guard",
            priority=0.15,
        )

    if any(token in full_text for token in ("class_version_error", "source_target", "release")):
        add(
            action_type="set_maven_compiler_release",
            target="pom.xml",
            reason=failure_type or "class_version_error",
            worker="maven_compiler_operator",
            priority=0.15,
        )

    if any(token in full_text for token in ("compile_error", "compilation failure", "source option")):
        add(
            action_type="select_compile_operator",
            target="maven_build",
            reason=failure_type or "compile_error",
            worker="maven_compiler_operator",
            priority=0.1,
        )

    if any(token in full_text for token in ("dependency_resolution", "could not resolve", "javax.xml.bind", "jaxb")):
        add(
            action_type="add_missing_dependency",
            target="pom.xml",
            reason=failure_type or "dependency_resolution_error",
            worker="dependency_operator",
            priority=0.12,
            metadata={"pattern": "jaxb" if "jaxb" in full_text or "javax.xml.bind" in full_text else "dependency"},
        )

    if "official_eval_failed" in full_text or "#tests=-2" in full_text or "test summary" in full_text:
        add(
            action_type="interpret_official_eval",
            target="official_eval",
            reason=failure_type or "official_eval_failed",
            worker="official_eval_interpreter",
            priority=0.2,
        )
        add(
            action_type="preserve_test_count",
            target="tests",
            reason="preserve_existing_tests",
            worker="test_preservation_checker",
            priority=0.16,
        )

    if "preserve_existing_tests" in set(feedback.anti_actions):
        add(
            action_type="guard_existing_tests",
            target="tests",
            reason="anti_action:preserve_existing_tests",
            worker="test_preservation_checker",
            priority=0.08,
        )

    for index, recommended in enumerate(feedback.recommended_next_actions):
        if not isinstance(recommended, dict):
            continue
        action = str(recommended.get("action") or "recommended_action")
        target = str(recommended.get("target") or action)
        worker = _worker_for_action(action)
        add(
            action_type=action,
            target=target,
            reason=str(recommended.get("rationale") or failure_type or action),
            worker=worker,
            priority=max(0.0, 0.08 - index * 0.02),
            metadata={"recommended": dict(recommended)},
        )

    # Stable de-duplication by id keeps replay and live snapshots identical.
    by_id = {item.affordance_id: item for item in items}
    return tuple(
        sorted(by_id.values(), key=lambda item: (-item.priority, item.affordance_id))
    )


def _severity_priority(severity: str) -> float:
    if severity in {"fatal", "blocking"}:
        return 0.65
    if severity == "warning":
        return 0.5
    return 0.35


def _first_location_path(feedback: FeedbackDigest) -> str | None:
    for location in feedback.locations:
        if isinstance(location, dict) and location.get("path"):
            return str(location["path"])
    return None


def _worker_for_action(action: str) -> str:
    action = action.lower()
    if any(token in action for token in ("dependency", "jaxb", "javax")):
        return "dependency_operator"
    if any(token in action for token in ("surefire", "official", "test_summary")):
        return "official_eval_interpreter"
    if "test" in action or "preserve" in action:
        return "test_preservation_checker"
    if any(token in action for token in ("compile", "maven", "release", "source", "target")):
        return "maven_compiler_operator"
    if any(token in action for token in ("replace", "exact", "inspect")):
        return "exact_edit_guard"
    return "operator_selector"


__all__ = ["affordances_from_feedback"]
