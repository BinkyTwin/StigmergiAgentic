"""Text edit operators with exact-match guards."""

from __future__ import annotations

from dataclasses import dataclass

from core_v10.contracts import JsonDict


@dataclass(frozen=True)
class ExactReplaceResult:
    """Result of validating and applying an exact replace operation in memory."""

    applied: bool
    text: str
    reason: str
    replacements: int = 0

    def to_dict(self) -> JsonDict:
        return {
            "applied": bool(self.applied),
            "reason": self.reason,
            "replacements": int(self.replacements),
        }


class ExactReplaceText:
    """Guarded exact text replacement.

    V11's rule is strict: no replace_text operation can be emitted unless the
    old span is proven present in the current file content.
    """

    operator_id = "ExactReplaceText"

    def applicable(
        self,
        *,
        current_text: str,
        old: str,
        expected_replacements: int = 1,
        allow_multiple: bool = False,
    ) -> bool:
        return self.apply(
            current_text=current_text,
            old=old,
            new=old,
            expected_replacements=expected_replacements,
            allow_multiple=allow_multiple,
        ).applied

    def apply(
        self,
        *,
        current_text: str,
        old: str,
        new: str,
        expected_replacements: int = 1,
        allow_multiple: bool = False,
    ) -> ExactReplaceResult:
        if not old:
            return ExactReplaceResult(
                applied=False,
                text=current_text,
                reason="old_span_empty",
            )
        count = str(current_text).count(old)
        expected = int(expected_replacements)
        if allow_multiple:
            if count < expected:
                return ExactReplaceResult(
                    applied=False,
                    text=current_text,
                    reason="old_not_present" if count == 0 else "replacement_count_too_low",
                    replacements=count,
                )
        elif count != expected:
            return ExactReplaceResult(
                applied=False,
                text=current_text,
                reason="old_not_present" if count == 0 else "replacement_count_mismatch",
                replacements=count,
            )
        return ExactReplaceResult(
            applied=True,
            text=str(current_text).replace(old, new),
            reason="ok",
            replacements=count,
        )


__all__ = ["ExactReplaceResult", "ExactReplaceText"]
