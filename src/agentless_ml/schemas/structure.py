"""Language-neutral repository structure contracts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath


def _validate_span(start_line: int, end_line: int) -> None:
    if start_line < 1:
        raise ValueError("start_line must be at least 1")
    if end_line < start_line:
        raise ValueError("end_line must not precede start_line")


@dataclass(frozen=True, slots=True)
class SymbolNode:
    kind: str
    name: str
    qualified_name: str
    signature: str
    start_line: int
    end_line: int
    children: tuple["SymbolNode", ...] = ()

    def __post_init__(self) -> None:
        if not self.kind.strip() or not self.name.strip() or not self.qualified_name.strip():
            raise ValueError("symbol kind, name, and qualified_name must not be empty")
        _validate_span(self.start_line, self.end_line)
        for child in self.children:
            if child.start_line < self.start_line or child.end_line > self.end_line:
                raise ValueError(f"child symbol {child.qualified_name!r} lies outside its parent")


@dataclass(frozen=True, slots=True)
class FileNode:
    path: str
    language: str
    line_count: int
    symbols: tuple[SymbolNode, ...] = ()

    def __post_init__(self) -> None:
        normalized = PurePosixPath(self.path.replace("\\", "/"))
        if normalized.is_absolute() or ".." in normalized.parts:
            raise ValueError("file path must be repository-relative and traversal-free")
        if not normalized.parts or str(normalized) == ".":
            raise ValueError("file path must not be empty")
        if not self.language.strip():
            raise ValueError("language must not be empty")
        if self.line_count < 0:
            raise ValueError("line_count must not be negative")
        for symbol in self.symbols:
            if symbol.end_line > self.line_count:
                raise ValueError(f"symbol {symbol.qualified_name!r} exceeds file line count")
