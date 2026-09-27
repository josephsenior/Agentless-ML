"""Parse localization responses and construct focused repair context."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from pathlib import PurePosixPath
from typing import Protocol

from agentless_ml.adapters.languages import (  # pyright: ignore[reportMissingTypeStubs]
    get_language_adapter,
)
from agentless_ml.schemas import FileNode  # pyright: ignore[reportMissingTypeStubs]


class ResolvedLocations(Protocol):
    """Structural type returned by language-specific location resolvers."""

    is_valid: bool
    context_intervals: Sequence[tuple[int, int]]


def extract_code_blocks(text: str) -> list[str]:
    """Extract unlabelled fenced blocks with published Agentless semantics."""
    matches = re.findall(r"```\n(.*?)\n```", text, re.DOTALL)
    if not matches and "```" in text:
        return [text.split("```", 1)[-1].strip()]
    return matches


def _normalize_location_path(
    raw_line: str,
    known: frozenset[str],
    repository_name: str | None,
) -> str | None:
    raw = raw_line.strip().strip("`'\"").replace("\\", "/")
    if not raw or raw.startswith(("#", "- ")):
        return None
    path = PurePosixPath(raw)
    if path.is_absolute() or ".." in path.parts:
        return None
    normalized = path.as_posix()
    # Prefer an exact tracked path. A repository can have a top-level package
    # with the same name, so stripping the display-only root prefix first is
    # ambiguous.
    if (
        repository_name
        and normalized not in known
        and normalized.startswith(repository_name + "/")
    ):
        normalized = normalized[len(repository_name) + 1 :]
    return normalized


def _is_new_location(
    raw_line: str,
    known: frozenset[str],
    selected: Sequence[str],
    repository_name: str | None,
    extension: str | tuple[str, ...],
) -> str | None:
    normalized = _normalize_location_path(raw_line, known, repository_name)
    if normalized is None:
        return None
    if normalized not in known or not normalized.endswith(extension):
        return None
    if normalized in selected:
        return None
    return normalized


def parse_file_locations(
    response: str,
    repository_paths: Sequence[str],
    *,
    repository_name: str | None = None,
    maximum_files: int = 5,
    extension: str | tuple[str, ...] = ".py",
) -> tuple[str, ...]:
    """Return ordered, known paths with the requested language extension.

    Published prompts display a repository-root component. Responses may retain
    or omit it, so an explicitly supplied repository name is stripped once.
    Unknown, unsafe, duplicate, wrong-extension and over-budget paths are rejected.
    """
    if maximum_files <= 0:
        raise ValueError("maximum_files must be positive")
    known = frozenset(PurePosixPath(path).as_posix() for path in repository_paths)
    selected: list[str] = []
    blocks = extract_code_blocks(response)
    candidates = blocks if blocks else [response]
    for block in candidates:
        for raw_line in block.splitlines():
            normalized = _is_new_location(
                raw_line,
                known,
                selected,
                repository_name,
                extension,
            )
            if normalized is None:
                continue
            selected.append(normalized)
            if len(selected) == maximum_files:
                return tuple(selected)
    return tuple(selected)


def parse_locations_for_files(
    blocks: Sequence[str],
    file_names: Sequence[str],
    *,
    keep_old_order: bool = False,
    extension: str | tuple[str, ...] = ".py",
) -> dict[str, list[str]]:
    """Associate model-returned location lines with known files."""
    results: dict[str, list[str]] = (
        {file_name: [] for file_name in file_names} if keep_old_order else {}
    )
    current_file_name: str | None = None
    for block in blocks:
        for line in block.splitlines():
            if line.strip().endswith(extension):
                current_file_name = line.strip()
            elif line.strip() and any(
                line.startswith(prefix)
                for prefix in (
                    "line:",
                    "function:",
                    "class:",
                    "variable:",
                    "method:",
                    "type:",
                    "constant:",
                    "field:",
                    "trait:",
                    "impl:",
                    "module:",
                )
            ):
                if current_file_name is not None and current_file_name in file_names:
                    results.setdefault(current_file_name, []).append(line)

    for file_name in file_names:
        results.setdefault(file_name, [])
    return {file_name: ["\n".join(results[file_name])] for file_name in results}


def resolve_locations(
    locations: str | Sequence[str],
    file_node: FileNode,
    source: str,
    *,
    context_window: int = 10,
    separate_intervals: bool = True,
    fine_grained_only: bool = False,
    remove_line_locations: bool = False,
) -> ResolvedLocations:
    """Resolve location strings to one-based inclusive line spans.

    The file's language decides the semantics: Python applies published Agentless
    v1.5.0 rules; the others use the language-neutral kind-and-name resolver.
    """
    if context_window < 0:
        raise ValueError("context_window must not be negative")
    return get_language_adapter(file_node.language).resolve_locations(
        locations,
        file_node,
        source,
        context_window=context_window,
        separate_intervals=separate_intervals,
        fine_grained_only=fine_grained_only,
        remove_line_locations=remove_line_locations,
    )


def _line_wrap_content(
    source: str,
    intervals: Sequence[tuple[int, int]],
    *,
    add_space: bool,
    no_line_number: bool,
    sticky_scroll: bool,
) -> str:
    lines = source.split("\n")
    active_intervals = list(intervals) or [(0, len(lines))]
    new_lines: list[str] = []
    previous_scopes: list[dict[str, int | str]] = []
    line_format = _line_format(add_space, no_line_number)

    for min_line, max_line in active_intervals:
        if min_line != 0:
            new_lines.append("...")
        scopes = _render_interval(
            lines,
            min_line,
            max_line,
            line_format,
            sticky_scroll,
            previous_scopes,
            new_lines,
        )
        previous_scopes = scopes
    if active_intervals[-1][1] != len(lines):
        new_lines.append("...")
    return "\n".join(new_lines)


def _line_format(add_space: bool, no_line_number: bool) -> str:
    if no_line_number:
        return "{line}"
    return "{line_number}| {line} " if add_space else "{line_number}|{line}"


def _update_scopes(
    scopes: list[dict[str, int | str]], line: str, index: int
) -> None:
    if not (line.startswith("class ") or line.strip().startswith("def ")):
        return
    indent_level = len(line) - len(line.lstrip())
    while scopes and int(scopes[-1]["indent_level"]) >= indent_level:
        scopes.pop()
    scopes.append({"line": line, "line_number": index, "indent_level": indent_level})


def _append_sticky_scopes(
    scopes: Sequence[dict[str, int | str]],
    previous_scopes: Sequence[dict[str, int | str]],
    index: int,
    line_format: str,
    new_lines: list[str],
) -> None:
    last_scope_line: int | None = None
    for scope_index, scope in enumerate(scopes):
        same_scope = (
            len(previous_scopes) > scope_index
            and previous_scopes[scope_index]["line_number"] == scope["line_number"]
        )
        if same_scope or index == scope["line_number"]:
            continue
        new_lines.append(
            line_format.format(
                line_number=int(scope["line_number"]) + 1,
                line=scope["line"],
            )
        )
        last_scope_line = int(scope["line_number"])
    if last_scope_line is not None and last_scope_line < index - 1:
        new_lines.append("...")


def _render_interval(
    lines: Sequence[str],
    min_line: int,
    max_line: int,
    line_format: str,
    sticky_scroll: bool,
    previous_scopes: Sequence[dict[str, int | str]],
    new_lines: list[str],
) -> list[dict[str, int | str]]:
    scopes: list[dict[str, int | str]] = []
    for index, line in enumerate(lines):
        if sticky_scroll:
            _update_scopes(scopes, line, index)
        if min_line != -1 and index < min_line - 1:
            continue
        if sticky_scroll and index == min_line - 1:
            _append_sticky_scopes(
                scopes, previous_scopes, index, line_format, new_lines
            )
        new_lines.append(line_format.format(line_number=index + 1, line=line))
        if max_line != -1 and index >= max_line - 1:
            break
    return scopes


def construct_selected_context(
    file_to_locations: Mapping[str, str | Sequence[str]],
    file_nodes: Mapping[str, FileNode],
    sources: Mapping[str, str],
    *,
    context_window: int = 10,
    separate_intervals: bool = True,
    fine_grained_only: bool = False,
    add_space: bool = False,
    sticky_scroll: bool = False,
    no_line_number: bool = True,
) -> tuple[str, dict[str, list[tuple[int, int]]]]:
    """Construct the focused multi-file source context used for repair."""
    context = ""
    file_intervals: dict[str, list[tuple[int, int]]] = {}
    for path, locations in file_to_locations.items():
        if path not in sources or path not in file_nodes:
            raise KeyError(f"missing selected file: {path}")
        resolved = resolve_locations(
            locations,
            file_nodes[path],
            sources[path],
            context_window=context_window,
            separate_intervals=separate_intervals,
            fine_grained_only=fine_grained_only,
        )
        if resolved.is_valid:
            wrapped = _line_wrap_content(
                sources[path],
                resolved.context_intervals,
                add_space=add_space,
                no_line_number=no_line_number,
                sticky_scroll=sticky_scroll,
            )
            context += f"### {path}\n{wrapped}\n\n\n"
            file_intervals[path] = list(resolved.context_intervals)
    return context, file_intervals
