"""MigrationBench domain tools for V6 static stigmergic runs."""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from core.marker import Marker, utc_now_iso
from core.tool_registry import ActionResult, RepairRequest, Tool, ValidationResult

from .evaluator import MigrationBenchEvaluator, build_strict_contract
from .schemas import TypedEdit, TypedEditSet
from .workspace import MigrationBenchWorkspace


SYSTEM_MIGRATION_EDIT = """You are migrating a Java Maven repository from Java 8 to Java 17.
Return strict JSON only. Never return a unified diff.
Use typed edits with repository-relative paths:
{"edits":[{"type":"replace_text","path":"pom.xml","old":"...","new":"...","expected_replacements":1}]}
Prefer minimal migration: preserve behavior and tests, change only what is necessary."""

SYSTEM_REPAIR_EDIT = """You are repairing a failed Java 8 to Java 17 migration patch.
Return strict JSON only using typed edits. Never return a unified diff.
Use the build/test feedback to make the smallest corrective edit.
Do not repeat edits that already failed unless the feedback shows an exact mismatch.
If previous_attempts are provided, avoid repeating a file/edit pattern that produced the same taxonomy."""


def deterministic_java17_pom_edits(workspace: MigrationBenchWorkspace) -> TypedEditSet:
    """Return conservative typed edits for common Maven Java version declarations."""
    edits: list[TypedEdit] = []
    for rel_path in [target for target in workspace.list_targets() if target.endswith("pom.xml")]:
        try:
            text = workspace.read_file(rel_path, max_bytes=2_000_000)
        except Exception:  # noqa: BLE001
            continue
        replacements = {
            "<maven.compiler.source>1.8</maven.compiler.source>": "<maven.compiler.source>17</maven.compiler.source>",
            "<maven.compiler.target>1.8</maven.compiler.target>": "<maven.compiler.target>17</maven.compiler.target>",
            "<maven.compiler.release>8</maven.compiler.release>": "<maven.compiler.release>17</maven.compiler.release>",
            "<source>1.8</source>": "<source>17</source>",
            "<target>1.8</target>": "<target>17</target>",
            "<release>8</release>": "<release>17</release>",
            "<java.version>1.8</java.version>": "<java.version>17</java.version>",
            "<java.version>8</java.version>": "<java.version>17</java.version>",
        }
        for old, new in replacements.items():
            count = text.count(old)
            if count:
                edits.append(
                    TypedEdit(
                        type="replace_text",
                        path=rel_path,
                        old=old,
                        new=new,
                        expected_replacements=count,
                        allow_multiple=True,
                    )
                )
    return TypedEditSet(
        edits=edits,
        rationale="Conservative Maven Java 17 source/target/release updates.",
    )


def _normalize_typed_edit_payload(raw: Any) -> Any:
    """Accept common LLM edit variants and coerce them into `TypedEditSet` shape."""
    if isinstance(raw, list):
        raw = {"edits": raw}
    if not isinstance(raw, dict):
        return raw

    payload = dict(raw)
    if "edits" not in payload and any(key in payload for key in ("path", "file", "content", "old", "new", "replace")):
        raw_edits = [payload]
        payload = {
            "edits": raw_edits,
            "rationale": raw.get("rationale", ""),
            "expected_build_command": raw.get("expected_build_command", "mvn clean verify"),
        }
    else:
        raw_edits = payload.get("edits", [])
    if isinstance(raw_edits, dict):
        raw_edits = [raw_edits]
    if not isinstance(raw_edits, list):
        raw_edits = []

    normalized: list[dict[str, Any]] = []
    for item in raw_edits:
        if not isinstance(item, dict):
            continue
        edit = dict(item)
        if "path" not in edit and "file" in edit:
            edit["path"] = edit.pop("file")
        if "type" not in edit:
            if "content" in edit and "old" not in edit and "new" not in edit:
                edit["type"] = "write_file"
            elif "replace" in edit or {"old", "new"}.issubset(edit):
                edit["type"] = "replace_text"
        if edit.get("type") == "replace_text" and "replace" in edit:
            replace = edit.pop("replace")
            if isinstance(replace, dict):
                edit.setdefault("old", replace.get("old"))
                edit.setdefault("new", replace.get("new"))
            elif isinstance(replace, str):
                edit.setdefault("old", replace)
        if edit.get("type") == "write_file":
            edit.setdefault("content", edit.get("new"))
        edit.setdefault("expected_replacements", 1)
        normalized.append(edit)

    payload["edits"] = normalized
    payload.setdefault("rationale", "")
    payload.setdefault("expected_build_command", "mvn clean verify")
    return payload


def parse_typed_edit_set(raw: Any) -> TypedEditSet:
    """Coerce LLM output into the shared typed edit schema."""
    if isinstance(raw, TypedEditSet):
        return raw
    if hasattr(raw, "model_dump"):
        return TypedEditSet.model_validate(_normalize_typed_edit_payload(raw.model_dump()))
    if isinstance(raw, dict):
        return TypedEditSet.model_validate(_normalize_typed_edit_payload(raw))
    text = str(raw or "").strip()
    if not text:
        return TypedEditSet(edits=[], rationale="empty_model_output")
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if fenced:
        text = fenced.group(1).strip()
    return TypedEditSet.model_validate(_normalize_typed_edit_payload(json.loads(text)))


def build_edit_prompt(
    *,
    workspace: MigrationBenchWorkspace,
    strategy: str,
    feedback: str = "",
) -> str:
    """Build a compact repository migration prompt."""
    summary = workspace.summarize()
    return (
        f"Strategy: {strategy}\n"
        f"Repository summary JSON:\n{json.dumps(summary, indent=2)[:180000]}\n\n"
        f"Build/test feedback:\n{feedback[:20000]}\n\n"
        "Return JSON with key `edits`. Use `write_file` only when a complete file rewrite is safer. "
        "Do not delete tests. Do not change public behavior unrelated to Java 17 migration."
    )


async def _request_typed_edits(
    *,
    llm_client: Any | None,
    workspace: MigrationBenchWorkspace,
    prompt: str,
    system: str,
    fallback: TypedEditSet,
    max_attempts: int = 2,
) -> tuple[TypedEditSet, int, float, int, str]:
    """Ask the LLM for typed edits while allowing local schema normalization/retry."""
    if llm_client is None:
        return fallback, 0, 0.0, 0, ""

    tokens = 0
    cost = 0.0
    llm_calls = 0
    llm_failure = ""
    current_prompt = prompt
    for attempt in range(max(1, int(max_attempts))):
        try:
            response = await llm_client.acall(
                prompt=current_prompt,
                system=system,
                response_schema=None,
            )
            tokens += int(response.tokens_used)
            cost += float(response.cost_usd)
            llm_calls += 1
            parsed = response.parsed if response.parsed is not None else response.content
            edits = parse_typed_edit_set(parsed)
            if attempt > 0:
                llm_failure = "recovered_after_schema_retry"
            return edits, tokens, cost, llm_calls, llm_failure
        except (ValidationError, json.JSONDecodeError, ValueError) as exc:
            llm_failure = f"{type(exc).__name__}:{exc}"
            if attempt == 0:
                current_prompt = (
                    f"{prompt}\n\nYour previous response failed schema validation:\n"
                    f"{llm_failure[:4000]}\n\n"
                    "Return STRICT JSON matching this shape only: "
                    '{"edits":[{"type":"replace_text","path":"pom.xml","old":"...","new":"...",'
                    '"expected_replacements":1}],"rationale":"..."}'
                )
                continue
            break
        except Exception as exc:  # noqa: BLE001
            llm_failure = f"{type(exc).__name__}:{exc}"
            break

    return fallback, tokens, cost, llm_calls, llm_failure


def classify_maven_failure(text: str) -> str:
    """Classify Maven/build feedback into a reusable repair taxonomy."""
    lowered = str(text or "").lower()
    if any(token in lowered for token in ["non-parseable pom", "malformed pom", "modelparseexception"]):
        return "pom_parse_error"
    if any(
        token in lowered
        for token in [
            "could not resolve dependencies",
            "failed to collect dependencies",
            "could not find artifact",
            "dependency resolution",
            "dependencyresolutionexception",
        ]
    ):
        return "dependency_resolution_error"
    if any(
        token in lowered
        for token in [
            "unsupported class file major version",
            "invalid target release",
            "release version",
            "source option",
            "target option",
        ]
    ):
        return "class_version_error"
    if any(
        token in lowered
        for token in [
            "compilation failure",
            "compilation error",
            "cannot find symbol",
            "package ",
            "does not exist",
            "maven-compiler-plugin",
        ]
    ):
        return "compile_error"
    if any(
        token in lowered
        for token in ["there are test failures", "surefire", "tests run:", "test failure"]
    ):
        return "test_failure"
    if "git_apply" in lowered or "patch does not apply" in lowered:
        return "patch_apply_error"
    return "build_failure"


def _feedback_digest(text: str, *, max_chars: int = 12000) -> str:
    """Extract Maven failure signal without drowning repairs in download progress."""
    lines = [line.rstrip() for line in str(text or "").splitlines()]
    selected: list[str] = []

    for idx, line in enumerate(lines):
        lowered = line.lower()
        if "[error]" in lowered:
            selected.extend(lines[idx : min(len(lines), idx + 30)])
        if "caused by:" in lowered:
            selected.extend(lines[idx : min(len(lines), idx + 6)])
        if "tests run:" in lowered:
            selected.append(line)
        if "build failure" in lowered:
            selected.extend(lines[idx : min(len(lines), idx + 4)])

    if lines:
        selected.append(lines[-1])
    if not selected:
        cleaned = "\n".join(lines)
        return cleaned[-max(1, int(max_chars)) :]

    compact = "\n".join(dict.fromkeys(line for line in selected if line.strip()))
    return compact[-max(1, int(max_chars)) :]


def _target_major_version(workspace: MigrationBenchWorkspace) -> int:
    return int(workspace.instance.require_compiled_java_major_version)


def _class_major_versions(workspace: MigrationBenchWorkspace) -> set[int]:
    """Return major versions for classes produced under target/classes."""
    versions: set[int] = set()
    if not workspace.repo_dir.exists():
        return versions
    class_files = [
        path
        for path in workspace.repo_dir.rglob("target/classes/**/*.class")
        if path.is_file()
    ]
    for path in class_files[:2000]:
        result = workspace.run_maven(
            f"javap -verbose {json.dumps(str(path))} | grep 'major version:'",
            timeout_seconds=30,
        )
        match = re.search(r"major version:\s*(\d+)", result.stdout + result.stderr)
        if match:
            versions.add(int(match.group(1)))
    return versions


def _surefire_test_count(workspace: MigrationBenchWorkspace) -> int | None:
    total = 0
    found = False
    for report in workspace.repo_dir.rglob("target/surefire-reports/TEST-*.xml"):
        try:
            root = ET.parse(report).getroot()
            total += int(float(root.attrib.get("tests", 0) or 0))
            found = True
        except Exception:  # noqa: BLE001
            continue
    return total if found else None


def _required_test_count(workspace: MigrationBenchWorkspace) -> int | None:
    raw = dict(workspace.instance.stats).get("num_test_cases")
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    return value if value >= 0 else None


def _relevant_edits(edits: TypedEditSet, workspace: MigrationBenchWorkspace) -> bool:
    targets = set(workspace.list_targets())
    for edit in edits.edits:
        path = str(edit.path).strip().replace("\\", "/")
        if path in targets and (path.endswith("pom.xml") or path.endswith(".java")):
            return True
    return False


def _objective_id(marker: Marker) -> str:
    payload = dict(marker.payload)
    raw = str(payload.get("objective_id", "")).strip()
    if raw:
        return raw
    marker_id = str(marker.id)
    if "::" in marker_id:
        return marker_id.rsplit("::", 1)[0]
    return marker_id


def _new_marker(
    *,
    marker_id: str,
    marker_type: str,
    target: str,
    payload: dict[str, Any],
    agent_id: str,
    intensity: float = 0.9,
    state: str = "pending",
) -> Marker:
    timestamp = utc_now_iso()
    return Marker(
        id=marker_id,
        marker_type=marker_type,
        target=target,
        intensity=max(0.0, min(1.0, float(intensity))),
        state=state,
        payload=payload,
        created_by=agent_id,
        created_at=timestamp,
        updated_by=agent_id,
        updated_at=timestamp,
        last_active_at=timestamp,
        history=["created"],
    )


def _migration_config(environment: Any) -> dict[str, Any]:
    config = getattr(environment, "config", {}) or {}
    return dict(config.get("migrationbench", {}))


def _repair_cap(environment: Any) -> int:
    config = getattr(environment, "config", {}) or {}
    targeted = dict(config.get("orchestrator", {}).get("targeted_repair", {}))
    return max(1, int(targeted.get("max_cycles", 40)))


def _branch_workspace(
    workspace: MigrationBenchWorkspace,
    *,
    branch_id: str,
    parent_branch_id: str | None = None,
    force: bool = False,
) -> MigrationBenchWorkspace:
    if parent_branch_id:
        return workspace.fork_branch_workspace(
            source_branch_id=parent_branch_id,
            branch_id=branch_id,
            force=force,
        )
    return workspace.branch_workspace(branch_id, force=force)


def _patch_markers(environment: Any) -> list[Marker]:
    try:
        return [
            marker
            for marker in environment.store.query_markers(marker_type="patch_hypothesis")
        ]
    except Exception:  # noqa: BLE001
        return []


def _best_patch_payload(environment: Any) -> dict[str, Any]:
    candidates = []
    for marker in _patch_markers(environment):
        payload = dict(marker.payload)
        score = float(payload.get("quality_score", 0.0) or 0.0)
        if payload.get("build_success"):
            score += 0.5
        if payload.get("patch_applies"):
            score += 0.2
        candidates.append((score, str(payload.get("branch_id", "")), payload))
    if not candidates:
        return {}
    candidates.sort(key=lambda item: (-item[0], item[1]))
    return dict(candidates[0][2])


def _repair_history(environment: Any, *, limit: int = 8) -> list[dict[str, Any]]:
    markers = sorted(
        _patch_markers(environment),
        key=lambda marker: int(marker.payload.get("attempt", 0) or 0),
    )
    history: list[dict[str, Any]] = []
    for marker in markers[-max(1, int(limit)) :]:
        payload = dict(marker.payload)
        application = payload.get("edit_application") or {}
        if not isinstance(application, dict):
            application = {}
        history.append(
            {
                "branch_id": payload.get("branch_id", ""),
                "attempt": int(payload.get("attempt", 0) or 0),
                "taxonomy": payload.get("failure_taxonomy", ""),
                "files_modified": list(application.get("files_modified", []) or [])[:5],
                "key_error": _feedback_digest(
                    str(payload.get("build_feedback_digest", "")),
                    max_chars=400,
                ),
            }
        )
    return history


def _edits_signature(edits: TypedEditSet) -> str:
    """Stable hash of (path, content) pairs to detect strictly identical edit sets."""
    import hashlib

    items = sorted(
        (str(edit.path).strip(), str(getattr(edit, "content", "")))
        for edit in edits.edits
        if str(edit.path).strip()
    )
    blob = "\n".join(f"{path}\x00{content}" for path, content in items).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _would_repeat_failed_repair(
    *,
    payload: dict[str, Any],
    edits: TypedEditSet,
    environment: Any,
    current_marker_id: str = "",
) -> bool:
    """Fire only when the EXACT same edits (path+content) were already tried.

    Editing the same file with different content is legitimate iterative refinement
    on a Java migration (bumping deps one by one). What is a true loop is re-emitting
    a byte-identical edit set. We compare cryptographic signatures, not paths.
    """
    if not edits.edits:
        return False
    new_signature = _edits_signature(edits)
    for marker in _patch_markers(environment):
        if current_marker_id and marker.id == current_marker_id:
            continue
        candidate = dict(marker.payload)
        prior_typed = candidate.get("typed_edits") or {}
        if not isinstance(prior_typed, dict):
            continue
        prior_edits = prior_typed.get("edits") or []
        if not isinstance(prior_edits, list) or not prior_edits:
            continue
        try:
            prior_set = TypedEditSet.model_validate({"edits": prior_edits})
        except Exception:  # noqa: BLE001
            continue
        if _edits_signature(prior_set) == new_signature:
            return True
    return False


class InspectRepositoryTool(Tool):
    """Collect compact repository context for downstream patching."""

    action_type = "inspect_repository"

    def is_eligible(self, marker: Marker) -> bool:
        return self.action_type in set(marker.payload.get("eligible_actions", []))

    async def execute(
        self,
        *,
        agent_id: str,
        marker: Marker,
        environment: Any,
        llm_client: Any | None = None,
    ) -> ActionResult:
        workspace = _workspace(environment)
        updated = Marker.from_dict(marker.to_dict())
        payload = dict(updated.payload)
        payload["repo_summary"] = workspace.summarize()
        updated.payload = payload
        updated.state = "terminal"
        return ActionResult(action_type=self.action_type, marker_updates=[updated])


class ProposePatchTool(Tool):
    """LLM-backed typed edit proposal with deterministic fallback edits."""

    action_type = "propose_patch"

    def is_eligible(self, marker: Marker) -> bool:
        return self.action_type in set(marker.payload.get("eligible_actions", []))

    async def execute(
        self,
        *,
        agent_id: str,
        marker: Marker,
        environment: Any,
        llm_client: Any | None = None,
    ) -> ActionResult:
        workspace = _workspace(environment)
        tokens = 0
        cost = 0.0
        llm_failure = ""
        edits = deterministic_java17_pom_edits(workspace)

        if llm_client is not None:
            try:
                prompt = build_edit_prompt(workspace=workspace, strategy="stigmergic_v6_static")
                response = await llm_client.acall(
                    prompt=prompt,
                    system=SYSTEM_MIGRATION_EDIT,
                    response_schema=TypedEditSet,
                )
                tokens = int(response.tokens_used)
                cost = float(response.cost_usd)
                parsed = response.parsed if response.parsed is not None else response.content
                edits = parse_typed_edit_set(parsed)
            except Exception as exc:  # noqa: BLE001
                llm_failure = f"{type(exc).__name__}:{exc}"

        application = workspace.apply_typed_edits(edits)
        updated = Marker.from_dict(marker.to_dict())
        payload = dict(updated.payload)
        payload.update(
            {
                "typed_edits": edits.model_dump(),
                "edit_application": application.model_dump(),
                "llm_failure": llm_failure,
            }
        )
        updated.payload = payload
        updated.state = "terminal" if application.applied else "escalated"
        return ActionResult(
            action_type=self.action_type,
            marker_updates=[updated],
            consumed_tokens=tokens,
            cost_usd=cost,
            metadata={
                "llm_calls": 1 if llm_client is not None and not llm_failure else 0,
                "failed": not application.applied,
                "reason": application.failure_reason,
            },
        )


class RunBuildTool(Tool):
    """Run the configured Maven build command after applying edits."""

    action_type = "run_build"

    def __init__(self, *, config: dict[str, Any]) -> None:
        migration_cfg = dict(config.get("migrationbench", {}))
        self.command = str(migration_cfg.get("build_command", "mvn clean verify"))
        self.timeout_seconds = float(migration_cfg.get("build_timeout_seconds", 1800))

    def is_eligible(self, marker: Marker) -> bool:
        return self.action_type in set(marker.payload.get("eligible_actions", []))

    async def execute(
        self,
        *,
        agent_id: str,
        marker: Marker,
        environment: Any,
        llm_client: Any | None = None,
    ) -> ActionResult:
        workspace = _workspace(environment)
        build = workspace.run_maven(self.command, timeout_seconds=self.timeout_seconds)
        updated = Marker.from_dict(marker.to_dict())
        payload = dict(updated.payload)
        payload["build"] = {
            "command": self.command,
            "returncode": build.returncode,
            "stdout_tail": build.stdout[-4000:],
            "stderr_tail": build.stderr[-4000:],
            "runtime_seconds": round(build.runtime_seconds, 4),
        }
        updated.payload = payload
        updated.state = "terminal"
        return ActionResult(
            action_type=self.action_type,
            marker_updates=[updated],
            metadata={"build_success": build.ok, "failed": not build.ok},
        )


class LocalizeMigrationSurfaceTool(Tool):
    """Create compact migration-localization context before patch generation."""

    action_type = "localize_migration_surface"

    def is_eligible(self, marker: Marker) -> bool:
        return self.action_type in set(marker.payload.get("eligible_actions", []))

    async def execute(
        self,
        *,
        agent_id: str,
        marker: Marker,
        environment: Any,
        llm_client: Any | None = None,
    ) -> ActionResult:
        workspace = _workspace(environment)
        updated = Marker.from_dict(marker.to_dict())
        payload = dict(updated.payload)
        summary = workspace.summarize(max_files=80)
        payload["repo_summary"] = summary
        payload["migration_surface"] = {
            "pom_files": summary.get("pom_files", []),
            "java_files_sample": summary.get("java_files_sample", []),
            "target_java": workspace.instance.target_java,
            "migration_mode": workspace.instance.migration_mode,
        }
        updated.payload = payload
        updated.state = "terminal"
        return ActionResult(action_type=self.action_type, marker_updates=[updated])


class ProposePatchCandidateTool(Tool):
    """Generate the first traceable patch hypothesis without mutating the base repo."""

    action_type = "propose_patch_candidate"

    def is_eligible(self, marker: Marker) -> bool:
        return self.action_type in set(marker.payload.get("eligible_actions", []))

    async def execute(
        self,
        *,
        agent_id: str,
        marker: Marker,
        environment: Any,
        llm_client: Any | None = None,
    ) -> ActionResult:
        workspace = _workspace(environment)
        tokens = 0
        cost = 0.0
        llm_calls = 0
        llm_failure = ""
        edits = deterministic_java17_pom_edits(workspace)

        prompt = build_edit_prompt(
            workspace=workspace,
            strategy="v7 initial patch hypothesis; reason-act-observe repair colony",
        )
        edits, tokens, cost, llm_calls, llm_failure = await _request_typed_edits(
            llm_client=llm_client,
            workspace=workspace,
            prompt=prompt,
            system=SYSTEM_MIGRATION_EDIT,
            fallback=edits,
        )

        if not edits.edits or not _relevant_edits(edits, workspace):
            updated = Marker.from_dict(marker.to_dict())
            updated_payload = dict(updated.payload)
            updated_payload.update(
                {
                    "typed_edits": edits.model_dump(),
                    "failure_taxonomy": "empty_or_irrelevant_edits",
                    "llm_failure": llm_failure,
                }
            )
            updated.payload = updated_payload
            updated.state = "terminal"
            return ActionResult(
                action_type=self.action_type,
                marker_updates=[updated],
                consumed_tokens=tokens,
                cost_usd=cost,
                metadata={"llm_calls": llm_calls, "failed": True},
                validation=_retry_same_action_validation(
                    marker=updated,
                    action_type=self.action_type,
                    taxonomy="empty_or_irrelevant_edits",
                    feedback=["The patch proposal emitted no relevant edits for existing pom.xml or Java files."],
                    environment=environment,
                ),
            )

        objective_id = _objective_id(marker)
        branch_id = "b1"
        hypothesis_id = f"{objective_id}::patch::{branch_id}"
        base_payload = dict(marker.payload)
        patch_payload = {
            **base_payload,
            "objective_id": objective_id,
            "branch_id": branch_id,
            "parent_branch_id": None,
            "attempt": 0,
            "typed_edits": edits.model_dump(),
            "failure_taxonomy": "",
            "build_feedback_digest": "",
            "patch_applies": False,
            "build_success": False,
            "official_success": False,
            "quality_score": 0.0,
            "llm_failure": llm_failure,
            "eligible_actions": ["apply_patch_candidate"],
            "depends_on": [marker.id],
        }
        hypothesis = _new_marker(
            marker_id=hypothesis_id,
            marker_type="patch_hypothesis",
            target=f"patch::{branch_id}",
            payload=patch_payload,
            agent_id=agent_id,
            intensity=0.95,
        )
        updated = Marker.from_dict(marker.to_dict())
        updated.state = "terminal"
        updated_payload = dict(updated.payload)
        updated_payload["initial_branch_id"] = branch_id
        updated_payload["llm_failure"] = llm_failure
        updated.payload = updated_payload
        return ActionResult(
            action_type=self.action_type,
            marker_updates=[updated, hypothesis],
            consumed_tokens=tokens,
            cost_usd=cost,
            metadata={"llm_calls": llm_calls, "failed": False},
        )


class ApplyPatchCandidateTool(Tool):
    """Apply one candidate's typed edits inside an isolated branch workspace."""

    action_type = "apply_patch_candidate"

    def is_eligible(self, marker: Marker) -> bool:
        return self.action_type in set(marker.payload.get("eligible_actions", []))

    async def execute(
        self,
        *,
        agent_id: str,
        marker: Marker,
        environment: Any,
        llm_client: Any | None = None,
    ) -> ActionResult:
        workspace = _workspace(environment)
        payload = dict(marker.payload)
        branch_id = str(payload.get("branch_id", "b1")).strip() or "b1"
        parent_branch_id = payload.get("parent_branch_id")
        if parent_branch_id is not None:
            parent_branch_id = str(parent_branch_id).strip() or None
        edits = parse_typed_edit_set(payload.get("typed_edits", {}))
        updated = Marker.from_dict(marker.to_dict())
        if not edits.edits:
            application_payload = {
                "applied": False,
                "failure_reason": "empty_typed_edits",
                "files_modified": [],
                "replacements": {},
            }
            payload["edit_application"] = application_payload
            payload["failure_taxonomy"] = "patch_apply_error"
            updated.payload = payload
            updated.state = "terminal"
            return ActionResult(
                action_type=self.action_type,
                marker_updates=[updated],
                metadata={"failed": True, "reason": "empty_typed_edits"},
                validation=_repair_validation(
                    marker=updated,
                    taxonomy="patch_apply_error",
                    feedback=["The candidate emitted no typed edits."],
                    environment=environment,
                ),
            )

        branch = _branch_workspace(
            workspace,
            branch_id=branch_id,
            parent_branch_id=parent_branch_id,
            force=True,
        )
        application = branch.apply_typed_edits(edits)
        payload["edit_application"] = application.model_dump()
        payload["patch_applies"] = bool(application.applied)
        updated.payload = payload
        if application.applied:
            payload["eligible_actions"] = ["run_build_validation"]
            updated.payload = payload
            updated.state = "planning"
            return ActionResult(
                action_type=self.action_type,
                marker_updates=[updated],
                metadata={"failed": False, "quality_score": 0.2},
            )

        taxonomy = "patch_apply_error"
        payload["failure_taxonomy"] = taxonomy
        updated.payload = payload
        updated.state = "terminal"
        return ActionResult(
            action_type=self.action_type,
            marker_updates=[updated],
            metadata={"failed": True, "reason": application.failure_reason},
            validation=_repair_validation(
                marker=updated,
                taxonomy=taxonomy,
                feedback=[application.failure_reason],
                environment=environment,
            ),
        )


class RunBuildValidationTool(Tool):
    """Run official-like Maven validation on a candidate branch."""

    action_type = "run_build_validation"

    def __init__(self, *, config: dict[str, Any]) -> None:
        migration_cfg = dict(config.get("migrationbench", {}))
        self.command = str(migration_cfg.get("build_command", "mvn clean verify"))
        self.timeout_seconds = float(migration_cfg.get("build_timeout_seconds", 1800))

    def is_eligible(self, marker: Marker) -> bool:
        return self.action_type in set(marker.payload.get("eligible_actions", []))

    async def execute(
        self,
        *,
        agent_id: str,
        marker: Marker,
        environment: Any,
        llm_client: Any | None = None,
    ) -> ActionResult:
        workspace = _workspace(environment)
        payload = dict(marker.payload)
        branch_id = str(payload.get("branch_id", "b1")).strip() or "b1"
        branch = workspace.branch_workspace(branch_id, force=False)
        short_timeout = min(300.0, self.timeout_seconds)
        dependency = branch.run_maven("mvn dependency:resolve", timeout_seconds=short_timeout)
        compile_result = branch.run_maven("mvn clean compile", timeout_seconds=self.timeout_seconds)
        verify_result = branch.run_maven(self.command, timeout_seconds=self.timeout_seconds)
        test_result = branch.run_maven("mvn -DskipTests=false test", timeout_seconds=self.timeout_seconds)
        class_versions = _class_major_versions(branch)
        target_major = _target_major_version(branch)
        compiled_major_version_ok = class_versions == {target_major}
        tests_run_count = _surefire_test_count(branch)
        required_tests = _required_test_count(branch)
        test_count_non_decreasing = (
            True
            if required_tests is None
            else bool(tests_run_count is not None and tests_run_count >= required_tests)
        )
        build_success = bool(
            verify_result.ok and compiled_major_version_ok and test_count_non_decreasing
        )
        combined_feedback = "\n".join(
            [
                dependency.stdout,
                dependency.stderr,
                compile_result.stdout,
                compile_result.stderr,
                verify_result.stdout,
                verify_result.stderr,
                test_result.stdout,
                test_result.stderr,
                f"class_versions={sorted(class_versions)} target_major={target_major}",
                f"tests_run_count={tests_run_count} required_tests={required_tests}",
            ]
        )
        feedback = _feedback_digest(combined_feedback, max_chars=4000)
        payload["build"] = {
            "command": self.command,
            "returncode": verify_result.returncode,
            "stdout_tail": verify_result.stdout[-4000:],
            "stderr_tail": verify_result.stderr[-4000:],
            "runtime_seconds": round(verify_result.runtime_seconds, 4),
        }
        payload["official_like_validation"] = {
            "dependency_resolution": {
                "command": "mvn dependency:resolve",
                "returncode": dependency.returncode,
                "success": bool(dependency.ok),
                "runtime_seconds": round(dependency.runtime_seconds, 4),
            },
            "compile": {
                "command": "mvn clean compile",
                "returncode": compile_result.returncode,
                "success": bool(compile_result.ok),
                "runtime_seconds": round(compile_result.runtime_seconds, 4),
            },
            "verify": {
                "command": self.command,
                "returncode": verify_result.returncode,
                "success": bool(verify_result.ok),
                "runtime_seconds": round(verify_result.runtime_seconds, 4),
            },
            "test": {
                "command": "mvn -DskipTests=false test",
                "returncode": test_result.returncode,
                "success": bool(test_result.ok),
                "runtime_seconds": round(test_result.runtime_seconds, 4),
            },
            "class_versions": sorted(class_versions),
            "target_major_version": target_major,
            "tests_run_count": tests_run_count,
            "required_tests": required_tests,
        }
        payload["dependency_resolution_success"] = bool(dependency.ok)
        payload["compile_success"] = bool(compile_result.ok)
        payload["test_success"] = bool(test_result.ok)
        payload["compiled_major_version_ok"] = bool(compiled_major_version_ok)
        payload["test_count_non_decreasing"] = bool(test_count_non_decreasing)
        payload["build_feedback_digest"] = feedback
        payload["build_success"] = bool(build_success)
        payload["quality_score"] = (
            0.85 if build_success else 0.55 if compile_result.ok else 0.25
        )
        payload["eligible_actions"] = (
            ["select_patch_candidate"] if build_success else ["classify_build_failure"]
        )
        updated = Marker.from_dict(marker.to_dict())
        updated.payload = payload
        updated.state = "planning"
        return ActionResult(
            action_type=self.action_type,
            marker_updates=[updated],
            metadata={
                "build_success": build_success,
                "failed": False,
                "quality_score": payload["quality_score"],
            },
        )


class ClassifyBuildFailureTool(Tool):
    """Turn build feedback into a typed stigmergic repair request."""

    action_type = "classify_build_failure"

    def is_eligible(self, marker: Marker) -> bool:
        return self.action_type in set(marker.payload.get("eligible_actions", []))

    async def execute(
        self,
        *,
        agent_id: str,
        marker: Marker,
        environment: Any,
        llm_client: Any | None = None,
    ) -> ActionResult:
        payload = dict(marker.payload)
        feedback = str(payload.get("build_feedback_digest", "")).strip()
        taxonomy = classify_maven_failure(feedback)
        attempt = int(payload.get("attempt", 0) or 0)
        payload["failure_taxonomy"] = taxonomy
        payload["quality_score"] = 0.15
        updated = Marker.from_dict(marker.to_dict())
        updated.payload = payload
        updated.state = "terminal"
        marker_updates = [updated]

        if attempt >= _repair_cap(environment):
            best_payload = _best_patch_payload(environment)
            if best_payload and (
                bool(best_payload.get("compile_success"))
                or bool(best_payload.get("patch_applies"))
            ):
                branch_id = str(best_payload.get("branch_id", "best")).strip() or "best"
                objective_id = str(
                    best_payload.get("objective_id", payload.get("objective_id", _objective_id(marker)))
                ).strip()
                best_payload.update(
                    {
                        "selected_for_official_eval": True,
                        "best_partial_finalization": True,
                        "eligible_actions": ["finalize_evaluated_patch"],
                        "failure_taxonomy": f"repair_cap_reached:{taxonomy}",
                        "failure_reason": f"repair_cap_reached:{taxonomy}",
                    }
                )
                marker_updates.append(
                    _new_marker(
                        marker_id=f"{objective_id}::patch::{branch_id}::best_partial_finalize",
                        marker_type="patch_hypothesis",
                        target=f"patch::{branch_id}",
                        payload=best_payload,
                        agent_id=agent_id,
                        intensity=0.9,
                        state="pending",
                    )
                )
            else:
                marker_updates.append(
                    _final_marker_from_payload(
                        source_marker=updated,
                        agent_id=agent_id,
                        reason="repair_cap_reached:no_buildable_branch",
                    )
                )
            return ActionResult(
                action_type=self.action_type,
                marker_updates=marker_updates,
                metadata={"failed": False, "quality_score": 0.0},
            )

        return ActionResult(
            action_type=self.action_type,
            marker_updates=marker_updates,
            metadata={"failed": False, "quality_score": 0.1},
            validation=_repair_validation(
                marker=updated,
                taxonomy=taxonomy,
                feedback=[feedback or taxonomy],
                environment=environment,
            ),
        )


class RepairPatchCandidateTool(Tool):
    """Generate a new candidate branch from a typed failure marker."""

    action_type = "repair_patch_candidate"

    def is_eligible(self, marker: Marker) -> bool:
        return self.action_type in set(marker.payload.get("eligible_actions", []))

    async def execute(
        self,
        *,
        agent_id: str,
        marker: Marker,
        environment: Any,
        llm_client: Any | None = None,
    ) -> ActionResult:
        workspace = _workspace(environment)
        payload = dict(marker.payload)
        parent_branch_id = str(payload.get("branch_id", "b1")).strip() or "b1"
        repair_attempt = int(payload.get("repair_attempt", payload.get("attempt", 0) + 1) or 1)
        branch_id = f"b{repair_attempt + 1}"
        taxonomy = str(payload.get("failure_taxonomy", "build_failure")).strip()
        feedback = "\n".join(str(item) for item in payload.get("repair_feedback", []) if str(item).strip())
        parent_branch = workspace.branch_workspace(parent_branch_id, force=False)
        tokens = 0
        cost = 0.0
        llm_calls = 0
        llm_failure = ""
        edits = TypedEditSet(edits=[], rationale="no_llm_repair_available")

        previous_attempts = _repair_history(environment)
        prompt = build_edit_prompt(
            workspace=parent_branch,
            strategy=(
                f"v7 repair branch for {taxonomy}; "
                f"parent={parent_branch_id}; attempt={repair_attempt}"
            ),
            feedback=(
                f"{feedback}\n\nprevious_attempts JSON:\n"
                f"{json.dumps(previous_attempts, indent=2)[:6000]}"
            ),
        )
        edits, tokens, cost, llm_calls, llm_failure = await _request_typed_edits(
            llm_client=llm_client,
            workspace=parent_branch,
            prompt=prompt,
            system=SYSTEM_REPAIR_EDIT,
            fallback=edits,
        )

        if not edits.edits or not _relevant_edits(edits, parent_branch):
            updated = Marker.from_dict(marker.to_dict())
            updated_payload = dict(updated.payload)
            updated_payload.update(
                {
                    "typed_edits": edits.model_dump(),
                    "failure_taxonomy": "empty_or_irrelevant_edits",
                    "llm_failure": llm_failure,
                }
            )
            updated.payload = updated_payload
            updated.state = "terminal"
            return ActionResult(
                action_type=self.action_type,
                marker_updates=[updated],
                consumed_tokens=tokens,
                cost_usd=cost,
                metadata={"llm_calls": llm_calls, "failed": True},
                validation=_repair_validation(
                    marker=updated,
                    taxonomy="empty_or_irrelevant_edits",
                    feedback=["The repair emitted no relevant edits for existing pom.xml or Java files."],
                    environment=environment,
                ),
            )

        if _would_repeat_failed_repair(
            payload=payload,
            edits=edits,
            environment=environment,
            current_marker_id=marker.id,
        ):
            duplicate_signature = _edits_signature(edits)
            anti_repeat_prompt = build_edit_prompt(
                workspace=parent_branch,
                strategy=(
                    f"v7 repair retry for {taxonomy}; "
                    f"parent={parent_branch_id}; attempt={repair_attempt}; "
                    f"FORBIDDEN signature={duplicate_signature[:12]}"
                ),
                feedback=(
                    f"{feedback}\n\nIMPORTANT: your previous response was BYTE-IDENTICAL to a "
                    f"prior failed attempt. You MUST emit substantially different content "
                    f"(different dependency versions, different config keys, or different files). "
                    f"Do not re-emit the same edit set.\n\nprevious_attempts JSON:\n"
                    f"{json.dumps(previous_attempts, indent=2)[:6000]}"
                ),
            )
            retry_edits, retry_tokens, retry_cost, retry_calls, retry_failure = await _request_typed_edits(
                llm_client=llm_client,
                workspace=parent_branch,
                prompt=anti_repeat_prompt,
                system=SYSTEM_REPAIR_EDIT,
                fallback=edits,
            )
            tokens += retry_tokens
            cost += retry_cost
            llm_calls += retry_calls
            if retry_failure:
                llm_failure = retry_failure
            still_duplicate = (
                not retry_edits.edits
                or _edits_signature(retry_edits) == duplicate_signature
                or _would_repeat_failed_repair(
                    payload=payload,
                    edits=retry_edits,
                    environment=environment,
                    current_marker_id=marker.id,
                )
            )
            if still_duplicate:
                updated = Marker.from_dict(marker.to_dict())
                updated_payload = dict(updated.payload)
                updated_payload.update(
                    {
                        "typed_edits": edits.model_dump(),
                        "failure_taxonomy": "anti_loop_repeated_repair",
                        "llm_failure": llm_failure,
                    }
                )
                updated.payload = updated_payload
                updated.state = "terminal"
                return ActionResult(
                    action_type=self.action_type,
                    marker_updates=[updated],
                    consumed_tokens=tokens,
                    cost_usd=cost,
                    metadata={"llm_calls": llm_calls, "failed": True},
                )
            edits = retry_edits

        objective_id = str(payload.get("objective_id", _objective_id(marker))).strip()
        hypothesis_id = f"{objective_id}::patch::{branch_id}"
        patch_payload = {
            **payload,
            "objective_id": objective_id,
            "branch_id": branch_id,
            "parent_branch_id": parent_branch_id,
            "attempt": repair_attempt,
            "typed_edits": edits.model_dump(),
            "failure_taxonomy": taxonomy,
            "llm_failure": llm_failure,
            "eligible_actions": ["apply_patch_candidate"],
            "depends_on": [marker.id],
        }
        for key in (
            "repair_target_id",
            "repair_source_id",
            "repair_attempt",
            "repair_targets",
            "validation_feedback",
            "repair_feedback",
        ):
            patch_payload.pop(key, None)
        hypothesis = _new_marker(
            marker_id=hypothesis_id,
            marker_type="patch_hypothesis",
            target=f"patch::{branch_id}",
            payload=patch_payload,
            agent_id=agent_id,
            intensity=0.95,
        )
        updated = Marker.from_dict(marker.to_dict())
        updated.state = "terminal"
        return ActionResult(
            action_type=self.action_type,
            marker_updates=[updated, hypothesis],
            consumed_tokens=tokens,
            cost_usd=cost,
            metadata={"llm_calls": llm_calls, "failed": False},
        )


class SelectPatchCandidateTool(Tool):
    """Select a build-validated candidate for official evaluation."""

    action_type = "select_patch_candidate"

    def is_eligible(self, marker: Marker) -> bool:
        return self.action_type in set(marker.payload.get("eligible_actions", []))

    async def execute(
        self,
        *,
        agent_id: str,
        marker: Marker,
        environment: Any,
        llm_client: Any | None = None,
    ) -> ActionResult:
        payload = dict(marker.payload)
        if not bool(payload.get("build_success")) and not bool(
            payload.get("best_partial_finalization")
        ):
            payload["selected_for_official_eval"] = False
            payload["failure_taxonomy"] = "selection_rejected_unvalidated_patch"
            updated = Marker.from_dict(marker.to_dict())
            updated.payload = payload
            updated.state = "terminal"
            return ActionResult(
                action_type=self.action_type,
                marker_updates=[updated],
                metadata={"failed": True, "quality_score": 0.0},
            )
        payload["selected_for_official_eval"] = True
        payload["eligible_actions"] = ["finalize_evaluated_patch"]
        payload["quality_score"] = max(0.75, float(payload.get("quality_score", 0.0) or 0.0))
        updated = Marker.from_dict(marker.to_dict())
        updated.payload = payload
        updated.state = "planning"
        return ActionResult(
            action_type=self.action_type,
            marker_updates=[updated],
            metadata={"failed": False, "quality_score": payload["quality_score"]},
        )


class FinalizeEvaluatedPatchTool(Tool):
    """Export the selected branch patch and run the official evaluator."""

    action_type = "finalize_evaluated_patch"

    def __init__(self, *, config: dict[str, Any]) -> None:
        self.config = config

    def is_eligible(self, marker: Marker) -> bool:
        return self.action_type in set(marker.payload.get("eligible_actions", []))

    async def execute(
        self,
        *,
        agent_id: str,
        marker: Marker,
        environment: Any,
        llm_client: Any | None = None,
    ) -> ActionResult:
        workspace = _workspace(environment)
        payload = dict(marker.payload)
        branch_id = str(payload.get("branch_id", "b1")).strip() or "b1"
        branch = workspace.branch_workspace(branch_id, force=False)
        cfg = dict(self.config.get("migrationbench", {}))
        output_dir = Path(cfg.get("artifact_dir", workspace.root_dir / "artifacts"))
        patch_path = output_dir / f"{branch_id}_patch.diff"
        final_patch_path = output_dir / "patch.diff"
        official_dir = output_dir / "official"
        stats = branch.export_patch(patch_path)
        if patch_path.exists():
            final_patch_path.parent.mkdir(parents=True, exist_ok=True)
            final_patch_path.write_text(patch_path.read_text(encoding="utf-8"), encoding="utf-8")
        patch_applies, patch_reason = branch.verify_patch_applies(
            patch_path=patch_path,
            verification_root=branch.root_dir / "verification",
            force=True,
        )
        evaluator = MigrationBenchEvaluator(
            migrationbench_root=cfg.get("official_root", "external/MigrationBench"),
            run_official=bool(cfg.get("run_official_eval", True)),
            timeout_seconds=float(cfg.get("official_timeout_seconds", 1800)),
        )
        official = evaluator.evaluate_patch(
            instance=workspace.instance,
            patch_path=patch_path,
            output_dir=official_dir,
            patch_stats=stats,
            patch_applies=patch_applies,
            patch_apply_reason=patch_reason,
            maven_command=str(cfg.get("official_maven_command", "cd {root_dir}; mvn clean verify")),
        )
        llm_cfg = dict(self.config.get("llm", {}))
        patch_markers = _patch_markers(environment)
        repair_cycles = max(
            [int(candidate.payload.get("attempt", 0) or 0) for candidate in patch_markers] or [0]
        )
        branch_count = len({
            str(candidate.payload.get("branch_id", "")).strip()
            for candidate in patch_markers
            if str(candidate.payload.get("branch_id", "")).strip()
        })
        contract = build_strict_contract(
            instance=workspace.instance,
            framework=str(cfg.get("framework", "stigmergic_v7_repair_colony")),
            provider=str(llm_cfg.get("provider", "")),
            model=str(llm_cfg.get("model", "")),
            seed=int(cfg.get("seed", 42)),
            patch_path=final_patch_path,
            patch_stats=stats,
            patch_applies=patch_applies,
            patch_apply_reason=patch_reason,
            official=official,
            tokens_total=int(getattr(environment, "tokens_used", 0)),
            cost_total_usd=float(getattr(environment, "cost_used", 0.0)),
            repair_cycles=repair_cycles,
            llm_calls=int(getattr(environment, "llm_calls_used", 0)),
            extra={
                "best_branch_id": branch_id,
                "branch_count": branch_count,
                "failure_taxonomy": payload.get("failure_taxonomy", ""),
                "build_feedback_digest": payload.get("build_feedback_digest", ""),
                "caps_hit": _caps_hit(environment=environment, repair_cycles=repair_cycles),
            },
        )
        source_update = Marker.from_dict(marker.to_dict())
        source_payload = dict(source_update.payload)
        source_payload.update(
            {
                "official_success": contract["official_success"],
                "strict_success": contract["strict_success"],
                "patch_applies": contract["patch_applies"],
                "quality_score": 1.0 if contract["strict_success"] else 0.2,
                "failure_taxonomy": (
                    ""
                    if contract["strict_success"]
                    else (
                        "official_eval_failed"
                        if contract["patch_applies"]
                        else "patch_apply_error"
                    )
                ),
            }
        )
        source_update.payload = source_payload
        source_update.state = "terminal"
        final_marker = _final_marker_from_payload(
            source_marker=source_update,
            agent_id=agent_id,
            reason=contract["failure_reason"],
        )
        final_payload = dict(final_marker.payload)
        final_payload.update(contract)
        final_marker.payload = final_payload
        validation = None
        official_ran = bool(official.get("official_eval_ran", False))
        repairable_final_failure = bool(
            not contract["strict_success"]
            and (not contract["patch_applies"] or official_ran)
        )
        if repairable_final_failure:
            feedback_text = "\n".join(
                [
                    str(official.get("official_eval_stdout_tail", "")),
                    str(official.get("official_eval_stderr_tail", "")),
                    str(contract.get("patch_apply_reason", "")),
                ]
            )
            validation = _repair_validation(
                marker=source_update,
                taxonomy=str(source_payload.get("failure_taxonomy", "official_eval_failed")),
                feedback=[_feedback_digest(feedback_text)],
                environment=environment,
            )

        return ActionResult(
            action_type=self.action_type,
            marker_updates=[source_update, final_marker],
            metadata={"quality_score": 1.0 if contract["strict_success"] else 0.0},
            validation=validation,
        )


def _repair_validation(
    *,
    marker: Marker,
    taxonomy: str,
    feedback: list[str],
    environment: Any,
) -> ValidationResult | None:
    is_repair_marker = str(marker.id).startswith("repair::")
    target_marker_id = (
        str(marker.payload.get("repair_target_id", "")).strip()
        if is_repair_marker
        else ""
    ) or marker.id
    attempt_basis = (
        marker.payload.get("repair_attempt")
        if is_repair_marker and marker.payload.get("repair_attempt") is not None
        else marker.payload.get("attempt", 0)
    )
    attempt = int(attempt_basis or 0) + 1
    max_attempts = _repair_cap(environment)
    if attempt > max_attempts:
        return None
    payload_updates = {
        "failure_taxonomy": taxonomy,
        "repair_feedback": [item for item in feedback if str(item).strip()],
        "eligible_actions": ["repair_patch_candidate"],
    }
    return ValidationResult(
        status="failed",
        source_marker_id=target_marker_id,
        targets=[target_marker_id],
        feedback=[item for item in feedback if str(item).strip()],
        repair=RepairRequest(
            target_marker_id=target_marker_id,
            attempt=attempt,
            max_attempts=max_attempts,
            feedback=[item for item in feedback if str(item).strip()],
            eligible_actions=["repair_patch_candidate"],
            intensity=0.95,
            marker_type="patch_hypothesis",
            payload_updates=payload_updates,
        ),
    )


def _retry_same_action_validation(
    *,
    marker: Marker,
    action_type: str,
    taxonomy: str,
    feedback: list[str],
    environment: Any,
) -> ValidationResult | None:
    attempt = int(marker.payload.get("repair_attempt", marker.payload.get("attempt", 0)) or 0) + 1
    max_attempts = _repair_cap(environment)
    if attempt > max_attempts:
        return None
    payload_updates = {
        "failure_taxonomy": taxonomy,
        "repair_feedback": [item for item in feedback if str(item).strip()],
        "eligible_actions": [action_type],
    }
    return ValidationResult(
        status="failed",
        source_marker_id=marker.id,
        targets=[marker.id],
        feedback=[item for item in feedback if str(item).strip()],
        repair=RepairRequest(
            target_marker_id=marker.id,
            attempt=attempt,
            max_attempts=max_attempts,
            feedback=[item for item in feedback if str(item).strip()],
            eligible_actions=[action_type],
            intensity=0.95,
            marker_type=marker.marker_type,
            payload_updates=payload_updates,
        ),
    )


def _final_marker_from_payload(
    *,
    source_marker: Marker,
    agent_id: str,
    reason: str,
) -> Marker:
    payload = dict(source_marker.payload)
    objective_id = str(payload.get("objective_id", _objective_id(source_marker))).strip()
    payload["artifact_delivered"] = bool(payload.get("artifact_delivered", False))
    payload["patch_delivered"] = bool(payload.get("patch_delivered", False))
    payload["patch_applies"] = bool(payload.get("patch_applies", False))
    payload["official_success"] = bool(payload.get("official_success", False))
    payload["strict_success"] = bool(payload.get("strict_success", False))
    payload["failure_reason"] = str(reason or payload.get("failure_reason", "official_eval_failed"))
    return _new_marker(
        marker_id=f"{objective_id}::finalize_evaluated_patch",
        marker_type="task",
        target="finalize_evaluated_patch",
        payload=payload,
        agent_id=agent_id,
        intensity=0.8,
        state="terminal",
    )


def _caps_hit(*, environment: Any, repair_cycles: int) -> dict[str, bool]:
    config = getattr(environment, "config", {}) or {}
    migration_cfg = dict(config.get("migrationbench", {}))
    caps = dict(migration_cfg.get("safety_caps", {}))
    token_cap = int(
        config.get("llm", {}).get(
            "max_tokens_total",
            caps.get("max_tokens_per_instance", 0),
        )
        or 0
    )
    llm_call_cap = int(caps.get("max_llm_calls_per_instance", 0) or 0)
    repair_cap = int(caps.get("max_repair_cycles_per_instance", _repair_cap(environment)) or 0)
    return {
        "tokens": bool(token_cap and int(getattr(environment, "tokens_used", 0)) >= token_cap),
        "llm_calls": bool(llm_call_cap and int(getattr(environment, "llm_calls_used", 0)) >= llm_call_cap),
        "repair_cycles": bool(repair_cap and int(repair_cycles) >= repair_cap),
    }


class FinalizePatchTool(Tool):
    """Export, verify, and officially evaluate the final patch artifact."""

    action_type = "finalize_patch"

    def __init__(self, *, config: dict[str, Any]) -> None:
        self.config = config

    def is_eligible(self, marker: Marker) -> bool:
        return self.action_type in set(marker.payload.get("eligible_actions", []))

    async def execute(
        self,
        *,
        agent_id: str,
        marker: Marker,
        environment: Any,
        llm_client: Any | None = None,
    ) -> ActionResult:
        workspace = _workspace(environment)
        cfg = dict(self.config.get("migrationbench", {}))
        output_dir = Path(cfg.get("artifact_dir", workspace.root_dir / "artifacts"))
        patch_path = output_dir / "patch.diff"
        official_dir = output_dir / "official"
        stats = workspace.export_patch(patch_path)
        patch_applies, patch_reason = workspace.verify_patch_applies(
            patch_path=patch_path,
            verification_root=workspace.root_dir / "verification",
            force=True,
        )
        evaluator = MigrationBenchEvaluator(
            migrationbench_root=cfg.get("official_root", "external/MigrationBench"),
            run_official=bool(cfg.get("run_official_eval", True)),
            timeout_seconds=float(cfg.get("official_timeout_seconds", 1800)),
        )
        official = evaluator.evaluate_patch(
            instance=workspace.instance,
            patch_path=patch_path,
            output_dir=official_dir,
            patch_stats=stats,
            patch_applies=patch_applies,
            patch_apply_reason=patch_reason,
            maven_command=str(cfg.get("official_maven_command", "cd {root_dir}; mvn clean verify")),
        )
        llm_cfg = dict(self.config.get("llm", {}))
        contract = build_strict_contract(
            instance=workspace.instance,
            framework=str(cfg.get("framework", "stigmergic_v6_static")),
            provider=str(llm_cfg.get("provider", "")),
            model=str(llm_cfg.get("model", "")),
            seed=int(cfg.get("seed", 42)),
            patch_path=patch_path,
            patch_stats=stats,
            patch_applies=patch_applies,
            patch_apply_reason=patch_reason,
            official=official,
            tokens_total=int(getattr(environment, "tokens_used", 0)),
            cost_total_usd=float(getattr(environment, "cost_used", 0.0)),
        )
        updated = Marker.from_dict(marker.to_dict())
        payload = dict(updated.payload)
        payload.update(contract)
        updated.payload = payload
        updated.state = "terminal"
        return ActionResult(
            action_type=self.action_type,
            marker_updates=[updated],
            metadata={"quality_score": 1.0 if contract["strict_success"] else 0.0},
        )


def _workspace(environment: Any) -> MigrationBenchWorkspace:
    workspace = getattr(environment, "workspace", None)
    if not isinstance(workspace, MigrationBenchWorkspace):
        raise RuntimeError("MigrationBenchWorkspace is required")
    return workspace
