"""Parse and atomically apply model-produced SEARCH/REPLACE edits."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import PurePosixPath
from types import MappingProxyType
from typing import Mapping, Sequence


class EditParseError(ValueError):
    """The model response does not contain well-formed edits."""


class EditApplicationError(ValueError):
    """An edit cannot be applied unambiguously to the visible sources."""


@dataclass(frozen=True, slots=True)
class SearchReplaceEdit:
    path: str
    search: str
    replacement: str

    def __post_init__(self) -> None:
        normalized = _normalize_path(self.path)
        if not self.search:
            raise EditParseError("SEARCH content must not be empty")
        object.__setattr__(self, "path", normalized)


@dataclass(frozen=True, slots=True)
class AppliedRepair:
    edits: tuple[SearchReplaceEdit, ...]
    original_sources: Mapping[str, str]
    updated_sources: Mapping[str, str]
    changed_paths: tuple[str, ...]


_FENCED_BLOCK = re.compile(r"```[^\n`]*\n(.*?)(?:\n```|\Z)", re.DOTALL)


def _normalize_path(path: str) -> str:
    raw = path.strip().strip("'\"").replace("\\", "/")
    candidate = PurePosixPath(raw)
    if (
        not raw
        or candidate.as_posix() == "."
        or candidate.is_absolute()
        or ".." in candidate.parts
        or (candidate.parts and ":" in candidate.parts[0])
    ):
        raise EditParseError(f"unsafe repository-relative path: {path!r}")
    return candidate.as_posix()


def _response_blocks(response: str) -> list[str]:
    blocks = _FENCED_BLOCK.findall(response)
    return blocks if blocks else [response]


def parse_search_replace_edits(response: str) -> tuple[SearchReplaceEdit, ...]:
    """Extract ordered, de-duplicated SEARCH/REPLACE edits from a response."""
    edits: list[SearchReplaceEdit] = []
    seen: set[SearchReplaceEdit] = set()
    saw_marker = "<<<<<<< SEARCH" in response or ">>>>>>> REPLACE" in response

    for block in _response_blocks(response):
        lines = block.splitlines()
        current_path: str | None = None
        index = 0
        while index < len(lines):
            stripped = lines[index].strip()
            if stripped.startswith("### "):
                current_path = _normalize_path(stripped[4:])
                index += 1
                continue
            if stripped != "<<<<<<< SEARCH":
                index += 1
                continue
            if current_path is None:
                raise EditParseError("SEARCH block is missing a preceding '### path'")

            divider = _find_marker(lines, index + 1, "=======")
            end = _find_marker(lines, divider + 1, ">>>>>>> REPLACE")
            edit = SearchReplaceEdit(
                path=current_path,
                search="\n".join(lines[index + 1 : divider]),
                replacement="\n".join(lines[divider + 1 : end]),
            )
            if edit not in seen:
                edits.append(edit)
                seen.add(edit)
            index = end + 1

    if not edits:
        detail = "malformed" if saw_marker else "missing"
        raise EditParseError(f"{detail} SEARCH/REPLACE edit")
    return tuple(edits)


def _find_marker(lines: list[str], start: int, marker: str) -> int:
    for index in range(start, len(lines)):
        if lines[index].strip() == marker:
            return index
    raise EditParseError(f"SEARCH/REPLACE edit is missing {marker!r}")


def _occurrences(source: str, needle: str) -> list[tuple[int, int]]:
    found: list[tuple[int, int]] = []
    start = 0
    while True:
        offset = source.find(needle, start)
        if offset < 0:
            return found
        first_line = source.count("\n", 0, offset) + 1
        last_line = first_line + needle.count("\n")
        found.append((offset, last_line))
        start = offset + max(1, len(needle))


def _inside_intervals(
    source: str,
    offset_and_end: tuple[int, int],
    intervals: Sequence[tuple[int, int]],
) -> bool:
    offset, last_line = offset_and_end
    first_line = source.count("\n", 0, offset) + 1
    return any(start <= first_line and last_line <= end for start, end in intervals)


def apply_search_replace_edits(
    sources: Mapping[str, str],
    edits: Sequence[SearchReplaceEdit],
    *,
    allowed_intervals: Mapping[str, Sequence[tuple[int, int]]] | None = None,
) -> AppliedRepair:
    """Apply all edits in memory, failing atomically on an invalid edit.

    A SEARCH block must identify exactly one eligible occurrence. No caller-owned
    mapping is changed when any edit fails.
    """
    if not edits:
        raise EditApplicationError("at least one edit is required")
    originals: dict[str, str] = {}
    for path, content in sources.items():
        normalized_path = _normalize_path(path)
        if normalized_path in originals:
            raise EditApplicationError(
                f"multiple source paths normalize to {normalized_path!r}"
            )
        originals[normalized_path] = content
    updated = dict(originals)
    changed_paths: list[str] = []
    normalized_intervals: dict[str, tuple[tuple[int, int], ...]] | None = None
    if allowed_intervals is not None:
        normalized_intervals = {}
        for path, intervals in allowed_intervals.items():
            normalized_path = _normalize_path(path)
            checked = tuple(intervals)
            if any(start < 1 or end < start for start, end in checked):
                raise EditApplicationError(
                    f"invalid allowed interval for {normalized_path}"
                )
            normalized_intervals[normalized_path] = checked

    for edit in edits:
        if edit.path not in updated:
            raise EditApplicationError(f"edited file is not visible: {edit.path}")
        source = updated[edit.path]
        matches = _occurrences(source, edit.search)
        if normalized_intervals is not None:
            if edit.path not in normalized_intervals:
                raise EditApplicationError(
                    f"edited file has no authorized interval: {edit.path}"
                )
            matches = [
                match
                for match in matches
                if _inside_intervals(source, match, normalized_intervals[edit.path])
            ]
        if not matches:
            raise EditApplicationError(f"SEARCH content not found in {edit.path}")
        if len(matches) != 1:
            raise EditApplicationError(f"SEARCH content is ambiguous in {edit.path}")
        offset, _ = matches[0]
        updated[edit.path] = (
            source[:offset] + edit.replacement + source[offset + len(edit.search) :]
        )
        if edit.path not in changed_paths:
            changed_paths.append(edit.path)

    changed_paths = [path for path in changed_paths if updated[path] != originals[path]]
    if not changed_paths:
        raise EditApplicationError("edits do not change the repository")
    return AppliedRepair(
        edits=tuple(edits),
        original_sources=MappingProxyType(originals),
        updated_sources=MappingProxyType(updated),
        changed_paths=tuple(changed_paths),
    )
