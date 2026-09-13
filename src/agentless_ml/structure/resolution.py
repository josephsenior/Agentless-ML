"""Resolve model-returned location strings against a repository structure.

``resolve_symbol_locations`` is the language-neutral resolver: an explicit kind
label and a name, matched against the ``FileNode`` alone. A language whose
published behavior requires other semantics supplies its own resolver through
``LanguageAdapter.resolve_locations``; both return ``ResolvedLocations``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from agentless_ml.schemas import FileNode


@dataclass(frozen=True, slots=True)
class ResolvedLocations:
    line_intervals: tuple[tuple[int, int], ...]
    context_intervals: tuple[tuple[int, int], ...]
    unrecognized: tuple[str, ...] = ()

    @property
    def is_valid(self) -> bool:
        return bool(self.line_intervals)


def merge_intervals(intervals: list[tuple[int, int]]) -> list[tuple[int, int]]:
    if not intervals:
        return []
    intervals.sort(key=lambda interval: interval[0])
    merged = [intervals[0]]
    for current in intervals[1:]:
        previous = merged[-1]
        if current[0] <= previous[1]:
            merged[-1] = (previous[0], max(previous[1], current[1]))
        else:
            merged.append(current)
    return merged


# Location labels the prompts may use, and the symbol kinds each one selects.
LABEL_KINDS = {
    "function": {"function", "method"},
    "method": {"method"},
    "type": {"type", "struct", "interface", "enum", "trait"},
    "trait": {"trait"},
    "impl": {"impl"},
    "module": {"module"},
    "class": {"class"},
    "field": {"field"},
    "variable": {"variable", "constant", "object"},
    "constant": {"constant"},
}


def resolve_symbol_locations(
    locations: str | Sequence[str],
    file_node: FileNode,
    source: str,
    *,
    context_window: int,
    separate_intervals: bool,
    fine_grained_only: bool,
    remove_line_locations: bool,
) -> ResolvedLocations:
    """Resolve explicit symbol kinds without Python AST or class assumptions."""

    def flatten(symbols):
        for symbol in symbols:
            yield symbol
            yield from flatten(symbol.children)

    symbols = tuple(flatten(file_node.symbols))
    groups = [locations] if isinstance(locations, str) else locations
    spans: list[tuple[int, int]] = []
    unknown = []
    for group in groups:
        for raw in group.splitlines():
            if not raw.strip():
                continue
            kind, separator, name = raw.strip().partition(":")
            name = name.strip()
            if kind == "line" and separator:
                if remove_line_locations:
                    continue
                if name.isdecimal() and 1 <= int(name) <= file_node.line_count:
                    spans.append((int(name), int(name)))
                else:
                    unknown.append(raw)
                continue
            matches = [
                s
                for s in symbols
                if s.kind in LABEL_KINDS.get(kind, set())
                and (
                    s.qualified_name == name
                    or ("." not in name and "::" not in name and s.name == name)
                )
            ]
            if len(matches) == 1:
                spans.append((matches[0].start_line, matches[0].end_line))
            else:
                unknown.append(raw)
    spans = list(dict.fromkeys(spans))
    if fine_grained_only:
        spans = [
            s
            for s in spans
            if not any(
                s != other and s[0] <= other[0] and other[1] <= s[1] for other in spans
            )
        ]
    if not spans:
        return ResolvedLocations((), (), tuple(unknown))
    contextual = [
        (
            max(1, start - context_window),
            min(file_node.line_count, end + context_window),
        )
        for start, end in spans
    ]
    if separate_intervals:
        contextual = merge_intervals(contextual)
    else:
        contextual = [(min(s for s, _ in contextual), max(e for _, e in contextual))]
    return ResolvedLocations(tuple(spans), tuple(contextual), tuple(unknown))
