"""Python structure extraction with an explicit Agentless v1.5 parity seam."""

from __future__ import annotations

import ast
import re
import warnings
from dataclasses import dataclass
from typing import Any

import libcst as cst
import libcst.matchers as matchers

from agentless_ml.schemas import FileNode, SymbolNode


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
