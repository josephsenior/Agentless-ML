"""The repository-representation invariant every language must preserve.

Localization reads a ``FileNode`` in exactly these ways: it filters symbols by
``kind``, matches ``qualified_name`` (and ``name``), turns ``start_line`` and
``end_line`` into edit regions, walks ``children`` for hierarchical lookup, and
bounds ``line:`` locations by ``line_count``. Those fields, together with symbol
order, are the workflow as the model experiences it.

``signature`` is not read by localization. It only affects rendered text, so a
change to it is a rendering change rather than a workflow change.
"""

from __future__ import annotations

from typing import Any

from agentless_ml.schemas import FileNode, SymbolNode

StructuralSymbol = tuple[str, str, str, int, int, tuple["StructuralSymbol", ...]]


def symbol_record(symbol: SymbolNode) -> dict[str, Any]:
    """Every field of a symbol, including rendering-only ones, as plain data."""
    return {
        "kind": symbol.kind,
        "name": symbol.name,
        "qualified_name": symbol.qualified_name,
        "signature": symbol.signature,
        "start_line": symbol.start_line,
        "end_line": symbol.end_line,
        "children": [symbol_record(child) for child in symbol.children],
    }


def file_record(node: FileNode) -> dict[str, Any]:
    return {
        "path": node.path,
        "language": node.language,
        "line_count": node.line_count,
        "symbols": [symbol_record(symbol) for symbol in node.symbols],
    }


def file_from_record(record: dict[str, Any]) -> FileNode:
    def symbol(data: dict[str, Any]) -> SymbolNode:
        return SymbolNode(
            kind=data["kind"],
            name=data["name"],
            qualified_name=data["qualified_name"],
            signature=data["signature"],
            start_line=data["start_line"],
            end_line=data["end_line"],
            children=tuple(symbol(child) for child in data["children"]),
        )

    return FileNode(
        record["path"],
        record["language"],
        record["line_count"],
        tuple(symbol(data) for data in record["symbols"]),
    )


def structural_view(
    symbols: tuple[SymbolNode, ...],
) -> tuple[StructuralSymbol, ...]:
    """Symbols reduced to the fields localization depends on, in order."""
    return tuple(
        (
            s.kind,
            s.name,
            s.qualified_name,
            s.start_line,
            s.end_line,
            structural_view(s.children),
        )
        for s in symbols
    )


def structural_differences(expected: FileNode, actual: FileNode) -> list[str]:
    """Describe each place where ``actual`` breaks the workflow invariant."""
    differences = [
        f"{field}: expected {getattr(expected, field)!r}, got {getattr(actual, field)!r}"
        for field in ("path", "language", "line_count")
        if getattr(expected, field) != getattr(actual, field)
    ]

    def compare(
        left: tuple[SymbolNode, ...], right: tuple[SymbolNode, ...], scope: str
    ) -> None:
        for index in range(max(len(left), len(right))):
            where = f"{scope}[{index}]"
            if index >= len(left):
                differences.append(f"{where}: unexpected {right[index].qualified_name!r}")
                continue
            if index >= len(right):
                differences.append(f"{where}: missing {left[index].qualified_name!r}")
                continue
            a, b = left[index], right[index]
            for field in ("kind", "name", "qualified_name", "start_line", "end_line"):
                if getattr(a, field) != getattr(b, field):
                    differences.append(
                        f"{where} {a.qualified_name!r} {field}: "
                        f"expected {getattr(a, field)!r}, got {getattr(b, field)!r}"
                    )
            compare(a.children, b.children, f"{where}.children")

    compare(expected.symbols, actual.symbols, "symbols")
    return differences


def observe(adapter: Any, path: str, source: str) -> dict[str, Any]:
    """Everything a language exposes for one file, with failures as data.

    Rejections are part of the representation: which files raise decides which
    files can enter the repository structure at all.
    """

    def attempt(operation: Any) -> Any:
        try:
            return operation()
        except ValueError as error:
            return {"error": {"type": type(error).__name__, "message": str(error)}}

    return {
        "parse": attempt(lambda: file_record(adapter.parse_file(path, source))),
        "skeleton": attempt(lambda: adapter.render_skeleton(source, path=path)),
    }


def assert_structurally_equivalent(expected: FileNode, actual: FileNode) -> None:
    differences = structural_differences(expected, actual)
    if differences:
        raise AssertionError(
            "repository representation changed at the workflow level:\n  "
            + "\n  ".join(differences)
        )
