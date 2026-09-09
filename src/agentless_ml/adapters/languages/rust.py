"""Rust source declarations; no macro expansion, build scripts or code execution."""

from dataclasses import dataclass
from pathlib import PurePosixPath

import tree_sitter_rust
from tree_sitter import Language, Parser

from agentless_ml.schemas import FileNode, SymbolNode


def _parse(source):
    data = source.encode("utf-8")
    root = Parser(Language(tree_sitter_rust.language())).parse(data).root_node
    if root.has_error:
        raise ValueError("Rust source contains a syntax error or missing token")
    return data, root


def _text(data, node):
    return data[node.start_byte : node.end_byte].decode("utf-8")


def _declarations(data, parent, prefix="", owner=False):
    symbols = []
    attributes = []
    kinds = {
        "function_item": "method" if owner else "function",
        "function_signature_item": "method",
        "struct_item": "struct",
        "enum_item": "enum",
        "trait_item": "trait",
        "type_item": "type",
        "associated_type": "type",
        "const_item": "constant",
        "static_item": "variable",
        "mod_item": "module",
        "field_declaration": "field",
        "enum_variant": "variant",
        "impl_item": "impl",
        "union_item": "type",
    }
    for node in parent.named_children:
        if node.type == "attribute_item":
            attributes.append(node)
            continue
        if node.type in {"line_comment", "block_comment"}:
            continue
        kind = kinds.get(node.type)
        name_node = node.child_by_field_name("name")
        if kind is None or (name_node is None and kind != "impl"):
            attributes = []
            continue
        if kind == "impl":
            name = _text(data, node.child_by_field_name("type"))
            trait = node.child_by_field_name("trait")
            if trait is not None:
                name = f"<{name} as {_text(data, trait)}>"
        else:
            name = _text(data, name_node)
        qualified = f"{prefix}::{name}" if prefix else name
        body = node.child_by_field_name("body")
        children = ()
        if body is not None and kind in {
            "impl",
            "trait",
            "module",
            "struct",
            "enum",
            "type",
        }:
            children = _declarations(data, body, qualified, kind in {"impl", "trait"})
        start = attributes[0] if attributes else node
        signature_end = body.start_byte if body is not None else node.end_byte
        symbols.append(
            SymbolNode(
                kind=kind,
                name=name,
                qualified_name=qualified,
                signature=data[start.start_byte : signature_end]
                .decode("utf-8")
                .strip(),
                start_line=start.start_point.row + 1,
                end_line=node.end_point.row + bool(node.end_point.column),
                children=children,
            )
        )
        attributes = []
    return tuple(symbols)


@dataclass(frozen=True, slots=True)
class RustAdapter:
    language: str = "rust"
    extension: str = ".rs"
    extensions: tuple[str, ...] = (".rs",)

    def is_source_path(self, path: str) -> bool:
        return path.endswith(self.extension) and not any(
            part in {"target", "vendor"} or part.startswith(".")
            for part in PurePosixPath(path).parts
        )

    def is_test_path(self, path: str) -> bool:
        return bool({"tests", "benches"} & set(PurePosixPath(path).parts))

    def parse_file(self, path: str, source: str) -> FileNode:
        data, root = _parse(source)
        return FileNode(
            path, self.language, len(source.splitlines()), _declarations(data, root)
        )

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
            raise ValueError("assignment compression is not implemented for Rust")
        data, root = _parse(source)
        bodies = []

        def visit(node):
            if node.type == "function_item":
                body = node.child_by_field_name("body")
                if body is not None:
                    bodies.append(body)
                    return
            for child in node.named_children:
                visit(child)

        visit(root)
        for body in reversed(bodies):
            data = data[: body.start_byte] + b"{ ... }" + data[body.end_byte :]
        return data.decode("utf-8")
