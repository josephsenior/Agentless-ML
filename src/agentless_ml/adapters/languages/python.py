"""Python structure extraction with an explicit Agentless v1.5 parity seam."""

from __future__ import annotations

import ast
import re
import warnings
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import libcst as cst
import libcst.matchers as matchers

from agentless_ml.schemas import FileNode, SymbolNode
from agentless_ml.schemas.prompts import LanguagePrompts, RepairExample
from agentless_ml.structure.resolution import ResolvedLocations, merge_intervals

# Published Agentless v1.5.0 prompt text, kept byte-identical for parity.
_AGENTLESS_SYMBOL_LOCALIZATION = """
Please look through the following GitHub Problem Description and the Skeleton of Relevant Files.
Identify all locations that need inspection or editing to fix the problem, including directly related areas as well as any potentially related global variables, functions, and classes.
For each location you provide, either give the name of the class, the name of a method in a class, the name of a function, or the name of a global variable.

### GitHub Problem Description ###
{problem_statement}

### Skeleton of Relevant Files ###
{file_contents}

###

Please provide the complete set of locations as either a class name, a function name, or a variable name.
Note that if you include a class, you do not need to list its specific methods.
You can include either the entire class or don't include the class name and instead include specific methods in the class.
### Examples:
```
full_path1/file1.py
function: my_function_1
class: MyClass1
function: MyClass2.my_method

full_path2/file2.py
variable: my_var
function: MyClass3.my_method

full_path3/file3.py
function: my_function_2
function: my_function_3
function: MyClass4.my_method_1
class: MyClass5
```

Return just the locations.
"""

PYTHON_PROMPTS = LanguagePrompts(
    symbol_localization=_AGENTLESS_SYMBOL_LOCALIZATION,
    repair_example=RepairExample(
        path="mathweb/flask/app.py",
        search="from flask import Flask",
        replace="import math\nfrom flask import Flask",
        indented_line="        print(x)",
    ),
)


def _source_lines(source: str) -> list[str]:
    return source.splitlines()


def _parse_python(source: str, filename: str = "<unknown>") -> ast.Module:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SyntaxWarning)
        return ast.parse(source, filename=filename)


def _node_text(node: ast.AST, lines: list[str]) -> list[str]:
    return lines[node.lineno - 1 : node.end_lineno]  # type: ignore[attr-defined]


def legacy_symbol_projection(source: str) -> dict[str, Any]:
    """Reproduce ``parse_python_file`` output from pinned Agentless v1.5.0.

    This deliberately retains published behavior, including its treatment of
    synchronous versus asynchronous definitions. It is a regression seam, not
    the future multilingual core representation.
    """
    parsed = _parse_python(source)
    lines = _source_lines(source)
    classes: list[dict[str, Any]] = []
    functions: list[dict[str, Any]] = []
    class_methods: set[str] = set()

    for node in ast.walk(parsed):
        if isinstance(node, ast.ClassDef):
            methods: list[dict[str, Any]] = []
            for child in node.body:
                if isinstance(child, ast.FunctionDef):
                    methods.append(
                        {
                            "name": child.name,
                            "start_line": child.lineno,
                            "end_line": child.end_lineno,
                            "text": _node_text(child, lines),
                        }
                    )
                    class_methods.add(child.name)
            classes.append(
                {
                    "name": node.name,
                    "start_line": node.lineno,
                    "end_line": node.end_lineno,
                    "text": _node_text(node, lines),
                    "methods": methods,
                }
            )
        elif isinstance(node, ast.FunctionDef) and not isinstance(
            node, ast.AsyncFunctionDef
        ):
            if node.name not in class_methods:
                functions.append(
                    {
                        "name": node.name,
                        "start_line": node.lineno,
                        "end_line": node.end_lineno,
                        "text": _node_text(node, lines),
                    }
                )

    return {"classes": classes, "functions": functions, "text": lines}


def _arguments(node: ast.FunctionDef) -> str:
    rendered = ast.unparse(node.args)
    return rendered if rendered.startswith("(") else f"({rendered})"


def _class_signature(node: ast.ClassDef) -> str:
    bases = [ast.unparse(base) for base in node.bases]
    bases.extend(
        f"{keyword.arg}={ast.unparse(keyword.value)}" for keyword in node.keywords
    )
    suffix = f"({', '.join(bases)})" if bases else ""
    return f"class {node.name}{suffix}"


@dataclass(frozen=True, slots=True)
class PythonAdapter:
    """Build normalized Python structures and legacy-compatible skeletons."""

    language: str = "python"
    extension: str = ".py"
    extensions: tuple[str, ...] = (".py",)
    prompts: LanguagePrompts = PYTHON_PROMPTS

    def is_source_path(self, path: str) -> bool:
        return path.endswith(self.extension)

    def is_test_path(self, path: str) -> bool:
        return any(part.startswith("test") for part in path.replace("\\", "/").split("/"))

    def parse_file(self, path: str, source: str) -> FileNode:
        tree = _parse_python(source, filename=path)
        symbols: list[SymbolNode] = []

        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                children = tuple(
                    self._function_symbol(child, parent=node.name)
                    for child in node.body
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
                )
                symbols.append(
                    SymbolNode(
                        kind="class",
                        name=node.name,
                        qualified_name=node.name,
                        signature=_class_signature(node),
                        start_line=node.lineno,
                        end_line=node.end_lineno,
                        children=children,
                    )
                )
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                symbols.append(self._function_symbol(node))

        return FileNode(
            path=path,
            language=self.language,
            line_count=len(_source_lines(source)),
            symbols=tuple(symbols),
        )

    def resolve_locations(
        self,
        locations: str | Sequence[str],
        file_node: FileNode,
        source: str,
        *,
        context_window: int,
        separate_intervals: bool,
        fine_grained_only: bool,
        remove_line_locations: bool,
    ) -> ResolvedLocations:
        return _resolve_agentless_locations(
            locations,
            file_node,
            source,
            context_window=context_window,
            separate_intervals=separate_intervals,
            fine_grained_only=fine_grained_only,
            remove_line_locations=remove_line_locations,
        )

    @staticmethod
    def _function_symbol(
        node: ast.FunctionDef | ast.AsyncFunctionDef, parent: str | None = None
    ) -> SymbolNode:
        prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
        qualified_name = f"{parent}.{node.name}" if parent else node.name
        return SymbolNode(
            kind="method" if parent else "function",
            name=node.name,
            qualified_name=qualified_name,
            signature=f"{prefix} {node.name}{_arguments(node)}",
            start_line=node.lineno,
            end_line=node.end_lineno,
        )

    def render_skeleton(
        self,
        source: str,
        *,
        path: str | None = None,
        keep_constant: bool = True,
        keep_indent: bool = False,
        compress_assign: bool = False,
        total_lines: int = 30,
        prefix_lines: int = 10,
        suffix_lines: int = 10,
    ) -> str:
        """Render the code skeleton used by the published localization prompt."""
        try:
            tree = cst.parse_module(source)
        except Exception:
            return source

        modified = tree.visit(_SkeletonTransformer(keep_constant=keep_constant))
        code = modified.code
        if compress_assign:
            code = _compress_assignments(
                code,
                total_lines=total_lines,
                prefix_lines=prefix_lines,
                suffix_lines=suffix_lines,
            )

        marker = _SkeletonTransformer.replacement_string
        if keep_indent:
            code = code.replace(marker + "\n", "...\n")
            code = code.replace(marker, "...\n")
        else:
            code = re.sub(rf"\n[ \t]*{re.escape(marker)}", "\n...", code)
        return code


class _SkeletonTransformer(cst.CSTTransformer):
    replacement_string = '"__FUNC_BODY_REPLACEMENT_STRING__"'

    def __init__(self, *, keep_constant: bool) -> None:
        self.keep_constant = keep_constant

    def leave_Module(
        self, original_node: cst.Module, updated_node: cst.Module
    ) -> cst.Module:
        body = [
            statement
            for statement in updated_node.body
            if matchers.matches(statement, matchers.ClassDef())
            or matchers.matches(statement, matchers.FunctionDef())
            or (
                self.keep_constant
                and matchers.matches(statement, matchers.SimpleStatementLine())
                and matchers.matches(statement.body[0], matchers.Assign())
            )
        ]
        return updated_node.with_changes(body=body)

    def leave_ClassDef(
        self, original_node: cst.ClassDef, updated_node: cst.ClassDef
    ) -> cst.ClassDef:
        body = [
            statement
            for statement in updated_node.body.body
            if not (
                matchers.matches(statement, matchers.SimpleStatementLine())
                and matchers.matches(statement.body[0], matchers.Expr())
                and matchers.matches(statement.body[0].value, matchers.SimpleString())
            )
        ]
        return updated_node.with_changes(body=cst.IndentedBlock(body=body))

    def leave_FunctionDef(
        self, original_node: cst.FunctionDef, updated_node: cst.FunctionDef
    ) -> cst.CSTNode:
        expression = cst.Expr(
            value=cst.SimpleString(value=self.replacement_string)
        )
        body = cst.IndentedBlock(body=[cst.SimpleStatementLine(body=[expression])])
        return updated_node.with_changes(body=body)


class _AssignmentVisitor(cst.CSTVisitor):
    METADATA_DEPENDENCIES = (cst.metadata.PositionProvider,)

    def __init__(self) -> None:
        self.spans: list[tuple[int, int]] = []

    def leave_Assign(self, original_node: cst.Assign) -> None:
        position = self.get_metadata(cst.metadata.PositionProvider, original_node)
        self.spans.append((position.start.line, position.end.line))


def _compress_assignments(
    source: str,
    *,
    total_lines: int,
    prefix_lines: int,
    suffix_lines: int,
) -> str:
    try:
        wrapper = cst.metadata.MetadataWrapper(cst.parse_module(source))
    except Exception:
        return source
    visitor = _AssignmentVisitor()
    wrapper.visit(visitor)
    intervals = [
        (start + prefix_lines, end - suffix_lines)
        for start, end in visitor.spans
        if end - start > total_lines
    ]
    result = ""
    for index, line in enumerate(source.splitlines(), start=1):
        if not any(start <= index <= end for start, end in intervals):
            result += line + "\n"
        if any(start == index for start, _ in intervals):
            result += "...\n"
    return result


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


def _resolve_agentless_locations(
    locations: str | Sequence[str],
    file_node: FileNode,
    source: str,
    *,
    context_window: int,
    separate_intervals: bool,
    fine_grained_only: bool,
    remove_line_locations: bool,
) -> ResolvedLocations:
    """Published Agentless v1.5.0 location semantics for Python files.

    Reproduces ``transfer_arb_locs_to_locs``: a ``class:`` line sets the class
    that later bare ``function:`` names are looked up in, dotted names select a
    method of a class, and ``variable:`` names are module-level assignments read
    from the source with LibCST, because the normalized structure has no
    variable symbols. Its quirks are kept deliberately for parity.
    """
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
                    line_locations.append(
                        (relevant[0].start_line, relevant[0].end_line)
                    )
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
                            child
                            for child in relevant_class.children
                            if child.name == name
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
        context_intervals = merge_intervals(contextual)
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
