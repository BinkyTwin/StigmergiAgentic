"""V11 guarded edit-set validation tests."""

from __future__ import annotations

from core_v10.operators import validate_edit_set_against_workspace


class StubWorkspace:
    def __init__(self, files: dict[str, str]) -> None:
        self.files = dict(files)

    def read_file(self, rel: str, *, max_bytes: int = 0) -> str:
        return self.files[rel]


def test_guard_accepts_exact_replace_against_workspace() -> None:
    result = validate_edit_set_against_workspace(
        {
            "edits": [
                {
                    "type": "replace_text",
                    "path": "pom.xml",
                    "old": "<java.version>1.8</java.version>",
                    "new": "<java.version>17</java.version>",
                    "expected_replacements": 1,
                }
            ]
        },
        StubWorkspace({"pom.xml": "<java.version>1.8</java.version>"}),
    )

    assert result.ok is True
    assert result.issues == ()


def test_guard_rejects_old_span_absent_in_real_workspace() -> None:
    result = validate_edit_set_against_workspace(
        {
            "edits": [
                {
                    "type": "replace_text",
                    "path": "pom.xml",
                    "old": "<java.version>1.8</java.version>",
                    "new": "<java.version>17</java.version>",
                    "expected_replacements": 1,
                }
            ]
        },
        StubWorkspace({"pom.xml": "<java.version>17</java.version>"}),
    )

    assert result.ok is False
    assert result.issues[0].reason == "old_span_absent"
    assert result.issues[0].actual_replacements == 0


def test_guard_rejects_sequential_duplicate_replace_that_adapter_would_fail() -> None:
    result = validate_edit_set_against_workspace(
        {
            "edits": [
                {
                    "type": "replace_text",
                    "path": "pom.xml",
                    "old": "<plugin.version>1</plugin.version>",
                    "new": "<plugin.version>2</plugin.version>",
                    "expected_replacements": 1,
                    "allow_multiple": True,
                },
                {
                    "type": "replace_text",
                    "path": "pom.xml",
                    "old": "<plugin.version>1</plugin.version>",
                    "new": "<plugin.version>3</plugin.version>",
                    "expected_replacements": 1,
                    "allow_multiple": True,
                },
            ]
        },
        StubWorkspace({"pom.xml": "<plugin.version>1</plugin.version>"}),
    )

    assert result.ok is False
    assert result.issues[0].index == 1
    assert result.issues[0].reason == "old_span_absent"
    assert result.issues[0].actual_replacements == 0


def test_guard_rejects_path_traversal() -> None:
    result = validate_edit_set_against_workspace(
        {
            "edits": [
                {
                    "type": "replace_text",
                    "path": "../pom.xml",
                    "old": "x",
                    "new": "y",
                }
            ]
        },
        StubWorkspace({"pom.xml": "x"}),
    )

    assert result.ok is False
    assert result.issues[0].reason == "unsafe_path"


def test_guard_rejects_test_file_without_justification() -> None:
    result = validate_edit_set_against_workspace(
        {
            "edits": [
                {
                    "type": "replace_text",
                    "path": "src/test/java/FooTest.java",
                    "old": "assertEquals(1, value);",
                    "new": "assertEquals(2, value);",
                }
            ]
        },
        StubWorkspace({"src/test/java/FooTest.java": "assertEquals(1, value);"}),
    )

    assert result.ok is False
    assert result.issues[0].reason == "test_modification_without_justification"


def test_guard_allows_justified_test_compile_fix() -> None:
    result = validate_edit_set_against_workspace(
        {
            "rationale": "test compile migration fix",
            "edits": [
                {
                    "type": "replace_text",
                    "path": "src/test/java/FooTest.java",
                    "old": "javax.annotation.Nullable",
                    "new": "jakarta.annotation.Nullable",
                }
            ],
        },
        StubWorkspace({"src/test/java/FooTest.java": "javax.annotation.Nullable"}),
    )

    assert result.ok is True
