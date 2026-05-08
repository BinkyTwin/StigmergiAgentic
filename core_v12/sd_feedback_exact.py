"""Official SD-Feedback protocol adapters for V12.4.

This module mirrors the JavaMigration ``self_debug`` protocol closely enough
for a strong MigrationBench baseline: Java 17 seed POM rewrite, grouped
``[Change Start]`` responses, paired ``[Find]/[Replace]`` parsing, fuzzy
find-block replacement, feedback retries, and accept/revert based on whether
the build error changed.

Source implementation: https://github.com/amazon-science/JavaMigration
Package path in that repository: ``self_debug/src/self_debug``.
"""

from __future__ import annotations

import glob
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

from core_v10.contracts import ValidationResult


OFFICIAL_SD_FEEDBACK_SOURCE_URL = "https://github.com/amazon-science/JavaMigration"
OFFICIAL_TARGET_JAVA = 17
OFFICIAL_RESTART_MESSAGES_LEN_GT = 10
OFFICIAL_BUILD_ERRORS_DO_NOT_CHANGE_AS_FEEDBACK = (
    "The build errors are all the same as before, after applying the suggested "
    "changes, therefore the changes are reverted."
)

_MAVEN_NS = "http://maven.apache.org/POM/4.0.0"
_NS = {"xmlns": _MAVEN_NS}


OFFICIAL_MAVEN_TEMPLATE_PROMPT = """You are a Java programmer.
You are a skilled debugger of Java applications.
You are trying to resolve a build error.
Use knowledge and explain how all constraints, requirements are satisfied before making the code change.
Given the compile_error in the file_content, output a set of changes that I can apply to the file_content to get new file content without compile error.

Think step by step and provide an explanation of the changes before the code changes.
All constraints and requirements must be followed.


<constraints>
- Explanation must match code change.
- The code change is only to fix the compile error and no more.
</constraints>

<knowledge>
Sometimes imports need to added or replaced.
Sometimes the fix for the error requires a change to another location in the file than the snippet where the error is located.
</knowledge>


<requirements>
Requirement 0: File changes are grouped by file, between [Change Start $full_filepath] and [Change End $full_filepath], where $full_filepath is the full path to the filename to change, NOT angle brackets like <Change Start $full_filepath> and <Change End $full_filepath>.
Requirement 1: A file change contains one or more code change blocks:
  - A code change block is a paired find and replace block with find between [Find Start] and [Find End] and replace between [Replace Start] and [Replace End]
  - The find block has to be present in the given file, otherwise we're unable to apply the replacement or fix the compile error
  - The replace block has to be different from the find block in the same code change block, otherwise it's a no op, and guaranteed NOT to be able to fix the compile error
Requirement 2: File changes include the code change blocks ONLY, not including the explanation or quoting anything from the constraints, requirements or user feedback sections.
Requirement 3: Apply each Find and Replace Block and validate the results are as expected.
Requirement 4: Validate Syntax of file is valid after applying Find and Replace Blocks. *DO NOT* break syntax.
Requirement 5: Each line in the find block between [Find Start] and [Find End] must have the same number of blanks at the beginning of the line as the original file.
Requirement 6: Please keep the Find and Replace blocks separate.
Requirement 7: Code change in find block must not have unbalanced parentheses.
Requirement 8: Use separate find blocks even if the same code change is repeated on separate lines.
Requirement 9: Retain fully qualified variable names.
Requirement 10: Do not swap find and replace blocks.
Requirement 11: Verify that the find block does exist in the file contents.
Requirement 12: Changes should be holistic. For this you might need multiple Find and Replace blocks.
Requirement 13: The code inside a Find and Replace block needs to have the same level of indentation as the code in the file.
Requirement 14: The code inside the Replace block should be functionally equivalent to the code inside the Find block. 
Requirement 15: The code inside the Replace block should use public java 17 APIs when possible.
Requirement 16: The code inside the Replace block should remove any usage of deprecated methods when possible.
Requirement 17: Focus on solving the error message related to the snippet provided. Do not try to solve other issues.
Requirement 18: Do not rename classes, functions, or modules.
</requirements>

Here is an example output:
<example_output>
Explanation:
- I'm making this change because blabla.
- It meets the constraints and requirements sections in that blabla.
- It incorporates the user feedback in that blabla. (Note that this section is optional when it's the first message from the user)

[Change Start FULL_FILENAME]
[Find Start]
FIND_BLOCK_1
[Find End]
[Replace Start]
REPLACE_BLOCK_1
[Replace End]

[Find Start]
FIND_BLOCK_2
[Find End]
[Replace Start]
REPLACE_BLOCK_2
[Replace End]
[Change End FULL_FILENAME]
</example_output>

I see a java compilation error while compiling a Maven Java application that I have partially upgraded to Java 17.

To provide information about the application setup, here is the `{project_path}` file of the application:

```xml
{FILE__project_content}
```

This is the java file {file_path} where the error is raised:

```java
{FILE__file_content}
```


Here is the compilation error:

```
{compile_error}
```

This is the snippet around where the compilation error is located in above file (line number: {line_number}, column number: {column_number}).
Keep in mind that it is also possible that the fix for the error requires a change to another location in the file.
```java
{code_snippet}
```
"""


OFFICIAL_MAVEN_PROJECT_TEMPLATE_PROMPT = """You are a Java programmer.
You are a skilled debugger of Java applications.
You are trying to resolve a build error.
Use knowledge and explain how all constraints, requirements are satisfied before making the code change.
Given the build error and the `pom.xml` file, output a set of changes that I can apply to the `pom.xml` file to get new file content without compile error.

Think step by step and provide an explanation of the changes before the code changes.
All constraints and requirements must be followed.


<constraints>
- Explanation must match code change.
- The code change is only to fix the compile error and no more.
- The projects needs to be build in Java 17. Changing the java version to something other than 17 is not an option.
</constraints>


<requirements>
Requirement 0: File changes are grouped by file, between [Change Start $full_filepath] and [Change End $full_filepath], where $full_filepath is the full path to the filename to change, NOT angle brackets like <Change Start $full_filepath> and <Change End $full_filepath>.
Requirement 1: A file change contains one or more code change blocks:
  - A code change block is a paired find and replace block with find between [Find Start] and [Find End] and replace between [Replace Start] and [Replace End]
  - The find block has to be present in the given file, otherwise we're unable to apply the replacement or fix the compile error
  - The replace block has to be different from the find block in the same code change block, otherwise it's a no op, and guaranteed NOT to be able to fix the compile error
Requirement 2: File changes include the code change blocks ONLY, not including the explanation or quoting anything from the constraints, requirements or user feedback sections.
Requirement 3: Apply each Find and Replace Block and validate the results are as expected.
Requirement 4: Validate Syntax of file is valid after applying Find and Replace Blocks. *DO NOT* break syntax.
Requirement 5: Each line in the find block between [Find Start] and [Find End] must have the same number of blanks at the beginning of the line as the original file.
Requirement 6: Please keep the Find and Replace blocks separate.
Requirement 7: Code change in find block must not have unbalanced parentheses.
Requirement 8: Use separate find blocks even if the same code change is repeated on separate lines.
Requirement 9: Retain fully qualified variable names.
Requirement 10: Do not swap find and replace blocks.
Requirement 11: Verify that the find block does exist in the file contents.
Requirement 12: Changes should be holistic. For this you might need multiple Find and Replace blocks.
Requirement 13: The code inside a Find and Replace block needs to have the same level of indentation as the code in the file.
Requirement 14: The projects needs to be build in Java 17. Changing the java version to something other than 17 is not an option.
</requirements>

Here is an example output:
<example_output>
Explanation:
- I'm making this change because blabla.
- It meets the constraints and requirements sections in that blabla.
- It incorporates the user feedback in that blabla. (Note that this section is optional when it's the first message from the user)

[Change Start FULL_FILENAME]
[Find Start]
FIND_BLOCK_1
[Find End]
[Replace Start]
REPLACE_BLOCK_1
[Replace End]

[Find Start]
FIND_BLOCK_2
[Find End]
[Replace Start]
REPLACE_BLOCK_2
[Replace End]
[Change End FULL_FILENAME]
</example_output>

I am currently migration a Java 8 Maven application to Java 17.

Here is the `{project_path}` file which is causing the error:

```xml
{FILE__project_content}
```

When I try to build it with Java 17 with `mvn clean verify` command, I get the following error:

```error
{compile_error}
```
"""


@dataclass(frozen=True)
class FindReplacePair:
    """One official SD-Feedback find/replace block pair."""

    find: str | None
    replace: str | None


@dataclass(frozen=True)
class ChangeGroup:
    """One ``[Change Start full/path]`` group."""

    path: str
    pairs: tuple[FindReplacePair, ...]


@dataclass(frozen=True)
class SDFeedbackParseResult:
    """Parsed official SD-Feedback LLM response."""

    groups: tuple[ChangeGroup, ...]
    parsed_content: str
    feedback: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return bool(self.groups) and not self.feedback


@dataclass(frozen=True)
class SDFeedbackPatchResult:
    """Result of applying parsed official SD-Feedback groups."""

    patched: dict[str, bool | None]
    feedback: tuple[str, ...] = ()
    files_modified: tuple[str, ...] = ()

    @property
    def any_patched(self) -> bool:
        return any(value is True for value in self.patched.values())


@dataclass(frozen=True)
class SDBuildData:
    """Prompt-facing build error view following JavaMigration's BuildData."""

    filename: str | None
    project: str
    line_number: int | None
    column_number: int | None
    error_message: str
    code_snippet: str | None = None
    error_code: str | None = None
    context: str | None = None
    related_files: tuple[str, ...] = ()
    requirements: str = ""


@dataclass(frozen=True)
class SDPromptRequest:
    """Prompt and message history for one SD-Feedback LLM call."""

    prompt: str
    messages: tuple[dict[str, str], ...] = ()
    prompt_kind: str = "official_sd_feedback_initial"


@dataclass(frozen=True)
class SDBuildSignature:
    """Comparable build-error signature approximating BuildData equality."""

    failure_type: str
    first_error_file: str | None
    first_error_line: int | None
    first_error_column: int | None
    first_error_message: str
    digest: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "failure_type": self.failure_type,
            "first_error_file": self.first_error_file,
            "first_error_line": self.first_error_line,
            "first_error_column": self.first_error_column,
            "first_error_message": self.first_error_message,
            "digest": self.digest,
        }


def parse_official_sd_response(text: str) -> SDFeedbackParseResult:
    """Parse grouped ``[Change]`` + paired ``[Find]/[Replace]`` blocks."""

    feedback: list[str] = []
    groups: list[ChangeGroup] = []
    parsed_content = ""
    grouped_blocks = _extract_paired_blocks(
        text,
        start_regex=r"\[Change Start [^\]]+\]",
        end_regex=r"\[Change End [^\]]+\]",
    )
    if not grouped_blocks:
        feedback.append(
            "Unable to get any file to change, please double check the formats for filenames."
        )

    for group_start, block, group_end in grouped_blocks:
        group = _get_group_name(group_start, group_end)
        if group is None:
            if len(block) > 10:
                feedback.append(
                    "Unable to get same filename from\n"
                    f"[Start]\n{group_start}\n[End]\n"
                    "and\n"
                    f"[Start]\n{group_end}\n[End]\n"
                    f"with the content\n[Start]\n{block}\n[End]"
                )
            continue
        pairs, block_feedback = _parse_find_replace_pairs(block)
        feedback.extend(block_feedback)
        if pairs:
            groups.append(ChangeGroup(path=group, pairs=tuple(pairs)))
            parsed_content += "\n".join(["", group_start, block, group_end])
        else:
            feedback.append(
                f"Unable to parse correctly for file `{group}`: Skip parsing\n"
                f"[Start]\n{block}\n[End]"
            )

    return SDFeedbackParseResult(
        groups=tuple(groups),
        parsed_content=parsed_content,
        feedback=tuple(feedback),
    )


def apply_official_sd_groups(
    groups: Sequence[ChangeGroup],
    workspace_or_repo: Any,
) -> SDFeedbackPatchResult:
    """Apply groups with JavaMigration's fuzzy find-block replacement behavior."""

    repo_dir = _repo_dir(workspace_or_repo)
    if repo_dir is None:
        return SDFeedbackPatchResult(
            patched={},
            feedback=("Repository directory is unavailable.",),
        )
    patched: dict[str, bool | None] = {}
    feedback: list[str] = []
    modified: list[str] = []
    for group in sorted(groups, key=lambda item: item.path):
        path = _resolve_group_path(repo_dir, group.path)
        if path is None or not path.exists() or not path.is_file():
            feedback.append(f"File to patch doesn't exist: `{group.path}`.")
            patched[group.path] = None
            continue
        content = path.read_text(encoding="utf-8", errors="replace")
        success = False
        seen: dict[str, str | None] = {}
        for pair in group.pairs:
            find = pair.find or ""
            replace = pair.replace or ""
            if find in seen:
                if seen[find] != replace:
                    feedback.append(
                        "\n".join(
                            [
                                "Same find block with different replace block!",
                                f"[Find Start]\n{find}\n[Find End]",
                                "==>",
                                f"[Replace Start]\n{seen[find]}\n[Replace End]vs",
                                f"[Replace Start]\n{replace}\n[Replace End]",
                            ]
                        )
                    )
                continue
            seen[find] = replace
            content, block_success, block_feedback = _apply_single_official_patch(
                content,
                pair,
            )
            feedback.extend(block_feedback)
            success = success or block_success
        if success:
            path.write_text(content, encoding="utf-8")
            modified.append(path.relative_to(repo_dir).as_posix())
        else:
            feedback.append(
                f"Find blocks are not found at all for `{group.path}`: "
                f"For all find blocks count = {len(group.pairs)}."
            )
        patched[group.path] = success
    return SDFeedbackPatchResult(
        patched=patched,
        feedback=tuple(feedback),
        files_modified=tuple(sorted(set(modified))),
    )


def collect_official_feedback(messages: Sequence[str]) -> str | None:
    """Wrap parser/writer/build feedback using JavaMigration's tags."""

    feedbacks: list[str] = []
    for msg in messages:
        text = str(msg or "").strip()
        if text:
            feedbacks.append(f"[Feedback Start]{text}[Feedback End]")
    return "\n".join(feedbacks) if feedbacks else None


def prepare_official_sd_prompt(
    *,
    repo_dir: Path,
    project_path: Path | None,
    build_data: SDBuildData,
    last_prompt_messages: Sequence[dict[str, str]] | None = None,
    last_llm_response: str | None = None,
    feedback: Sequence[str] = (),
    restart_messages_len_gt: int = OFFICIAL_RESTART_MESSAGES_LEN_GT,
    extra_context: str = "",
) -> SDPromptRequest:
    """Build the JavaMigration prompt or feedback retry prompt."""

    messages = list(last_prompt_messages or [])
    if feedback:
        if not (
            restart_messages_len_gt and len(messages) > int(restart_messages_len_gt)
        ):
            retry_messages = [
                *messages,
                {"role": "assistant", "content": str(last_llm_response or "")},
            ]
            details = collect_official_feedback(feedback) or ""
            prompt = (
                "The response is incorrect, as it doesn't fix the build error. "
                "Please generate a full solution again.\n"
                "Below are details:\n"
                f"{details}"
            )
            return SDPromptRequest(
                prompt=prompt,
                messages=tuple(retry_messages),
                prompt_kind="official_sd_feedback_retry",
            )

    project = Path(build_data.project) if build_data.project else (project_path or repo_dir / "pom.xml")
    project_content = _read_text(project)
    file_content = ""
    if build_data.filename:
        file_content = _read_text(Path(build_data.filename))
    template = (
        OFFICIAL_MAVEN_TEMPLATE_PROMPT
        if build_data.filename and file_content
        else OFFICIAL_MAVEN_PROJECT_TEMPLATE_PROMPT
    )
    prompt = template.format(
        project_path=str(project),
        FILE__project_content=project_content,
        file_path=str(build_data.filename or ""),
        FILE__file_content=file_content,
        compile_error=build_data.error_message,
        line_number="" if build_data.line_number is None else build_data.line_number,
        column_number="" if build_data.column_number is None else build_data.column_number,
        code_snippet=build_data.code_snippet or "",
    )
    if extra_context.strip():
        prompt = f"{prompt}\n\n{extra_context.strip()}\n"
    return SDPromptRequest(
        prompt=prompt,
        messages=(),
        prompt_kind="official_sd_feedback_initial",
    )


def build_data_from_validation(
    validation: ValidationResult,
    *,
    repo_dir: Path,
) -> SDBuildData:
    """Extract the first Maven compile error, otherwise use project/POM error."""

    project = repo_dir / "pom.xml"
    text = validation.raw_output or validation.summary or "\n".join(validation.errors)
    parsed = _first_java_compile_error(text, repo_dir=repo_dir)
    if parsed is not None:
        file_path, line, column, message = parsed
        return SDBuildData(
            filename=str(file_path),
            project=str(project),
            line_number=line,
            column_number=column,
            error_message=message or (validation.summary or "build error"),
            code_snippet=_code_snippet(file_path, line, before=min(5, line), after=5),
            error_code=validation.summary,
        )
    return SDBuildData(
        filename=None,
        project=str(project),
        line_number=None,
        column_number=None,
        error_message=text[-12_000:] or validation.summary or "build error",
        error_code=validation.summary,
    )


def signature_from_validation(
    validation: ValidationResult,
    *,
    repo_dir: Path,
) -> SDBuildSignature:
    """Comparable signature for JavaMigration ERRORS_DIFFERENT_FROM_BEFORE."""

    build_data = build_data_from_validation(validation, repo_dir=repo_dir)
    digest_source = "\n".join(
        [
            str(validation.summary or ""),
            str(build_data.filename or ""),
            str(build_data.line_number or ""),
            str(build_data.column_number or ""),
            str(build_data.error_message or "")[:2000],
        ]
    )
    import hashlib

    digest = hashlib.sha1(digest_source.encode("utf-8")).hexdigest()[:16]
    return SDBuildSignature(
        failure_type=str(validation.summary or "build_failure"),
        first_error_file=build_data.filename,
        first_error_line=build_data.line_number,
        first_error_column=build_data.column_number,
        first_error_message=build_data.error_message,
        digest=digest,
    )


def apply_official_jdk17_seed(workspace_or_repo: Any) -> tuple[str, ...]:
    """Apply JavaMigration's mandatory Java 17 Maven seed rewrite to all POMs."""

    repo_dir = _repo_dir(workspace_or_repo)
    if repo_dir is None:
        raise ValueError("repository directory unavailable")
    root_pom = repo_dir / "pom.xml"
    if not root_pom.exists():
        raise ValueError(f"No `pom.xml` file found in repository root dir {repo_dir}.")
    modified: list[str] = []
    for raw_path in sorted(glob.glob(str(repo_dir / "**" / "pom.xml"), recursive=True)):
        pom_path = Path(raw_path)
        before = pom_path.read_text(encoding="utf-8", errors="replace")
        _update_jdk_related_pom(pom_path)
        after = pom_path.read_text(encoding="utf-8", errors="replace")
        if after != before:
            modified.append(pom_path.relative_to(repo_dir).as_posix())
    return tuple(modified)


def build_sd_feedback_extra_context(
    *,
    read_only_context: Sequence[dict[str, Any]] = (),
    stigmergic_context: dict[str, Any] | None = None,
) -> str:
    """Append non-official context without changing the official block format."""

    parts: list[str] = []
    if read_only_context:
        import json

        parts.append(
            "<read_only_tool_context>\n"
            + json.dumps(list(read_only_context), ensure_ascii=False, indent=2, sort_keys=True)[
                :20_000
            ]
            + "\n</read_only_tool_context>"
        )
    if stigmergic_context:
        import json

        parts.append(
            "<stigmergic_context>\n"
            + json.dumps(stigmergic_context, ensure_ascii=False, indent=2, sort_keys=True)[
                :20_000
            ]
            + "\n</stigmergic_context>"
        )
    return "\n\n".join(parts)


def _extract_paired_blocks(
    text: str,
    *,
    start_regex: str,
    end_regex: str,
) -> list[tuple[str, str, str]]:
    pattern = re.compile(rf"({start_regex})(.*?)({end_regex})", re.DOTALL)
    return [(a, b, c) for a, b, c in pattern.findall(text or "")]


def _get_group_name(group_start: str, group_end: str) -> str | None:
    names: set[str | None] = set()
    for group in (group_start, group_end):
        value = group.rstrip().split(" ")[-1]
        value = re.sub(r"^[`\[<|\(]+", "", value)
        value = re.sub(r"[`\]>|\)]+$", "", value)
        names.add(value if "." in value else None)
    if len(names) == 1:
        name = next(iter(names))
        if name is not None:
            return name
    return None


def _parse_find_replace_pairs(block: str) -> tuple[list[FindReplacePair], list[str]]:
    find_blocks = _extract_paired_blocks(
        block,
        start_regex=r"\[Find Start\]",
        end_regex=r"\[Find End\]",
    )
    replace_blocks = _extract_paired_blocks(
        block,
        start_regex=r"\[Replace Start\]",
        end_regex=r"\[Replace End\]",
    )
    feedback: list[str] = []
    if len(find_blocks) != len(replace_blocks):
        feedback.append(
            f"Number of find vs replace blocks are not the same "
            f"{len(find_blocks)} != {len(replace_blocks)}:\n"
            f"[Find Block Start]\n{find_blocks}\n[Find Block End]\n"
            f"[Replace Block Start]\n{replace_blocks}\n[Replace Block End]"
        )
        return [], feedback
    pairs: list[FindReplacePair] = []
    for find, replace in zip(find_blocks, replace_blocks):
        find_content = _maybe_strip(find[1])
        replace_content = _maybe_strip(replace[1])
        if find_content == replace_content:
            feedback.append(
                f"Find and replace blocks are the same:\n"
                f"[Find Start]\n{find[1]}\n[Find End]\n"
                "vs\n"
                f"[Replace Start]\n{replace[1]}\n[Replace End]"
            )
            continue
        pairs.append(FindReplacePair(find=find_content, replace=replace_content))
    return pairs, feedback


def _maybe_strip(value: str) -> str:
    return str(value).strip()


def _apply_single_official_patch(
    content: str,
    pair: FindReplacePair,
) -> tuple[str, bool, list[str]]:
    find = pair.find or ""
    replace = pair.replace or ""
    lines = [line.strip() for line in find.splitlines()]
    lines = [re.escape(line) for line in lines if line]
    pattern = r"\s*".join(lines)
    feedback: list[str] = []
    try:
        compiled_pattern = re.compile(pattern, re.MULTILINE)
        if compiled_pattern.search(content) is not None:
            char = "\\"
            if char in replace:
                for n in range(2, 100):
                    if (char * n) not in content:
                        break
                else:
                    raise ValueError(f"Too many {char} in file.")
                n *= 2

                def _escape(value: str) -> str:
                    return value.replace(char, char * n)

                def _escape_back(value: str) -> str:
                    return value.replace(char * (n // 2), char)

                return (
                    _escape_back(compiled_pattern.sub(_escape(replace), content)),
                    True,
                    feedback,
                )
            return compiled_pattern.sub(replace, content), True, feedback
    except Exception as error:  # noqa: BLE001
        feedback.append(
            "Replacing block raises an error\n"
            f"[Error Start]\n{error}\n[Error End]\n"
            "when trying to replace block\n"
            f"[Find Start]\n{find}\n[Find End]\n"
            "with block"
            f"[Replace Start]\n{replace}\n[Replace End]"
        )
    return content, False, feedback


def _first_java_compile_error(
    text: str,
    *,
    repo_dir: Path,
) -> tuple[Path, int, int | None, str] | None:
    patterns = (
        re.compile(r"^\[ERROR\]\s*(.+\.java):\[(\d+),(\d+)\]\s*(.*)$"),
        re.compile(r"^(.+\.java):(\d+):\s+error:(.*)$"),
    )
    for line in (text or "").splitlines():
        for pattern in patterns:
            match = pattern.search(line)
            if not match:
                continue
            if pattern is patterns[0]:
                filename = match.group(1)
                line_number = int(match.group(2))
                column = int(match.group(3))
                message = match.group(4).rstrip()
            else:
                filename = match.group(1)
                line_number = int(match.group(2))
                column = None
                message = match.group(3).rstrip()
            path = _resolve_error_file(repo_dir, filename)
            if path is not None:
                return path, line_number, column, message
    return None


def _resolve_error_file(repo_dir: Path, filename: str) -> Path | None:
    raw = Path(str(filename))
    candidates: list[Path] = []
    if raw.is_absolute():
        candidates.append(raw)
    candidates.append(repo_dir / str(filename).lstrip("/"))
    suffix = raw.as_posix().split("/src/", 1)
    if len(suffix) == 2:
        candidates.append(repo_dir / "src" / suffix[1])
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
            resolved.relative_to(repo_dir.resolve())
        except ValueError:
            continue
        if resolved.is_file():
            return resolved
    basename = raw.name
    for path in repo_dir.rglob(basename):
        if path.is_file() and path.as_posix().endswith(raw.as_posix().lstrip("/")):
            return path
    for path in repo_dir.rglob(basename):
        if path.is_file():
            return path
    return None


def _code_snippet(path: Path, line_number: int, *, before: int, after: int) -> str:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    start = max(1, int(line_number) - int(before))
    end = min(len(lines), int(line_number) + int(after))
    snippet: list[str] = []
    for idx in range(start, end + 1):
        text = lines[idx - 1]
        if idx == int(line_number):
            text = f"{text}  //  Compilation error is at this line."
        snippet.append(text)
    return "\n".join(snippet)


def _repo_dir(workspace_or_repo: Any) -> Path | None:
    if isinstance(workspace_or_repo, Path):
        return workspace_or_repo
    metadata = getattr(workspace_or_repo, "metadata", None)
    if isinstance(metadata, dict) and metadata.get("repo_dir"):
        return Path(str(metadata["repo_dir"])).expanduser().resolve()
    root = getattr(workspace_or_repo, "root", None)
    if root is not None:
        root_path = Path(root)
        return (root_path / "repo").resolve() if (root_path / "repo").exists() else root_path.resolve()
    repo = getattr(workspace_or_repo, "repo_dir", None)
    return Path(repo).expanduser().resolve() if repo is not None else None


def _resolve_group_path(repo_dir: Path, group: str) -> Path | None:
    raw = Path(str(group))
    candidates: list[Path] = []
    if raw.is_absolute():
        candidates.append(raw)
        # JavaMigration asks the model to emit full file paths. In this harness
        # the LLM sees the parent/current branch path, while we apply into a
        # freshly forked candidate branch. Preserve the official absolute-path
        # contract, but remap the path segment below the repository root.
        parts = raw.parts
        if "repo" in parts:
            repo_index = len(parts) - 1 - list(reversed(parts)).index("repo")
            suffix = Path(*parts[repo_index + 1 :])
            candidates.append(repo_dir / suffix)
    candidates.append(repo_dir / str(group).lstrip("/"))
    for candidate in candidates:
        resolved = candidate.resolve()
        try:
            resolved.relative_to(repo_dir.resolve())
        except ValueError:
            continue
        return resolved
    return None


def _read_text(path: Path, *, max_chars: int = 120_000) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:max_chars]
    except OSError:
        return ""


def _update_jdk_related_pom(pom_path: Path) -> None:
    parser = ET.XMLParser(encoding="utf-8")
    tree = ET.parse(pom_path, parser=parser)
    root = tree.getroot()
    for property_name in (
        "maven.compiler.source",
        "maven.compiler.target",
        "maven.compiler.release",
    ):
        _update_jdk_property(root, property_name, "17", forced=True)
    for property_name in (
        "java.version",
        "jdk.version",
        "javaVersion",
        "jdkversion",
        "java.testversion",
    ):
        _update_jdk_property(root, property_name, "17", forced=False)
    _update_jdk_plugin_configuration(
        root,
        "org.apache.maven.plugins",
        "maven-compiler-plugin",
    )
    ET.register_namespace("", _MAVEN_NS)
    tree.write(pom_path, default_namespace=None)


def _tag(name: str) -> str:
    return f"{{{_MAVEN_NS}}}{name}"


def _strip_tag(tag: str) -> str:
    return str(tag).replace(f"{{{_MAVEN_NS}}}", "")


def _find_or_create_direct(root: ET.Element, name: str) -> ET.Element:
    child = root.find(f"xmlns:{name}", namespaces=_NS)
    if child is None:
        child = ET.Element(_tag(name))
        root.append(child)
    return child


def _update_jdk_property(
    root: ET.Element,
    property_name: str,
    property_version: str,
    *,
    forced: bool,
) -> None:
    properties = root.find(".//xmlns:properties", namespaces=_NS)
    if properties is None:
        if not forced:
            return
        properties = ET.Element(_tag("properties"))
        root.append(properties)
    found = False
    for child in list(properties):
        if _strip_tag(child.tag) == property_name:
            child.text = property_version
            found = True
            break
    if not found and forced:
        new_property = ET.Element(_tag(property_name))
        new_property.text = property_version
        properties.append(new_property)


def _update_jdk_plugin_configuration(
    root: ET.Element,
    groupid: str,
    artifactid: str,
) -> None:
    plugins = root.findall(".//xmlns:plugins", namespaces=_NS)
    if not plugins:
        build = root.find(".//xmlns:build", namespaces=_NS)
        if build is None:
            build = ET.Element(_tag("build"))
            root.append(build)
        plugins_block = ET.Element(_tag("plugins"))
        build.append(plugins_block)
        _append_compiler_plugin(plugins_block, groupid, artifactid)
        return
    found = False
    for plugin in root.findall(".//xmlns:plugin", namespaces=_NS):
        artifact_text = None
        configuration = None
        for child in list(plugin):
            tag = _strip_tag(child.tag)
            if tag == "artifactId":
                artifact_text = child.text
            elif tag == "configuration":
                configuration = child
        if artifact_text != artifactid:
            continue
        found = True
        if configuration is None:
            configuration = _compiler_configuration_block()
            plugin.append(configuration)
            continue
        present: set[str] = set()
        for item in list(configuration):
            tag = _strip_tag(item.tag)
            if tag in {"source", "target", "release"}:
                item.text = "17"
                present.add(tag)
        for tag in ("source", "target", "release"):
            if tag not in present:
                child = ET.Element(tag)
                child.text = "17"
                configuration.append(child)
    if not found:
        _append_compiler_plugin(plugins[0], groupid, artifactid)


def _compiler_configuration_block() -> ET.Element:
    return ET.XML(
        "<configuration>\n <source>17</source> <target>17</target>  <release>17</release>\n</configuration>\n"
    )


def _append_compiler_plugin(
    plugins_block: ET.Element,
    groupid: str,
    artifactid: str,
) -> None:
    plugin = ET.Element("plugin")
    group = ET.Element("groupId")
    group.text = groupid
    artifact = ET.Element("artifactId")
    artifact.text = artifactid
    plugin.extend([group, artifact, _compiler_configuration_block()])
    plugins_block.append(plugin)


__all__ = [
    "ChangeGroup",
    "FindReplacePair",
    "OFFICIAL_BUILD_ERRORS_DO_NOT_CHANGE_AS_FEEDBACK",
    "OFFICIAL_MAVEN_PROJECT_TEMPLATE_PROMPT",
    "OFFICIAL_MAVEN_TEMPLATE_PROMPT",
    "OFFICIAL_RESTART_MESSAGES_LEN_GT",
    "OFFICIAL_SD_FEEDBACK_SOURCE_URL",
    "OFFICIAL_TARGET_JAVA",
    "SDBuildData",
    "SDBuildSignature",
    "SDFeedbackParseResult",
    "SDFeedbackPatchResult",
    "SDPromptRequest",
    "apply_official_jdk17_seed",
    "apply_official_sd_groups",
    "build_data_from_validation",
    "build_sd_feedback_extra_context",
    "collect_official_feedback",
    "parse_official_sd_response",
    "prepare_official_sd_prompt",
    "signature_from_validation",
]
