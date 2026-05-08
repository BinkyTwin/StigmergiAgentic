"""Controlled V12 tool execution.

Only ``edit_file_guarded`` and ``apply_patch`` are allowed to mutate a
workspace. All ``suggest_*`` tools return structured proposals only.
"""

from __future__ import annotations

import re
import shlex
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

from adapters_v10.migrationbench._runtime import run_command
from adapters_v10.migrationbench.context import MigrationContext
from adapters_v10.migrationbench.maven import run_maven as run_maven_command
from adapters_v10.migrationbench.schemas import TypedEditSet
from core_v10.operators import validate_edit_set_against_workspace

from core_v12.tools.registry import ToolExecutionContext, ToolRegistry
from core_v12.tools.schema import ToolCall, ToolProposal, ToolResult, ToolSpec


class ToolExecutor:
    """Execute LLM-selected tool calls through a registry."""

    def __init__(self, registry: ToolRegistry) -> None:
        self.registry = registry

    def execute(self, call: ToolCall, context: ToolExecutionContext) -> ToolResult:
        """Execute a tool call and convert unexpected failures to ToolResult."""

        try:
            tool = self.registry.get(call.tool_name)
        except KeyError as exc:
            return ToolResult.rejected(
                tool_name=call.tool_name,
                summary="unknown tool",
                errors=[str(exc)],
            )
        try:
            return _enforce_tool_contract(tool.spec, tool.execute(context, call))
        except Exception as exc:  # noqa: BLE001
            return ToolResult.failed(
                tool_name=call.tool_name,
                summary=f"tool raised {type(exc).__name__}",
                errors=[str(exc)],
            )


def build_default_tool_registry() -> ToolRegistry:
    """Return the V12 default tool set shared by S2 and V12."""

    registry = ToolRegistry()
    _register(
        registry,
        "read_file",
        "Read one repository-relative file from the active workspace.",
        _read_file_tool,
        {"path": "repository-relative path", "max_bytes": "optional int"},
        tags=("io", "inspect"),
    )
    _register(
        registry,
        "search_repo",
        "Search text across repository files and return matching snippets.",
        _search_repo_tool,
        {"query": "literal text or regex", "max_results": "optional int"},
        tags=("io", "inspect"),
    )
    _register(
        registry,
        "inspect_pom",
        "Inspect Maven POM properties, dependencies, and plugins.",
        _inspect_pom_tool,
        {"path": "optional pom path, default pom.xml"},
        tags=("maven", "inspect"),
    )
    _register(
        registry,
        "edit_file_guarded",
        "Apply a typed edit set only after workspace-backed guard validation.",
        _edit_file_guarded_tool,
        {"edits": "TypedEditSet-style edits", "rationale": "why this edit is needed"},
        mutates_workspace=True,
        creates_candidate=True,
        tags=("edit", "guarded"),
    )
    _register(
        registry,
        "apply_patch",
        "Apply a unified diff after git-apply validation.",
        _apply_patch_tool,
        {"patch": "unified diff"},
        mutates_workspace=True,
        creates_candidate=True,
        tags=("edit", "guarded"),
    )
    _register(
        registry,
        "run_maven",
        "Run a Maven command in the repository workspace.",
        _run_maven_tool,
        {"command": "optional Maven command, default mvn clean verify"},
        tags=("maven", "verify"),
    )
    _register(
        registry,
        "run_tests",
        "Run Maven tests in the repository workspace.",
        _run_tests_tool,
        {"command": "optional Maven test command, default mvn test"},
        tags=("maven", "verify"),
    )
    _register(
        registry,
        "run_official_eval",
        "Run the official evaluator command when the workspace provides one.",
        _run_official_eval_tool,
        {"command": "optional command if allowed by workspace metadata"},
        tags=("official", "verify"),
    )
    for name, description, handler in (
        (
            "suggest_maven_compiler_config",
            "Suggest target-aware Maven compiler configuration changes without applying them.",
            _suggest_maven_compiler_config_tool,
        ),
        (
            "suggest_lombok_upgrade",
            "Suggest a target-aware Lombok upgrade when Lombok is already present.",
            _suggest_lombok_upgrade_tool,
        ),
        (
            "suggest_surefire_upgrade",
            "Suggest a target-aware Surefire configuration or upgrade without applying it.",
            _suggest_surefire_upgrade_tool,
        ),
        (
            "suggest_javafx_dependencies",
            "Suggest JavaFX dependencies for target Java versions where JavaFX is external.",
            _suggest_javafx_dependencies_tool,
        ),
        (
            "suggest_base64_rewrite",
            "Suggest exact sun.misc Base64 rewrites without changing source files.",
            _suggest_base64_rewrite_tool,
        ),
    ):
        _register(
            registry,
            name,
            description,
            handler,
            {"feedback": "optional verifier feedback text"},
            proposal_only=True,
            tags=("suggest", "proposal_only"),
        )
    return registry


def build_sd_feedback_readonly_tool_registry() -> ToolRegistry:
    """Return the V12.4 SD-Feedback perception toolbox.

    These tools are shared by the SD-Feedback+tools control and the
    stigmergic treatment arm. They may inspect files, logs and Maven metadata,
    but they must not create a candidate or mutate the source workspace. Patch
    creation for V12.4 happens through the explicit LLM patch-proposal channel,
    not through deterministic repair operators.
    """

    registry = ToolRegistry()
    _register(
        registry,
        "read_file",
        "Read one repository-relative source file from the active workspace.",
        _read_file_tool,
        {"path": "repository-relative path", "max_bytes": "optional int"},
        tags=("io", "inspect", "sd_feedback_readonly"),
    )
    _register(
        registry,
        "search_repo",
        "Search text across repository files and return matching snippets.",
        _search_repo_tool,
        {"query": "literal text or regex", "max_results": "optional int"},
        tags=("io", "inspect", "sd_feedback_readonly"),
    )
    _register(
        registry,
        "inspect_pom",
        "Inspect Maven POM properties, dependencies, and plugins.",
        _inspect_pom_tool,
        {"path": "optional pom path, default pom.xml"},
        tags=("maven", "inspect", "sd_feedback_readonly"),
    )
    _register(
        registry,
        "read_build_log",
        "Read an allowlisted build or official-eval log from campaign artifacts.",
        _read_build_log_tool,
        {"path": "artifact-log key or path", "max_bytes": "optional int"},
        tags=("logs", "inspect", "sd_feedback_readonly"),
    )
    _register(
        registry,
        "parse_maven_errors",
        "Extract Maven/compiler/test error hints from a supplied or artifact log.",
        _parse_maven_errors_tool,
        {"log_text": "optional log text", "path": "optional artifact-log path"},
        tags=("logs", "maven", "inspect", "sd_feedback_readonly"),
    )
    _register(
        registry,
        "inspect_effective_pom",
        "Run Maven effective-pom inspection without applying source repairs.",
        _inspect_effective_pom_tool,
        {"command": "optional exact Maven effective-pom command"},
        tags=("maven", "inspect", "sd_feedback_readonly"),
    )
    _register(
        registry,
        "dependency_tree",
        "Run Maven dependency:tree inspection without applying source repairs.",
        _dependency_tree_tool,
        {"command": "optional exact Maven dependency:tree command"},
        tags=("maven", "inspect", "sd_feedback_readonly"),
    )
    _register(
        registry,
        "lookup_dependency_version",
        "Return local target-aware dependency/plugin version hints without editing.",
        _lookup_dependency_version_tool,
        {"artifact": "artifact or plugin id to look up"},
        tags=("maven", "inspect", "sd_feedback_readonly"),
    )
    return registry


def _register(
    registry: ToolRegistry,
    name: str,
    description: str,
    handler: Any,
    input_schema: dict[str, Any],
    *,
    mutates_workspace: bool = False,
    creates_candidate: bool = False,
    proposal_only: bool = False,
    tags: tuple[str, ...] = (),
) -> None:
    registry.register(
        ToolSpec(
            name=name,
            description=description,
            input_schema=input_schema,
            mutates_workspace=mutates_workspace,
            creates_candidate=creates_candidate,
            proposal_only=proposal_only,
            tags=tags,
        ),
        handler,
    )


def _read_file_tool(context: ToolExecutionContext, call: ToolCall) -> ToolResult:
    path = _safe_relative_path(str(call.arguments.get("path") or ""))
    if path is None:
        return ToolResult.rejected(
            tool_name=call.tool_name, summary="unsafe or empty path"
        )
    max_bytes = int(call.arguments.get("max_bytes") or 120_000)
    text = _read_workspace_file(context.workspace, path, max_bytes=max_bytes)
    if text is None:
        return ToolResult.rejected(
            tool_name=call.tool_name,
            summary=f"file not found: {path}",
        )
    return ToolResult.success(
        tool_name=call.tool_name,
        summary=f"read {path}",
        output={"path": path, "content": text, "bytes": len(text.encode("utf-8"))},
    )


def _search_repo_tool(context: ToolExecutionContext, call: ToolCall) -> ToolResult:
    query = str(call.arguments.get("query") or "")
    if not query:
        return ToolResult.rejected(
            tool_name=call.tool_name, summary="query cannot be empty"
        )
    max_results = int(call.arguments.get("max_results") or 20)
    repo_dir = _repo_dir(context.workspace)
    if repo_dir is None or not repo_dir.exists():
        return ToolResult.rejected(
            tool_name=call.tool_name, summary="repo directory unavailable"
        )
    results: list[dict[str, Any]] = []
    pattern = re.compile(re.escape(query), re.IGNORECASE)
    for path in _iter_text_files(repo_dir):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line_no, line in enumerate(text.splitlines(), start=1):
            if pattern.search(line):
                results.append(
                    {
                        "path": path.relative_to(repo_dir).as_posix(),
                        "line": line_no,
                        "snippet": line.strip()[:500],
                    }
                )
                break
        if len(results) >= max_results:
            break
    return ToolResult.success(
        tool_name=call.tool_name,
        summary=f"found {len(results)} matches",
        output={"query": query, "matches": results},
    )


def _inspect_pom_tool(context: ToolExecutionContext, call: ToolCall) -> ToolResult:
    path = _safe_relative_path(str(call.arguments.get("path") or "pom.xml"))
    if path is None or not path.endswith("pom.xml"):
        return ToolResult.rejected(
            tool_name=call.tool_name, summary="path must target a pom.xml"
        )
    text = _read_workspace_file(context.workspace, path, max_bytes=2_000_000)
    if text is None:
        return ToolResult.rejected(
            tool_name=call.tool_name, summary=f"POM not found: {path}"
        )
    return ToolResult.success(
        tool_name=call.tool_name,
        summary=f"inspected {path}",
        output={"path": path, **_inspect_pom_text(text)},
    )


def _edit_file_guarded_tool(
    context: ToolExecutionContext, call: ToolCall
) -> ToolResult:
    edit_set = {
        "edits": call.arguments.get("edits") or [],
        "rationale": call.arguments.get("rationale") or call.rationale,
        "expected_build_command": call.arguments.get("expected_build_command")
        or _expected_build_command(context),
    }
    guard = validate_edit_set_against_workspace(edit_set, context.workspace)
    if not guard.ok:
        return ToolResult.rejected(
            tool_name=call.tool_name,
            summary="guarded edit set rejected",
            metadata={"guard": guard.to_dict()},
        )
    applied = _apply_edit_set(context.workspace, edit_set)
    if not applied["applied"]:
        return ToolResult.failed(
            tool_name=call.tool_name,
            summary=applied["failure_reason"],
            metadata={"guard": guard.to_dict(), "apply": applied},
        )
    return ToolResult.success(
        tool_name=call.tool_name,
        summary="guarded edit set applied",
        output=applied,
        workspace_mutated=True,
        candidate_created=True,
        metadata={"guard": guard.to_dict()},
    )


def _apply_patch_tool(context: ToolExecutionContext, call: ToolCall) -> ToolResult:
    patch = str(call.arguments.get("patch") or "")
    if not patch.strip():
        return ToolResult.rejected(
            tool_name=call.tool_name, summary="patch cannot be empty"
        )
    repo_dir = _repo_dir(context.workspace)
    if repo_dir is None:
        return ToolResult.rejected(
            tool_name=call.tool_name, summary="repo directory unavailable"
        )
    check = subprocess.run(
        ["git", "apply", "--check", "-"],
        cwd=repo_dir,
        input=patch,
        capture_output=True,
        text=True,
        check=False,
    )
    if check.returncode != 0:
        return ToolResult.rejected(
            tool_name=call.tool_name,
            summary="git apply check failed",
            errors=[(check.stderr or check.stdout)[-2000:]],
        )
    applied = subprocess.run(
        ["git", "apply", "-"],
        cwd=repo_dir,
        input=patch,
        capture_output=True,
        text=True,
        check=False,
    )
    if applied.returncode != 0:
        return ToolResult.failed(
            tool_name=call.tool_name,
            summary="git apply failed",
            errors=[(applied.stderr or applied.stdout)[-2000:]],
        )
    return ToolResult.success(
        tool_name=call.tool_name,
        summary="patch applied",
        output={"patch_chars": len(patch)},
        workspace_mutated=True,
        candidate_created=True,
    )


def _run_maven_tool(context: ToolExecutionContext, call: ToolCall) -> ToolResult:
    command = str(call.arguments.get("command") or _expected_build_command(context))
    command_error = _maven_command_error(command)
    if command_error:
        return ToolResult.rejected(tool_name=call.tool_name, summary=command_error)
    repo_dir = _repo_dir(context.workspace)
    if repo_dir is None:
        return ToolResult.rejected(
            tool_name=call.tool_name, summary="repo directory unavailable"
        )
    result = run_maven_command(
        repo_dir, command, timeout_seconds=context.timeout_seconds
    )
    return _command_tool_result(call.tool_name, result)


def _run_tests_tool(context: ToolExecutionContext, call: ToolCall) -> ToolResult:
    command = str(call.arguments.get("command") or "mvn test")
    command_error = _maven_command_error(command)
    if command_error:
        return ToolResult.rejected(tool_name=call.tool_name, summary=command_error)
    repo_dir = _repo_dir(context.workspace)
    if repo_dir is None:
        return ToolResult.rejected(
            tool_name=call.tool_name, summary="repo directory unavailable"
        )
    result = run_maven_command(
        repo_dir, command, timeout_seconds=context.timeout_seconds
    )
    return _command_tool_result(call.tool_name, result)


def _run_official_eval_tool(
    context: ToolExecutionContext, call: ToolCall
) -> ToolResult:
    metadata = _workspace_metadata(context.workspace)
    metadata_command = str(metadata.get("official_eval_command") or "")
    requested_command = str(call.arguments.get("command") or "")
    if not metadata_command:
        return ToolResult.rejected(
            tool_name=call.tool_name,
            summary="official evaluator command unavailable",
        )
    if requested_command and requested_command != metadata_command:
        return ToolResult.rejected(
            tool_name=call.tool_name,
            summary="official evaluator command not allowed by workspace metadata",
        )
    repo_dir = _repo_dir(context.workspace)
    if repo_dir is None:
        return ToolResult.rejected(
            tool_name=call.tool_name, summary="repo directory unavailable"
        )
    result = run_command(
        ["bash", "-lc", metadata_command],
        cwd=repo_dir,
        timeout_seconds=context.timeout_seconds,
    )
    return _command_tool_result(call.tool_name, result)


def _read_build_log_tool(context: ToolExecutionContext, call: ToolCall) -> ToolResult:
    max_bytes = int(call.arguments.get("max_bytes") or 120_000)
    resolved = _resolve_artifact_log_path(
        context,
        str(call.arguments.get("path") or call.arguments.get("log_key") or ""),
    )
    if resolved is None:
        return ToolResult.rejected(
            tool_name=call.tool_name,
            summary="artifact log unavailable or path not allowlisted",
        )
    try:
        text = resolved.read_bytes()[-max_bytes:].decode("utf-8", errors="replace")
    except OSError as exc:
        return ToolResult.failed(
            tool_name=call.tool_name,
            summary="artifact log could not be read",
            errors=[str(exc)],
        )
    return ToolResult.success(
        tool_name=call.tool_name,
        summary=f"read artifact log {resolved.name}",
        output={"path": str(resolved), "content": text, "bytes": len(text.encode())},
    )


def _parse_maven_errors_tool(
    context: ToolExecutionContext, call: ToolCall
) -> ToolResult:
    text = str(call.arguments.get("log_text") or "")
    if not text:
        resolved = _resolve_artifact_log_path(
            context,
            str(call.arguments.get("path") or call.arguments.get("log_key") or ""),
        )
        if resolved is not None:
            try:
                text = resolved.read_bytes()[-160_000:].decode(
                    "utf-8", errors="replace"
                )
            except OSError:
                text = ""
    if not text:
        return ToolResult.rejected(
            tool_name=call.tool_name,
            summary="no Maven log text available",
        )
    errors = _extract_maven_error_hints(text)
    return ToolResult.success(
        tool_name=call.tool_name,
        summary=f"parsed {len(errors)} Maven error hints",
        output={"errors": errors, "log_excerpt": text[-4000:]},
    )


def _inspect_effective_pom_tool(
    context: ToolExecutionContext, call: ToolCall
) -> ToolResult:
    command = str(
        call.arguments.get("command")
        or "mvn help:effective-pom -DskipTests -DskipITs -q"
    )
    command_error = _maven_command_error(command)
    if command_error:
        return ToolResult.rejected(tool_name=call.tool_name, summary=command_error)
    if "help:effective-pom" not in command:
        return ToolResult.rejected(
            tool_name=call.tool_name,
            summary="only Maven help:effective-pom inspection is allowed",
        )
    repo_dir = _repo_dir(context.workspace)
    if repo_dir is None:
        return ToolResult.rejected(
            tool_name=call.tool_name, summary="repo directory unavailable"
        )
    result = run_maven_command(
        repo_dir, command, timeout_seconds=context.timeout_seconds
    )
    return _command_tool_result(call.tool_name, result)


def _dependency_tree_tool(context: ToolExecutionContext, call: ToolCall) -> ToolResult:
    command = str(
        call.arguments.get("command")
        or "mvn dependency:tree -DskipTests -DskipITs -q"
    )
    command_error = _maven_command_error(command)
    if command_error:
        return ToolResult.rejected(tool_name=call.tool_name, summary=command_error)
    if "dependency:tree" not in command:
        return ToolResult.rejected(
            tool_name=call.tool_name,
            summary="only Maven dependency:tree inspection is allowed",
        )
    repo_dir = _repo_dir(context.workspace)
    if repo_dir is None:
        return ToolResult.rejected(
            tool_name=call.tool_name, summary="repo directory unavailable"
        )
    result = run_maven_command(
        repo_dir, command, timeout_seconds=context.timeout_seconds
    )
    return _command_tool_result(call.tool_name, result)


def _lookup_dependency_version_tool(
    context: ToolExecutionContext, call: ToolCall
) -> ToolResult:
    artifact = str(call.arguments.get("artifact") or "").strip().lower()
    if not artifact:
        return ToolResult.rejected(
            tool_name=call.tool_name, summary="artifact cannot be empty"
        )
    ctx = _migration_context(context)
    compatibility = ctx.compatibility if ctx is not None else None
    hints: dict[str, Any] = {}
    if "lombok" in artifact and compatibility is not None:
        hints = {
            "artifact": "org.projectlombok:lombok",
            "minimum_version": compatibility.lombok_min,
        }
    elif "surefire" in artifact and compatibility is not None:
        hints = {
            "artifact": "org.apache.maven.plugins:maven-surefire-plugin",
            "minimum_version": compatibility.surefire_min,
        }
    elif "compiler" in artifact and compatibility is not None:
        hints = {
            "artifact": "org.apache.maven.plugins:maven-compiler-plugin",
            "minimum_version": compatibility.compiler_plugin_min,
        }
    elif "javafx" in artifact and compatibility is not None:
        hints = {
            "artifact": "org.openjfx:javafx-controls",
            "suggested_version": compatibility.javafx_version,
        }
    if not hints:
        hints = {
            "artifact": artifact,
            "status": "no local compatibility hint",
            "note": "Use repository evidence or external documentation before editing.",
        }
    return ToolResult.success(
        tool_name=call.tool_name,
        summary="returned local dependency hint",
        output={
            "query": artifact,
            "hint": hints,
            "target_java": ctx.target_java if ctx is not None else None,
        },
    )


def _suggest_maven_compiler_config_tool(
    context: ToolExecutionContext, call: ToolCall
) -> ToolResult:
    ctx = _migration_context(context)
    target = ctx.target_java if ctx else call.arguments.get("target_java")
    if not target:
        return ToolResult.rejected(
            tool_name=call.tool_name, summary="target Java unavailable"
        )
    proposal = ToolProposal(
        proposal_id="proposal_maven_compiler_config",
        kind="maven_compiler_config",
        title=f"Set Maven compiler release to target Java {target}",
        rationale="The agent can choose to edit pom.xml so Maven emits target-compatible class files.",
        suggested_edits=[
            {
                "type": "replace_text_or_insert",
                "path": "pom.xml",
                "target_java": int(target),
                "hint": "Prefer <maven.compiler.release> or maven-compiler-plugin <release>.",
            }
        ],
        confidence=0.7,
        metadata={"target_java": int(target)},
    )
    return _proposal_result(call.tool_name, proposal)


def _suggest_lombok_upgrade_tool(
    context: ToolExecutionContext, call: ToolCall
) -> ToolResult:
    ctx = _migration_context(context)
    target = ctx.target_java if ctx else call.arguments.get("target_java")
    if not target:
        return ToolResult.rejected(
            tool_name=call.tool_name, summary="target Java unavailable"
        )
    target = int(target)
    lombok_min = ctx.compatibility.lombok_min if ctx else "target-compatible"
    proposal = ToolProposal(
        proposal_id="proposal_lombok_upgrade",
        kind="lombok_upgrade",
        title="Upgrade existing Lombok for the target JDK",
        rationale="Use only when Lombok is already present and verifier feedback mentions javac internals, delombok, or IllegalAccessError.",
        suggested_edits=[
            {
                "type": "replace_text_or_insert",
                "path": "pom.xml",
                "groupId": "org.projectlombok",
                "artifactId": "lombok",
                "minimum_version": lombok_min,
            }
        ],
        confidence=0.6,
        metadata={"target_java": target},
    )
    return _proposal_result(call.tool_name, proposal)


def _suggest_surefire_upgrade_tool(
    context: ToolExecutionContext, call: ToolCall
) -> ToolResult:
    ctx = _migration_context(context)
    target = ctx.target_java if ctx else call.arguments.get("target_java")
    if not target:
        return ToolResult.rejected(
            tool_name=call.tool_name, summary="target Java unavailable"
        )
    surefire_min = ctx.compatibility.surefire_min if ctx else "target-compatible"
    proposal = ToolProposal(
        proposal_id="proposal_surefire_upgrade",
        kind="surefire_upgrade",
        title="Ensure target-compatible Surefire test reporting",
        rationale="Use for official #tests=-2 or test-summary parsing failures without modifying tests.",
        suggested_edits=[
            {
                "type": "replace_text_or_insert",
                "path": "pom.xml",
                "artifactId": "maven-surefire-plugin",
                "minimum_version": surefire_min,
            }
        ],
        confidence=0.65,
        metadata={"target_java": int(target), "surefire_min": surefire_min},
    )
    return _proposal_result(call.tool_name, proposal)


def _suggest_javafx_dependencies_tool(
    context: ToolExecutionContext, call: ToolCall
) -> ToolResult:
    ctx = _migration_context(context)
    target = ctx.target_java if ctx else call.arguments.get("target_java")
    if not target:
        return ToolResult.rejected(
            tool_name=call.tool_name, summary="target Java unavailable"
        )
    target = int(target)
    if target < 11:
        return ToolResult.rejected(
            tool_name=call.tool_name, summary="JavaFX is bundled before Java 11"
        )
    javafx_version = ctx.compatibility.javafx_version if ctx else f"{target}.0.2"
    proposal = ToolProposal(
        proposal_id="proposal_javafx_dependencies",
        kind="javafx_dependencies",
        title="Add OpenJFX dependencies for target Java",
        rationale="JavaFX is external for modern target Java versions; the agent must inspect imports before editing.",
        suggested_edits=[
            {
                "type": "dependency_suggestion",
                "path": "pom.xml",
                "groupId": "org.openjfx",
                "artifactId": "javafx-controls",
                "version": javafx_version,
            }
        ],
        confidence=0.5,
        metadata={"target_java": target, "javafx_version": javafx_version},
    )
    return _proposal_result(call.tool_name, proposal)


def _suggest_base64_rewrite_tool(
    context: ToolExecutionContext, call: ToolCall
) -> ToolResult:
    proposal = ToolProposal(
        proposal_id="proposal_base64_rewrite",
        kind="base64_rewrite",
        title="Rewrite simple sun.misc Base64 usages to java.util.Base64",
        rationale="Use only after read_file/search_repo confirms exact BASE64Encoder/BASE64Decoder patterns.",
        suggested_edits=[
            {
                "type": "source_rewrite_suggestion",
                "imports": ["sun.misc.BASE64Encoder", "sun.misc.BASE64Decoder"],
                "replacement_import": "java.util.Base64",
                "requires_exact_pattern": True,
            }
        ],
        confidence=0.55,
    )
    return _proposal_result(call.tool_name, proposal)


def _proposal_result(tool_name: str, proposal: ToolProposal) -> ToolResult:
    return ToolResult.success(
        tool_name=tool_name,
        summary="proposal returned; no workspace mutation",
        proposal=proposal,
        output={"proposal": proposal.model_dump(mode="json")},
        workspace_mutated=False,
        candidate_created=False,
        metadata={"proposal_only": True},
    )


def _command_tool_result(tool_name: str, result: Any) -> ToolResult:
    output = {
        "command": list(result.command),
        "returncode": int(result.returncode),
        "stdout_tail": str(result.stdout or "")[-4000:],
        "stderr_tail": str(result.stderr or "")[-4000:],
        "runtime_seconds": float(result.runtime_seconds),
    }
    status = "success" if result.ok else "failed"
    return ToolResult(
        tool_name=tool_name,
        status=status,
        summary="command completed" if result.ok else "command failed",
        output=output,
    )


def _enforce_tool_contract(spec: ToolSpec, result: ToolResult) -> ToolResult:
    violations: list[str] = []
    if result.workspace_mutated and not spec.mutates_workspace:
        violations.append("tool reported workspace mutation but spec is read-only")
    if result.candidate_created and not spec.creates_candidate:
        violations.append("tool reported candidate creation but spec does not allow it")
    if spec.proposal_only:
        if result.workspace_mutated:
            violations.append("proposal-only tool reported workspace mutation")
        if result.candidate_created:
            violations.append("proposal-only tool reported candidate creation")
        if result.status == "success" and result.proposal is None:
            violations.append("proposal-only tool succeeded without a ToolProposal")
    if not violations:
        return result
    return ToolResult.failed(
        tool_name=spec.name,
        summary="tool contract violation",
        errors=violations,
        metadata={"original_result": result.model_dump(mode="json")},
    )


def _maven_command_error(command: str) -> str | None:
    stripped = command.strip()
    if not stripped:
        return "Maven command cannot be empty"
    if re.search(r"[;&|<>`$\n\r]", stripped):
        return "shell control operators are not allowed in Maven commands"
    try:
        parts = shlex.split(stripped)
    except ValueError:
        return "Maven command could not be parsed safely"
    if not parts or parts[0] != "mvn":
        return "only Maven commands are allowed"
    return None


def _inspect_pom_text(text: str) -> dict[str, Any]:
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return {"parse_ok": False, "properties": {}, "dependencies": [], "plugins": []}
    properties: dict[str, str] = {}
    dependencies: list[dict[str, str]] = []
    plugins: list[dict[str, str]] = []
    for child in root.iter():
        tag = _local_name(child.tag)
        if tag == "properties":
            for prop in list(child):
                properties[_local_name(prop.tag)] = (prop.text or "").strip()
        if tag == "dependency":
            dependencies.append(_maven_block(child))
        if tag == "plugin":
            plugins.append(_maven_block(child))
    return {
        "parse_ok": True,
        "properties": properties,
        "dependencies": dependencies,
        "plugins": plugins,
    }


def _maven_block(node: ET.Element) -> dict[str, str]:
    result: dict[str, str] = {}
    for child in list(node):
        name = _local_name(child.tag)
        if name in {"groupId", "artifactId", "version", "scope"}:
            result[name] = (child.text or "").strip()
    return result


def _local_name(tag: str) -> str:
    return str(tag).split("}", 1)[-1]


def _apply_edit_set(workspace: Any, edit_set: dict[str, Any]) -> dict[str, Any]:
    if hasattr(workspace, "apply_typed_edits"):
        edits = TypedEditSet.model_validate(edit_set)
        result = workspace.apply_typed_edits(edits)
        return {
            "applied": bool(result.applied),
            "failure_reason": result.failure_reason,
            "files_modified": list(result.files_modified),
            "replacements": dict(result.replacements),
        }
    files_modified: list[str] = []
    replacements: dict[str, int] = {}
    for edit in edit_set.get("edits") or []:
        path = str(edit["path"])
        if edit["type"] == "write_file":
            _write_workspace_file(workspace, path, str(edit.get("content") or ""))
            files_modified.append(path)
            continue
        old = str(edit.get("old") or "")
        new = str(edit.get("new") or "")
        current = _read_workspace_file(workspace, path, max_bytes=20_000_000)
        if current is None:
            return {"applied": False, "failure_reason": f"path_not_found:{path}"}
        replacements[path] = current.count(old)
        _write_workspace_file(workspace, path, current.replace(old, new))
        files_modified.append(path)
    return {
        "applied": True,
        "failure_reason": "ok",
        "files_modified": sorted(set(files_modified)),
        "replacements": replacements,
    }


def _safe_relative_path(raw_path: str) -> str | None:
    path = raw_path.strip().replace("\\", "/")
    if not path:
        return None
    posix = PurePosixPath(path)
    if posix.is_absolute() or any(part in {"", ".", ".."} for part in posix.parts):
        return None
    return str(posix)


def _repo_dir(workspace: Any) -> Path | None:
    metadata = _workspace_metadata(workspace)
    repo_dir = metadata.get("repo_dir")
    if repo_dir:
        return Path(str(repo_dir))
    root = getattr(workspace, "root", None)
    if root is not None:
        root_path = Path(root)
        if (root_path / "repo").exists():
            return root_path / "repo"
        return root_path
    repo = getattr(workspace, "repo_dir", None)
    return Path(repo) if repo is not None else None


def _workspace_metadata(workspace: Any) -> dict[str, Any]:
    metadata = getattr(workspace, "metadata", None)
    return dict(metadata) if isinstance(metadata, dict) else {}


def _read_workspace_file(
    workspace: Any, rel_path: str, *, max_bytes: int
) -> str | None:
    if hasattr(workspace, "read_file"):
        try:
            return str(workspace.read_file(rel_path, max_bytes=max_bytes))
        except Exception:  # noqa: BLE001
            return None
    repo_dir = _repo_dir(workspace)
    if repo_dir is None:
        return None
    path = (repo_dir / rel_path).resolve()
    try:
        path.relative_to(repo_dir.resolve())
    except ValueError:
        return None
    if not path.is_file():
        return None
    return path.read_bytes()[:max_bytes].decode("utf-8", errors="replace")


def _write_workspace_file(workspace: Any, rel_path: str, content: str) -> None:
    if hasattr(workspace, "write_file"):
        workspace.write_file(rel_path, content)
        return
    repo_dir = _repo_dir(workspace)
    if repo_dir is None:
        raise ValueError("workspace has no writable repo directory")
    path = (repo_dir / rel_path).resolve()
    path.relative_to(repo_dir.resolve())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _iter_text_files(repo_dir: Path) -> Iterable[Path]:
    skip = {".git", "target", "build", "out", ".gradle", ".idea", "__pycache__"}
    for path in repo_dir.rglob("*"):
        if any(part in skip for part in path.parts):
            continue
        if path.is_file() and path.stat().st_size <= 1_000_000:
            yield path


def _resolve_artifact_log_path(
    context: ToolExecutionContext,
    raw_path: str,
) -> Path | None:
    metadata = {**_workspace_metadata(context.workspace), **dict(context.metadata or {})}
    artifact_logs = metadata.get("artifact_logs") or {}
    if raw_path and isinstance(artifact_logs, dict) and raw_path in artifact_logs:
        raw_path = str(artifact_logs[raw_path])
    candidate_paths: list[Path] = []
    artifacts_dir = metadata.get("artifacts_dir")
    if raw_path:
        requested = Path(str(raw_path))
        if requested.is_absolute():
            candidate_paths.append(requested)
        else:
            safe = _safe_relative_path(str(raw_path))
            if safe and artifacts_dir:
                candidate_paths.append(Path(str(artifacts_dir)) / safe)
    else:
        for key in (
            "last_build_log",
            "build_log",
            "validation_log",
            "official_eval_log",
            "maven_log",
        ):
            if metadata.get(key):
                candidate_paths.append(Path(str(metadata[key])))
        if artifacts_dir:
            for name in (
                "build.log",
                "validation.log",
                "maven.log",
                "official_eval.log",
            ):
                candidate_paths.append(Path(str(artifacts_dir)) / name)

    allowed_roots: list[Path] = []
    if artifacts_dir:
        allowed_roots.append(Path(str(artifacts_dir)).resolve())
    repo_dir = _repo_dir(context.workspace)
    if repo_dir is not None:
        allowed_roots.append(repo_dir.resolve())
    for candidate in candidate_paths:
        path = candidate.resolve()
        if not path.is_file():
            continue
        if _path_is_under_any(path, allowed_roots):
            return path
    return None


def _path_is_under_any(path: Path, roots: Iterable[Path]) -> bool:
    for root in roots:
        try:
            path.relative_to(root)
            return True
        except ValueError:
            continue
    return False


def _extract_maven_error_hints(text: str) -> list[dict[str, Any]]:
    hints: list[dict[str, Any]] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        lower = stripped.lower()
        if not stripped:
            continue
        family: str | None = None
        if "unsupported class file major version" in lower:
            family = "bytecode_reader_incompatibility"
        elif "cannot find symbol" in lower:
            family = "cannot_find_symbol"
        elif "package " in lower and " does not exist" in lower:
            family = "missing_package"
        elif "failed to execute goal" in lower:
            family = "maven_goal_failure"
        elif "dependencyresolutionexception" in lower or "could not resolve" in lower:
            family = "dependency_resolution"
        elif "[error]" in lower or "compilation failure" in lower:
            family = "generic_maven_error"
        if family is None:
            continue
        hints.append(
            {
                "line": line_no,
                "family": family,
                "snippet": stripped[:500],
            }
        )
        if len(hints) >= 40:
            break
    return hints


def _migration_context(context: ToolExecutionContext) -> MigrationContext | None:
    if isinstance(context.migration_context, MigrationContext):
        return context.migration_context
    metadata_ctx = _workspace_metadata(context.workspace).get("migration_context")
    if isinstance(metadata_ctx, dict):
        raw = dict(metadata_ctx)
        if "target_java" in raw and "target_version" not in raw:
            raw["target_version"] = raw["target_java"]
        if "source_java" in raw and "source_version" not in raw:
            raw["source_version"] = raw["source_java"]
        try:
            return MigrationContext(
                **{
                    key: value
                    for key, value in raw.items()
                    if key
                    in {
                        "source_language",
                        "source_version",
                        "target_language",
                        "target_version",
                        "target_class_major",
                        "build_system",
                        "migration_mode",
                        "dependency_policy",
                        "framework_hints",
                        "expected_build_command",
                    }
                }
            )
        except Exception:  # noqa: BLE001
            return None
    return None


def _expected_build_command(context: ToolExecutionContext) -> str:
    ctx = _migration_context(context)
    if ctx is not None:
        return ctx.expected_build_command
    return str(
        _workspace_metadata(context.workspace).get("expected_build_command")
        or "mvn clean verify"
    )


__all__ = [
    "ToolExecutor",
    "build_default_tool_registry",
    "build_sd_feedback_readonly_tool_registry",
]
