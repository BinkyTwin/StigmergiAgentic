"""Typed operator guards shared by V11 strategies."""

from core_v10.operators.guarded_edit_set import (
    GuardedEditIssue,
    GuardedEditSetResult,
    validate_edit_set_against_workspace,
)
from core_v10.operators.text_operator import ExactReplaceText, ExactReplaceResult

__all__ = [
    "ExactReplaceResult",
    "ExactReplaceText",
    "GuardedEditIssue",
    "GuardedEditSetResult",
    "validate_edit_set_against_workspace",
]
