"""Parse localization responses and construct focused repair context."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import libcst as cst
import libcst.matchers as matchers

from agentless_ml.schemas import FileNode, SymbolNode


def extract_code_blocks(text: str) -> list[str]:
    """Extract unlabelled fenced blocks with published Agentless semantics."""
    matches = re.findall(r"```\n(.*?)\n```", text, re.DOTALL)
    if not matches and "```" in text:
        return [text.split("```", 1)[-1].strip()]
    return matches


def parse_locations_for_files(
    blocks: Sequence[str],
    file_names: Sequence[str],
    *,
    keep_old_order: bool = False,
) -> dict[str, list[str]]:
    """Associate model-returned location lines with known files."""
    results: dict[str, list[str]] = (
        {file_name: [] for file_name in file_names} if keep_old_order else {}
    )
    current_file_name: str | None = None
    for block in blocks:
        for line in block.splitlines():
            if line.strip().endswith(".py"):
                current_file_name = line.strip()
            elif line.strip() and any(
                line.startswith(prefix)
                for prefix in ("line:", "function:", "class:", "variable:")
            ):
                if current_file_name in file_names:
                    results.setdefault(current_file_name, []).append(line)

    for file_name in file_names:
        results.setdefault(file_name, [])
    return {file_name: ["\n".join(results[file_name])] for file_name in results}


def _merge_intervals(intervals: list[tuple[int, int]]) -> list[tuple[int, int]]:
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


class _GlobalAssignmentVisitor(cst.CSTVisitor):
    METADATA_DEPENDENCIES = (cst.metadata.PositionProvider,)

    def __init__(self) -> None:
        self.assignments: dict[str, tuple[int, int]] = {}

    def leave_Module(self, original_node: cst.Module) -> None:
        for statement in original_node.body:
            if not (
                matchers.matches(statement, matchers.SimpleStatementLine())
                and matchers.matches(statement.body[0], matchers.Assign())
            ):
                continue
            position = self.get_metadata(cst.metadata.PositionProvider, statement)
            assignment = statement.body[0]
            try:
                targets = [assignment.targets[0].target.value]
            except (AttributeError, IndexError):
                try:
                    targets = [
                        element.value.value
                        for element in assignment.targets[0].target.elements
                    ]
                except (AttributeError, IndexError):
                    targets = []
            for target in targets:
                self.assignments[target] = (position.start.line, position.end.line)


def _global_assignments(source: str) -> dict[str, tuple[int, int]]:
    try:
        wrapper = cst.metadata.MetadataWrapper(cst.parse_module(source))
    except Exception:
        return {}
    visitor = _GlobalAssignmentVisitor()
    wrapper.visit(visitor)
    return visitor.assignments


def _classes(file_node: FileNode) -> tuple[SymbolNode, ...]:
    return tuple(symbol for symbol in file_node.symbols if symbol.kind == "class")


def _functions(file_node: FileNode) -> tuple[SymbolNode, ...]:
    return tuple(symbol for symbol in file_node.symbols if symbol.kind == "function")


@dataclass(frozen=True, slots=True)
class ResolvedLocations:
    line_intervals: tuple[tuple[int, int], ...]
    context_intervals: tuple[tuple[int, int], ...]
    unrecognized: tuple[str, ...] = ()

    @property
    def is_valid(self) -> bool:
        return bool(self.line_intervals)


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
    """Resolve Agentless location strings to one-based inclusive line spans."""
    if context_window < 0:
        raise ValueError("context_window must not be negative")
    groups = [locations] if isinstance(locations, str) else locations
    classes = _classes(file_node)
    functions = _functions(file_node)
    globals_by_name = _global_assignments(source)
    line_locations: list[tuple[int, int]] = []
    unrecognized: list[str] = []

    for group in groups:
        current_class_name = ""
        for raw_location in group.splitlines():
            location = raw_location
            if location.startswith("class: ") and "." not in location:
                name = location[len("class: ") :].strip()
                relevant = [symbol for symbol in classes if symbol.name == name]
                if relevant:
                    line_locations.append((relevant[0].start_line, relevant[0].end_line))
                    current_class_name = name
                else:
                    unrecognized.append(name)
            elif location.startswith("function: ") or "." in location:
                name = location.split(":", 1)[-1].strip()
                if "." in name:
                    class_name, method_name = name.split(".")[:2]
                    relevant_classes = [
                        symbol for symbol in classes if symbol.name == class_name
                    ]
                    if not relevant_classes:
                        unrecognized.append(name)
                    else:
                        methods = [
                            child
                            for child in relevant_classes[0].children
                            if child.name == method_name
                        ]
                        if methods:
                            line_locations.append(
                                (methods[0].start_line, methods[0].end_line)
                            )
                        else:
                            unrecognized.append(name)
                else:
                    relevant_functions = [
                        symbol for symbol in functions if symbol.name == name
                    ]
                    if relevant_functions:
                        line_locations.append(
                            (
                                relevant_functions[0].start_line,
                                relevant_functions[0].end_line,
                            )
                        )
                    elif current_class_name:
                        relevant_class = next(
                            symbol
                            for symbol in classes
                            if symbol.name == current_class_name
                        )
                        methods = [
                            child for child in relevant_class.children if child.name == name
                        ]
                        if methods:
                            line_locations.append(
                                (methods[0].start_line, methods[0].end_line)
                            )
                        else:
                            unrecognized.append(name)
                    else:
                        methods = [
                            child
                            for parent in classes
                            for child in parent.children
                            if child.name == name
                        ]
                        if len(methods) == 1:
                            line_locations.append(
                                (methods[0].start_line, methods[0].end_line)
                            )
                        elif not methods:
                            unrecognized.append(name)
            elif location.startswith("line: "):
                if remove_line_locations:
                    continue
                token = location[len("line: ") :].strip().split()[0]
                try:
                    line = int(token)
                except ValueError:
                    continue
                line_locations.append((line, line))
            elif location.startswith("variable:"):
                names = location[len("variable:") :].strip().split()
                for name in names:
                    if name in globals_by_name:
                        line_locations.append(globals_by_name[name])
            elif location.strip():
                unrecognized.append(location)

    if fine_grained_only:
        filtered: list[tuple[int, int]] = []
        for start, end in line_locations:
            if filtered:
                previous_start, previous_end = filtered[-1]
                if previous_start <= start and end <= previous_end:
                    filtered.pop()
            filtered.append((start, end))
        line_locations = filtered

    if not line_locations:
        return ResolvedLocations((), (), tuple(unrecognized))

    line_count = len(source.split("\n"))
    if separate_intervals:
        contextual = [
            (
                min(max(start - context_window, 0), line_count),
                max(min(end + context_window, line_count), 0),
            )
            for start, end in line_locations
        ]
        context_intervals = _merge_intervals(contextual)
    else:
        context_intervals = [
            (
                max(min(start for start, _ in line_locations) - context_window, 0),
                min(max(end for _, end in line_locations) + context_window, line_count),
            )
        ]
    return ResolvedLocations(
        tuple(line_locations), tuple(context_intervals), tuple(unrecognized)
    )


def _line_wrap_content(
    source: str,
    intervals: Sequence[tuple[int, int]],
    *,
    add_space: bool,
    no_line_number: bool,
    sticky_scroll: bool,
) -> str:
    def is_scope(line: str) -> bool:
        return line.startswith("class ") or line.strip().startswith("def ")

    lines = source.split("\n")
    active_intervals = list(intervals) or [(0, len(lines))]
    new_lines: list[str] = []
    previous_scopes: list[dict[str, int | str]] = []
    line_format = "{line}"
    if not no_line_number:
        line_format = "{line_number}|{line}" if not add_space else "{line_number}| {line} "

    max_line = len(lines)
    for min_line, max_line in active_intervals:
        if min_line != 0:
            new_lines.append("...")
        scopes: list[dict[str, int | str]] = []
        for index, line in enumerate(lines):
            if sticky_scroll and is_scope(line):
                indent_level = len(line) - len(line.lstrip())
                while scopes and int(scopes[-1]["indent_level"]) >= indent_level:
                    scopes.pop()
                scopes.append(
                    {
                        "line": line,
                        "line_number": index,
                        "indent_level": indent_level,
                    }
                )
            if min_line != -1 and index < min_line - 1:
                continue
            if sticky_scroll and index == min_line - 1:
                last_scope_line: int | None = None
                for scope_index, scope in enumerate(scopes):
                    if (
                        len(previous_scopes) > scope_index
                        and previous_scopes[scope_index]["line_number"]
                        == scope["line_number"]
                    ):
                        continue
                    if index == scope["line_number"]:
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
            new_lines.append(line_format.format(line_number=index + 1, line=line))
            if max_line != -1 and index >= max_line - 1:
                break
        previous_scopes = scopes
    if max_line != len(lines):
        new_lines.append("...")
    return "\n".join(new_lines)


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
