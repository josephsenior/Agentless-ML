"""JavaScript and TypeScript source structure without executing project code."""

from dataclasses import dataclass
from pathlib import PurePosixPath

import tree_sitter_javascript
import tree_sitter_typescript
from tree_sitter import Language, Node, Parser

from agentless_ml.schemas import FileNode, SymbolNode

_JS_EXTENSIONS = (".js", ".jsx", ".mjs", ".cjs")
_TS_EXTENSIONS = (".ts", ".tsx", ".mts", ".cts")
_FUNCTIONS = {
    "function_declaration",
    "generator_function_declaration",
    "function_expression",
    "generator_function",
    "arrow_function",
    "function_signature",
}
_CLASSES = {"class", "class_declaration", "abstract_class_declaration"}
_METHODS = {"method_definition", "method_signature", "abstract_method_signature"}


def _text(data: bytes, node: Node) -> str:
    return data[node.start_byte : node.end_byte].decode("utf-8")


def _name(data: bytes, node: Node | None) -> str | None:
    if node is None:
        return None
    if node.type in {
        "identifier",
        "type_identifier",
        "property_identifier",
        "private_property_identifier",
        "number",
    }:
        return _text(data, node)
    if node.type == "string":
        # Keep literal spelling; do not evaluate computed keys or escape sequences.
        return _text(data, node)[1:-1]
    if node.type == "member_expression":
        owner = _name(data, node.child_by_field_name("object"))
        member = _name(data, node.child_by_field_name("property"))
        if owner and member:
            return f"{owner}.{member}"
    return None


def _parse(path: str, source: str) -> tuple[bytes, Node]:
    suffix = PurePosixPath(path).suffix
    if suffix in _JS_EXTENSIONS:
        grammar = tree_sitter_javascript.language()
    elif suffix == ".tsx":
        grammar = tree_sitter_typescript.language_tsx()
    elif suffix in _TS_EXTENSIONS:
        grammar = tree_sitter_typescript.language_typescript()
    else:
        raise ValueError(f"unsupported JavaScript/TypeScript suffix: {suffix}")
    data = source.encode("utf-8")
    root = Parser(Language(grammar)).parse(data).root_node
    if root.has_error:
        raise ValueError(f"syntax error or missing token in {path}")
    return data, root


def _make_symbol(
    data: bytes,
    node: Node,
    name: str,
    kind: str,
    parent: str = "",
    span: Node | None = None,
) -> SymbolNode:
    span = span if span is not None else node
    qualified = f"{parent}.{name}" if parent else name
    children = []
    body = node.child_by_field_name("body")
    members = node if node.type == "object" else body
    if kind in {"class", "interface", "object"} and members is not None:
        for member in members.named_children:
            key = (
                member.child_by_field_name("name")
                or member.child_by_field_name("key")
                or member.child_by_field_name("property")
            )
            member_name = _name(data, key)
            if not member_name:
                continue
            value = member.child_by_field_name("value")
            if member.type in _METHODS:
                children.append(
                    _make_symbol(data, member, member_name, "method", qualified)
                )
            elif value is not None and value.type in _FUNCTIONS:
                children.append(
                    _make_symbol(data, value, member_name, "method", qualified, member)
                )
            elif member.type in {
                "field_definition",
                "public_field_definition",
                "property_signature",
                "pair",
            }:
                children.append(
                    _make_symbol(data, member, member_name, "field", qualified)
                )
    end = body.start_byte if body is not None else node.end_byte
    return SymbolNode(
        kind=kind,
        name=name,
        qualified_name=qualified,
        signature=data[span.start_byte : end].decode("utf-8").strip(),
        start_line=span.start_point.row + 1,
        end_line=span.end_point.row + (1 if span.end_point.column else 0),
        children=tuple(children),
    )


def _value_kind(node: Node | None, fallback: str) -> str:
    if node is None:
        return fallback
    if node.type in _FUNCTIONS:
        return "function"
    if node.type in _CLASSES:
        return "class"
    if node.type == "object":
        return "object"
    return fallback


def _declarations(data: bytes, node: Node, span: Node | None = None):
    if node.type == "export_statement":
        declaration = node.child_by_field_name("declaration")
        if declaration is not None:
            yield from _declarations(data, declaration, node)
        else:
            value = node.child_by_field_name("value")
            if value is not None:
                name = _name(data, value.child_by_field_name("name")) or "default"
                yield _make_symbol(
                    data, value, name, _value_kind(value, "constant"), span=node
                )
        return
    if node.type == "ambient_declaration":
        for child in node.named_children:
            yield from _declarations(data, child, node)
        return
    name = _name(data, node.child_by_field_name("name"))
    kind = {
        "interface_declaration": "interface",
        "type_alias_declaration": "type",
        "enum_declaration": "enum",
    }.get(node.type)
    if node.type in _FUNCTIONS:
        kind = "function"
    elif node.type in _CLASSES:
        kind = "class"
    if name and kind:
        yield _make_symbol(data, node, name, kind, span=span)
    elif node.type in {"lexical_declaration", "variable_declaration"}:
        fallback = (
            "constant"
            if any(child.type == "const" for child in node.children)
            else "variable"
        )
        for child in node.named_children:
            if child.type != "variable_declarator":
                continue
            name = _name(data, child.child_by_field_name("name"))
            if name:
                value = child.child_by_field_name("value")
                kind = _value_kind(value, fallback)
                target = value if kind in {"function", "class", "object"} else child
                yield _make_symbol(data, target, name, kind, span=child)
    elif node.type == "expression_statement" and node.named_child_count == 1:
        assignment = node.named_children[0]
        if assignment.type != "assignment_expression":
            return
        name = _name(data, assignment.child_by_field_name("left"))
        value = assignment.child_by_field_name("right")
        if name and (
            name == "module.exports" or name.startswith(("exports.", "module.exports."))
        ):
            yield _make_symbol(
                data, value, name, _value_kind(value, "variable"), span=assignment
            )


@dataclass(frozen=True, slots=True)
class JavaScriptAdapter:
    language: str = "javascript"
    extension: str = ".js"
    extensions: tuple[str, ...] = _JS_EXTENSIONS

    def is_source_path(self, path: str) -> bool:
        parts = PurePosixPath(path).parts
        return path.endswith(self.extensions) and not any(
            p in {"node_modules", "vendor", "dist", "build", "coverage"}
            or p.startswith(".")
            for p in parts
        )

    def is_test_path(self, path: str) -> bool:
        parts = PurePosixPath(path).parts
        stem = PurePosixPath(path).stem
        return any(
            p in {"test", "tests", "__tests__", "__mocks__"} for p in parts
        ) or stem.endswith((".test", ".spec"))

    def parse_file(self, path: str, source: str) -> FileNode:
        if not path.endswith(self.extensions):
            raise ValueError(f"unsupported file for {self.language}: {path}")
        data, root = _parse(path, source)
        symbols = tuple(
            s for child in root.named_children for s in _declarations(data, child)
        )
        language = "javascript" if path.endswith(_JS_EXTENSIONS) else "typescript"
        return FileNode(path, language, len(source.splitlines()), symbols)

    def render_skeleton(
        self,
        source: str,
        *,
        path: str | None = None,
        compress_assign: bool = False,
        total_lines: int = 30,
        prefix_lines: int = 10,
        suffix_lines: int = 10,
    ) -> str:
        if compress_assign:
            raise ValueError(
                "assignment compression is not implemented for JavaScript/TypeScript"
            )
        path = path or "source" + self.extension
        if not path.endswith(self.extensions):
            raise ValueError(f"unsupported file for {self.language}: {path}")
        data, root = _parse(path, source)
        replacements = []

        def visit(node):
            if node.type in _FUNCTIONS | _METHODS:
                body = node.child_by_field_name("body")
                if body is not None:
                    marker = b"{ ... }" if body.type == "statement_block" else b"..."
                    replacements.append((body.start_byte, body.end_byte, marker))
                    return  # A nested function inside this body is already hidden.
            for child in node.named_children:
                visit(child)

        visit(root)
        for start, end, marker in reversed(replacements):
            data = data[:start] + marker + data[end:]
        return data.decode("utf-8")


@dataclass(frozen=True, slots=True)
class TypeScriptAdapter(JavaScriptAdapter):
    language: str = "typescript"
    extension: str = ".ts"
    # Mixed JS/TS repositories are common; each file chooses its own grammar.
    extensions: tuple[str, ...] = _TS_EXTENSIONS + _JS_EXTENSIONS
