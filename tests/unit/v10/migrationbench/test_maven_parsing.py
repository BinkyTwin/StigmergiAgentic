from __future__ import annotations

from pathlib import Path

import pytest

from adapters_v10.migrationbench.maven import (
    classify_maven_failure,
    feedback_digest,
    parse_class_major_versions,
    required_test_count,
    surefire_test_count,
)


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Non-parseable POM", "pom_parse_error"),
        ("ModelParseException at line 12", "pom_parse_error"),
        ("could not resolve dependencies", "dependency_resolution_error"),
        ("DependencyResolutionException for ...", "dependency_resolution_error"),
        ("Unsupported class file major version 61", "class_version_error"),
        ("invalid target release: 17", "class_version_error"),
        ("compilation failure: cannot find symbol", "compile_error"),
        ("There are test failures", "test_failure"),
        ("Tests run: 5, Failures: 1", "test_failure"),
        ("git_apply: patch does not apply", "patch_apply_error"),
        ("BUILD FAILURE for unknown reason", "build_failure"),
        ("", "build_failure"),
    ],
)
def test_classify_maven_failure_taxonomy(text: str, expected: str) -> None:
    assert classify_maven_failure(text) == expected


def test_feedback_digest_keeps_error_lines_and_drops_noise() -> None:
    log = "\n".join(
        [
            "[INFO] downloading some.jar",
            "[INFO] downloaded some.jar",
            "[ERROR] COMPILATION ERROR :",
            "[ERROR] cannot find symbol",
            "Caused by: java.lang.NullPointerException",
            "    at com.example.A.foo(A.java:12)",
            "Tests run: 3, Failures: 1, Errors: 0",
            "BUILD FAILURE",
        ]
    )
    digest = feedback_digest(log, max_chars=400)
    assert "[ERROR]" in digest
    assert "Caused by" in digest
    assert "Tests run:" in digest
    assert "downloading some.jar" not in digest


def test_parse_class_major_versions_extracts_all_majors() -> None:
    text = "major version: 52\nfoo bar\nmajor version: 61\nmajor version: 61\n"
    assert parse_class_major_versions(text) == {52, 61}


def test_parse_class_major_versions_empty() -> None:
    assert parse_class_major_versions("") == set()


def test_required_test_count_handles_missing_and_invalid() -> None:
    assert required_test_count({}) is None
    assert required_test_count({"num_test_cases": "12"}) == 12
    assert required_test_count({"num_test_cases": -3}) is None
    assert required_test_count({"num_test_cases": "abc"}) is None


def test_surefire_test_count_sums_xml_reports(tmp_path: Path) -> None:
    reports = tmp_path / "target" / "surefire-reports"
    reports.mkdir(parents=True)
    (reports / "TEST-foo.xml").write_text(
        '<?xml version="1.0"?><testsuite tests="3" />', encoding="utf-8"
    )
    (reports / "TEST-bar.xml").write_text(
        '<?xml version="1.0"?><testsuite tests="2" />', encoding="utf-8"
    )
    assert surefire_test_count(tmp_path) == 5


def test_surefire_test_count_returns_none_when_absent(tmp_path: Path) -> None:
    assert surefire_test_count(tmp_path) is None
