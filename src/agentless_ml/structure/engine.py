"""Build repository structure from any tree-sitter grammar a ``LanguageSpec`` describes.

Nothing here names a language. The walk over one scope (a file, or a
container's members) is:

- ``ignored`` node types are skipped without effect;
- ``leading`` node types (Rust attributes) accumulate and move the start of the
  next symbol up to the first of them, extending its edit region;
- a node whose ``declarations`` rule finds symbols produces them;
- otherwise a ``wrappers`` node is searched in place, in the same scope;
- anything else ends the leading run.

A symbol whose kind is in ``containers`` gets its members from the named field
of its owner (``None``: the owner itself). Members are walked with
``member_declarations`` and no wrappers, or exactly like the top level when
``member_declarations`` is ``None``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from functools import cache
from pathlib import PurePosixPath

from tree_sitter import Language, Node, Parser

from agentless_ml.schemas import FileNode, SymbolNode
from agentless_ml.schemas.prompts import LanguagePrompts
from agentless_ml.structure.resolution import (
    ResolvedLocations,
    resolve_symbol_locations,
)
from agentless_ml.structure.skeleton import hide_bodies, strip_comments
from agentless_ml.structure.spec import (
    Context,
    Declaration,
    Grammar,
    LanguageSpec,
    Rule,
    Wrapper,
)


@cache
def _language(load) -> Language:
    return Language(load())


def parse(
    spec: LanguageSpec, path: str | None, source: str
) -> tuple[Grammar, bytes, Node]:
    """Parse one file, rejecting what cannot enter the repository structure.

    Without a path, the language's primary extension selects the grammar.
    """
    grammar = spec.grammars.get(PurePosixPath(path or "source" + spec.extension).suffix)
    if grammar is None:
        raise ValueError(f"unsupported file for {spec.language}: {path}")
    data = source.encode("utf-8")
    root = Parser(_language(grammar.load)).parse(data).root_node
    if root.has_error:
        location = f" in {path}" if path else ""
        raise ValueError(
            f"{spec.display_name} source contains a syntax error or missing token{location}"
        )
    for node_type, declared in spec.requires.items():
        if not any(node.type == node_type for node in root.named_children):
            raise ValueError(f"{spec.display_name} source must declare {declared}")
    return grammar, data, root


def extract(spec: LanguageSpec, path: str, source: str) -> FileNode:
    grammar, data, root = parse(spec, path, source)
    context = Context(data, spec.naming)
    symbols = _walk(spec, root.named_children, context, spec.declarations, spec.wrappers)
    return FileNode(path, grammar.language, len(source.splitlines()), tuple(symbols))


def _walk(
    spec: LanguageSpec,
    nodes: Sequence[Node],
    context: Context,
    declarations: Mapping[str, Rule],
    wrappers: Mapping[str, Wrapper],
    span: Node | None = None,
) -> list[SymbolNode]:
    symbols: list[SymbolNode] = []
    leading: list[Node] = []
    for node in nodes:
        if node.type in spec.ignored:
            continue
        if node.type in spec.leading:
            leading.append(node)
            continue
        rule = declarations.get(node.type)
        found = tuple(rule(node, context)) if rule else ()
        if found:
            symbols.extend(_symbol(spec, found_one, context, leading, span) for found_one in found)
        elif node.type in wrappers:
            wrapper = wrappers[node.type]
            if wrapper.child_field is None:
                inner = node.named_children
            else:
                child = node.child_by_field_name(wrapper.child_field)
                inner = [child] if child is not None else []
            symbols.extend(
                _walk(
                    spec,
                    inner,
                    context,
                    declarations,
                    wrappers,
                    node if wrapper.widens_span else span,
                )
            )
        leading = []
    return symbols


def _symbol(
    spec: LanguageSpec,
    found: Declaration,
    context: Context,
    leading: Sequence[Node],
    inherited_span: Node | None,
) -> SymbolNode:
    span = found.span or inherited_span or found.owner
    start = leading[0] if leading else span
    body = found.owner.child_by_field_name("body")
    signature_end = body.start_byte if body is not None else found.owner.end_byte
    prefix = found.qualifier if found.qualifier is not None else context.parent_name
    qualified = f"{prefix}{spec.separator}{found.name}" if prefix else found.name
    children: list[SymbolNode] = []
    if found.kind in spec.containers:
        member_field = spec.containers[found.kind]
        members = (
            found.owner
            if member_field is None
            else found.owner.child_by_field_name(member_field)
        )
        if members is not None:
            scope = replace(context, parent_kind=found.kind, parent_name=qualified)
            if spec.member_declarations is None:
                rules, wrappers = spec.declarations, spec.wrappers
            else:
                rules, wrappers = spec.member_declarations, {}
            children = _walk(spec, members.named_children, scope, rules, wrappers)
    return SymbolNode(
        kind=found.kind,
        name=found.name,
        qualified_name=qualified,
        signature=context.data[start.start_byte : signature_end].decode("utf-8").strip(),
        start_line=start.start_point.row + 1,
        # A span ending at column 0 ends on the previous line.
        end_line=span.end_point.row + (1 if span.end_point.column else 0),
        children=tuple(children),
    )


@dataclass(frozen=True, slots=True)
class TreeSitterLanguage:
    """The workflow's ``LanguageAdapter`` contract, for any described language."""

    spec: LanguageSpec

    @property
    def language(self) -> str:
        return self.spec.language

    @property
    def extension(self) -> str:
        return self.spec.extension

    @property
    def extensions(self) -> tuple[str, ...]:
        return self.spec.extensions

    @property
    def prompts(self) -> LanguagePrompts:
        return self.spec.prompts

    def is_source_path(self, path: str) -> bool:
        return path.endswith(self.spec.extensions) and not any(
            part in self.spec.skip_directories or part.startswith(self.spec.skip_prefixes)
            for part in PurePosixPath(path).parts
        )

    def is_test_path(self, path: str) -> bool:
        return self.spec.test_paths.matches(path)

    def parse_file(self, path: str, source: str) -> FileNode:
        return extract(self.spec, path, source)

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
        return resolve_symbol_locations(
            locations,
            file_node,
            source,
            context_window=context_window,
            separate_intervals=separate_intervals,
            fine_grained_only=fine_grained_only,
            remove_line_locations=remove_line_locations,
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
            raise ValueError(
                f"assignment compression is not implemented for {self.spec.display_name}"
            )
        _, data, root = parse(self.spec, path, source)
        return hide_bodies(
            data, root, self.spec.elided_bodies, self.spec.block_bodies
        ).decode("utf-8")

    def strip_comments(self, source: str, *, path: str | None = None) -> str:
        _, data, root = parse(self.spec, path, source)
        return strip_comments(data, root, self.spec.comment_node_types).decode("utf-8")
