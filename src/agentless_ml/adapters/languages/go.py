"""Go declarations and source skeletons, parsed without executing repository code."""

from dataclasses import dataclass
from pathlib import PurePosixPath

import tree_sitter_go
from tree_sitter import Language, Node, Parser

from agentless_ml.schemas import FileNode, SymbolNode


def _parse(source: str) -> tuple[bytes, Node]:
    data = source.encode("utf-8")
    root = Parser(Language(tree_sitter_go.language())).parse(data).root_node
    if root.has_error:
        raise ValueError("Go source contains a syntax error or missing token")
    if not any(node.type == "package_clause" for node in root.named_children):
        raise ValueError("Go source must declare a package")
    return data, root


def _text(data: bytes, node: Node) -> str:
    return data[node.start_byte : node.end_byte].decode("utf-8")


def _symbol(
    data: bytes,
    node: Node,
    kind: str,
    name: str,
    qualified_name: str | None = None,
    children: tuple[SymbolNode, ...] = (),
) -> SymbolNode:
    body = node.child_by_field_name("body")
    end = body.start_byte if body is not None else node.end_byte
    return SymbolNode(
        kind=kind,
        name=name,
        qualified_name=qualified_name or name,
        signature=data[node.start_byte : end].decode("utf-8").strip(),
        start_line=node.start_point.row + 1,
        end_line=node.end_point.row + (1 if node.end_point.column else 0),
        children=children,
    )


def _receiver(data: bytes, node: Node) -> str:
    receiver = node.child_by_field_name("receiver")
    parameter = next(
        n for n in receiver.named_children if n.type == "parameter_declaration"
    )
    receiver_type = parameter.child_by_field_name("type")
    if receiver_type.type == "pointer_type":
        receiver_type = receiver_type.named_children[0]
    if receiver_type.type == "generic_type":
        receiver_type = receiver_type.child_by_field_name("type")
    return _text(data, receiver_type)


def _specs(node: Node):
    # var declarations use a var_spec_list for grouped declarations.
    for child in node.named_children:
        if child.type.endswith("_spec") or child.type == "type_alias":
            yield child
        elif child.type.endswith("_spec_list"):
            yield from _specs(child)


@dataclass(frozen=True, slots=True)
class GoAdapter:
    language: str = "go"
    extension: str = ".go"
    extensions: tuple[str, ...] = (".go",)

    def is_source_path(self, path: str) -> bool:
        parts = PurePosixPath(path).parts
        return path.endswith(self.extension) and not any(
            part in {"vendor", "testdata"} or part.startswith((".", "_"))
            for part in parts
        )

    def is_test_path(self, path: str) -> bool:
        return path.endswith("_test.go")

    def parse_file(self, path: str, source: str) -> FileNode:
        data, root = _parse(source)
        symbols = []
        for node in root.named_children:
            if node.type in {"function_declaration", "method_declaration"}:
                name = _text(data, node.child_by_field_name("name"))
                is_method = node.type == "method_declaration"
                qualified = f"{_receiver(data, node)}.{name}" if is_method else name
                symbols.append(
                    _symbol(
                        data,
                        node,
                        "method" if is_method else "function",
                        name,
                        qualified,
                    )
                )
            elif node.type == "type_declaration":
                for spec in _specs(node):
                    name = _text(data, spec.child_by_field_name("name"))
                    type_node = spec.child_by_field_name("type")
                    kind = {"struct_type": "struct", "interface_type": "interface"}.get(
                        type_node.type, "type"
                    )
                    children = []
                    if kind == "interface":
                        for member in type_node.named_children:
                            if member.type == "method_elem":
                                method = _text(data, member.child_by_field_name("name"))
                                children.append(
                                    _symbol(
                                        data,
                                        member,
                                        "method",
                                        method,
                                        f"{name}.{method}",
                                    )
                                )
                    symbols.append(
                        _symbol(data, spec, kind, name, children=tuple(children))
                    )
            elif node.type in {"var_declaration", "const_declaration"}:
                for spec in _specs(node):
                    for name_node in spec.children_by_field_name("name"):
                        name = _text(data, name_node)
                        if name != "_":
                            symbols.append(
                                _symbol(
                                    data,
                                    spec,
                                    "constant"
                                    if node.type == "const_declaration"
                                    else "variable",
                                    name,
                                )
                            )
        return FileNode(path, self.language, len(source.splitlines()), tuple(symbols))

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
            raise ValueError("assignment compression is not implemented for Go")
        data, root = _parse(source)
        # Replace bodies by byte span: braces in strings/comments do not interfere.
        bodies = [
            node.child_by_field_name("body")
            for node in root.named_children
            if node.type in {"function_declaration", "method_declaration"}
        ]
        for body in reversed([body for body in bodies if body is not None]):
            data = data[: body.start_byte] + b"{ ... }" + data[body.end_byte :]
        return data.decode("utf-8")
