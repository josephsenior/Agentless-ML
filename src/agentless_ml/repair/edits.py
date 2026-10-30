"""Parse and atomically apply text edits and explicit file operations."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import PurePosixPath
from types import MappingProxyType
from typing import Collection, Mapping, Sequence


class EditParseError(ValueError):
    """The model response does not contain well-formed edits."""


class EditApplicationError(ValueError):
    """An edit cannot be applied unambiguously to the visible sources."""


@dataclass(frozen=True, slots=True)
class SearchReplaceEdit:
    """One edit. An empty ``search`` creates a new file whose content is ``replacement``."""

    path: str
    search: str
    replacement: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "path", _normalize_path(self.path))

    @property
    def creates_file(self) -> bool:
        return not self.search


@dataclass(frozen=True, slots=True)
class DeleteFile:
    path: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "path", _normalize_path(self.path))


@dataclass(frozen=True, slots=True)
class RenameFile:
    path: str
    destination: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "path", _normalize_path(self.path))
        object.__setattr__(self, "destination", _normalize_path(self.destination))


RepairEdit = SearchReplaceEdit | DeleteFile | RenameFile


@dataclass(frozen=True, slots=True)
class AppliedRepair:
    edits: tuple[RepairEdit, ...]
    original_sources: Mapping[str, str]
    updated_sources: Mapping[str, str]
    changed_paths: tuple[str, ...]
    created_paths: tuple[str, ...] = ()
    renamed_paths: tuple[tuple[str, str], ...] = ()


_FENCED_BLOCK = re.compile(r"```[^\n`]*\n(.*?)(?:\n```|\Z)", re.DOTALL)


def _normalize_path(path: str) -> str:
    raw = path.strip().strip("'\"").replace("\\", "/")
    candidate = PurePosixPath(raw)
    if (
        not raw
        or candidate.as_posix() == "."
        or candidate.is_absolute()
        or ".." in candidate.parts
        or any(part.casefold() == ".git" for part in candidate.parts)
        or any(ord(char) < 32 or char == '"' for char in raw)
        or (candidate.parts and ":" in candidate.parts[0])
    ):
        raise EditParseError(f"unsafe repository-relative path: {path!r}")
    return candidate.as_posix()


def _response_blocks(response: str) -> list[str]:
    blocks = _FENCED_BLOCK.findall(response)
    return blocks if blocks else [response]


def parse_search_replace_edits(response: str) -> tuple[RepairEdit, ...]:
    """Extract ordered, de-duplicated edits and file operations from a response."""
    edits: list[RepairEdit] = []
    seen: set[RepairEdit] = set()
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
                if stripped.startswith(("DELETE FILE", "RENAME FILE")):
                    if current_path is None:
                        raise EditParseError("file operation requires a preceding '### path'")
                    if stripped == "DELETE FILE":
                        operation: RepairEdit = DeleteFile(current_path)
                    elif stripped.startswith("RENAME FILE TO "):
                        operation = RenameFile(current_path, stripped[len("RENAME FILE TO "):])
                    else:
                        raise EditParseError("malformed file operation")
                    if operation not in seen:
                        edits.append(operation)
                        seen.add(operation)
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
    edits: Sequence[RepairEdit],
    *,
    allowed_intervals: Mapping[str, Sequence[tuple[int, int]]] | None = None,
    existing_paths: Collection[str] | None = None,
) -> AppliedRepair:
    """Apply all edits in memory, failing atomically on an invalid edit.

    A SEARCH block must identify exactly one eligible occurrence. No caller-owned
    mapping is changed when any edit fails.

    An empty SEARCH block creates a new file. ``existing_paths`` is every path the
    repository already tracks; creation is refused without it, and for any path it
    contains (compared case-insensitively, as a Windows or macOS checkout would).
    A created file has no interval: all of it is new, so later edits in the same
    response may change any part of it. It appears in ``updated_sources`` only.
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
    created_paths: list[str] = []
    renamed_paths: list[tuple[str, str]] = []
    structural_paths: set[str] = set()
    taken = (
        None
        if existing_paths is None
        else {_normalize_path(path).casefold() for path in existing_paths}
        | {path.casefold() for path in originals}
    )
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
        if isinstance(edit, (DeleteFile, RenameFile)):
            if edit.path not in originals or edit.path not in updated:
                raise EditApplicationError(f"file operation requires an existing visible file: {edit.path}")
            if edit.path in structural_paths:
                raise EditApplicationError(f"multiple file operations on {edit.path}")
            if normalized_intervals is not None and not normalized_intervals.get(edit.path):
                raise EditApplicationError(f"file operation has no authorized interval: {edit.path}")
            if isinstance(edit, RenameFile):
                _require_new_path(edit.destination, taken)
                updated[edit.destination] = updated[edit.path]
                assert taken is not None
                taken.add(edit.destination.casefold())
                renamed_paths.append((edit.path, edit.destination))
                structural_paths.add(edit.destination)
                if normalized_intervals is not None:
                    normalized_intervals[edit.destination] = normalized_intervals[edit.path]
                changed_paths.append(edit.destination)
            del updated[edit.path]
            structural_paths.add(edit.path)
            if edit.path not in changed_paths:
                changed_paths.append(edit.path)
            continue
        if edit.creates_file:
            if edit.path in created_paths:
                raise EditApplicationError(f"file is created more than once: {edit.path}")
            if edit.path in updated:
                raise EditApplicationError(
                    f"SEARCH content must not be empty for an existing file: {edit.path}"
                )
            if taken is None:
                raise EditApplicationError(
                    "file creation requires the repository's tracked paths"
                )
            if edit.path.casefold() in taken:
                raise EditApplicationError(
                    f"cannot create a file that already exists: {edit.path}"
                )
            _require_new_path(edit.path, taken)
            content = edit.replacement
            if content and not content.endswith("\n"):
                content += "\n"
            updated[edit.path] = content
            taken.add(edit.path.casefold())
            created_paths.append(edit.path)
            changed_paths.append(edit.path)
            continue
        if edit.path not in updated:
            raise EditApplicationError(f"edited file is not visible: {edit.path}")
        source = updated[edit.path]
        matches = _occurrences(source, edit.search)
        found_in_source = bool(matches)
        if normalized_intervals is not None and edit.path not in created_paths:
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
            if found_in_source:
                raise EditApplicationError(
                    f"SEARCH content is outside authorized intervals in {edit.path}"
                )
            raise EditApplicationError(f"SEARCH content not found in {edit.path}")
        if len(matches) != 1:
            raise EditApplicationError(f"SEARCH content is ambiguous in {edit.path}")
        offset, _ = matches[0]
        if normalized_intervals is not None and edit.path not in created_paths:
            first_line = source.count("\n", 0, offset) + 1
            last_line = matches[0][1]
            new_last = first_line + edit.replacement.count("\n")
            delta = edit.replacement.count("\n") - edit.search.count("\n")
            # Later SEARCH blocks refer to the evolving source. Carry the
            # original authorization regions along with insertions/deletions.
            shifted = []
            for start, end in normalized_intervals[edit.path]:
                if end < first_line:
                    shifted.append((start, end))
                elif start > last_line:
                    shifted.append((start + delta, end + delta))
                else:
                    shifted.append((min(start, first_line), max(new_last, end + delta)))
            normalized_intervals[edit.path] = tuple(shifted)
        updated[edit.path] = (
            source[:offset] + edit.replacement + source[offset + len(edit.search) :]
        )
        if edit.path not in changed_paths:
            changed_paths.append(edit.path)

    changed_paths = [
        path
        for path in changed_paths
        if path not in originals or path not in updated or updated[path] != originals[path]
    ]
    if not changed_paths:
        raise EditApplicationError("edits do not change the repository")
    return AppliedRepair(
        edits=tuple(edits),
        original_sources=MappingProxyType(originals),
        updated_sources=MappingProxyType(updated),
        changed_paths=tuple(changed_paths),
        created_paths=tuple(created_paths),
        renamed_paths=tuple(renamed_paths),
    )


def _require_new_path(path: str, taken: set[str] | None) -> None:
    if taken is None:
        raise EditApplicationError("new destination requires the repository's tracked paths")
    folded = path.casefold()
    if any(folded == other or folded.startswith(other + "/") or other.startswith(folded + "/") for other in taken):
        raise EditApplicationError(f"destination collides with an existing path: {path}")
