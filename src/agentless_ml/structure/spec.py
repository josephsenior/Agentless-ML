"""The vocabulary for describing a language to the structure engine.

A ``LanguageSpec`` is data: file extensions and grammars, path policy, which
syntax node types declare symbols, which contain members, and which have bodies
to hide. The engine asks it a fixed set of questions and never branches on a
language name.

Most declarations are pure lookups (``struct_item`` declares a ``struct``), built
from ``declares``, ``declares_each`` and ``binds``. A few answers genuinely need
navigation through the tree first, such as a Go method's receiver type. Those
stay as small named functions passed into the same slots, and return the same
kind of answer.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import PurePosixPath

from tree_sitter import Node

from agentless_ml.schemas.prompts import LanguagePrompts


@dataclass(frozen=True, slots=True)
class Grammar:
    """A tree-sitter grammar and the ``FileNode.language`` label of its files."""

    language: str
    load: Callable[[], object]


@dataclass(frozen=True, slots=True)
class Naming:
    """How a name node spells a symbol name.

    ``literal`` node types are spelled by their source text (``None`` accepts any
    node). ``quoted`` types drop their surrounding quotes. ``chains`` join a
    left and right field, as in ``module.exports.api``. Anything else has no
    name, so the engine invents no symbol for it.
    """

    literal: frozenset[str] | None = None
    quoted: frozenset[str] = frozenset()
    chains: Mapping[str, tuple[str, str]] = field(default_factory=dict)
    chain_separator: str = "."

    def resolve(self, node: Node | None, text: Callable[[Node], str]) -> str | None:
        if node is None:
            return None
        if node.type in self.quoted:
            return text(node)[1:-1]
        if node.type in self.chains:
            left, right = self.chains[node.type]
            owner = self.resolve(node.child_by_field_name(left), text)
            member = self.resolve(node.child_by_field_name(right), text)
            return f"{owner}{self.chain_separator}{member}" if owner and member else None
        if self.literal is None or node.type in self.literal:
            return text(node)
        return None


@dataclass(frozen=True, slots=True)
class TestPaths:
    """Path rules that mark a file as a test; any matching rule is enough."""

    __test__ = False  # A path policy, not a pytest test class.

    suffixes: tuple[str, ...] = ()
    directories: frozenset[str] = frozenset()
    stem_suffixes: tuple[str, ...] = ()

    def matches(self, path: str) -> bool:
        pure = PurePosixPath(path)
        return (
            path.endswith(self.suffixes)
            or any(part in self.directories for part in pure.parts)
            or pure.stem.endswith(self.stem_suffixes)
        )


@dataclass(frozen=True, slots=True)
class Wrapper:
    """A syntax node that is not a symbol but contains declarations.

    ``child_field`` limits the search to one field; ``None`` searches every named
    child. With ``widens_span``, symbols found inside take their source span
    from the wrapper, as ``export`` does for the declaration it exports.
    """

    child_field: str | None = None
    widens_span: bool = False


@dataclass(frozen=True, slots=True)
class Declaration:
    """One symbol a rule found in the syntax tree.

    ``owner`` holds the symbol's body and members; the signature ends where its
    body begins. ``span`` overrides the source region when it differs from the
    owner's. ``qualifier`` replaces the lexical parent as the qualified-name
    prefix, for symbols owned by something they are not nested in.
    """

    owner: Node
    name: str
    kind: str
    span: Node | None = None
    qualifier: str | None = None


@dataclass(frozen=True, slots=True)
class Context:
    """What a declaration rule can see about where it is."""

    data: bytes
    naming: Naming
    parent_kind: str | None = None
    parent_name: str | None = None

    def text(self, node: Node) -> str:
        return self.data[node.start_byte : node.end_byte].decode("utf-8")

    def name(self, node: Node | None) -> str | None:
        return self.naming.resolve(node, self.text)


Rule = Callable[[Node, Context], Iterable[Declaration]]


def _field(node: Node, fields: Sequence[str]) -> Node | None:
    return next(
        (child for name in fields if (child := node.child_by_field_name(name)) is not None),
        None,
    )


def declares(
    kind: str,
    *,
    name_fields: Sequence[str] = ("name",),
    name: Callable[[Node, Context], str | None] | None = None,
    kind_within: Mapping[str, str] | None = None,
    kind_by_field: tuple[str, Mapping[str, str]] | None = None,
    qualifier: Callable[[Node, Context], str] | None = None,
) -> Rule:
    """A node that declares one named symbol.

    ``kind_within`` changes the kind by enclosing container kind (a function in an
    ``impl`` is a method). ``kind_by_field`` changes it by a field's node type (a
    type whose ``type`` field is a ``struct_type`` is a struct).
    """

    def rule(node: Node, context: Context) -> Iterable[Declaration]:
        resolved = name(node, context) if name else context.name(_field(node, name_fields))
        if not resolved:
            return ()
        resolved_kind = kind
        if kind_within and context.parent_kind is not None and context.parent_kind in kind_within:
            resolved_kind = kind_within[context.parent_kind]
        if kind_by_field:
            typed = node.child_by_field_name(kind_by_field[0])
            if typed is not None:
                resolved_kind = kind_by_field[1].get(typed.type, kind)
        return (
            Declaration(
                node,
                resolved,
                resolved_kind,
                qualifier=qualifier(node, context) if qualifier else None,
            ),
        )

    return rule


def declares_each(
    kind: str, *, name_field: str = "name", skip: frozenset[str] = frozenset()
) -> Rule:
    """A node that declares one symbol per name, as in ``var a, b = 1, 2``."""

    def rule(node: Node, context: Context) -> Iterable[Declaration]:
        for name_node in node.children_by_field_name(name_field):
            name = context.name(name_node)
            if name and name not in skip:
                yield Declaration(node, name, kind)

    return rule


def binds(
    kind: str | Callable[[Node], str],
    *,
    value_kinds: Mapping[str, str],
    name_fields: Sequence[str] = ("name",),
    value_field: str = "value",
) -> Rule:
    """A name bound to a value, whose kind comes from the value when it can.

    When the value's node type is in ``value_kinds``, the value owns the symbol
    (its body and members) while the binding keeps the source span. Otherwise the
    binding itself is the symbol, of ``kind``.
    """

    def rule(node: Node, context: Context) -> Iterable[Declaration]:
        name = context.name(_field(node, name_fields))
        if not name:
            return ()
        value = node.child_by_field_name(value_field)
        if value is not None and value.type in value_kinds:
            return (Declaration(value, name, value_kinds[value.type], span=node),)
        return (Declaration(node, name, kind(node) if callable(kind) else kind, span=node),)

    return rule


@dataclass(frozen=True, slots=True)
class LanguageSpec:
    """Everything the engine needs to know about one language."""

    language: str
    display_name: str
    extension: str
    extensions: tuple[str, ...]
    grammars: Mapping[str, Grammar]
    skip_directories: frozenset[str]
    skip_prefixes: tuple[str, ...]
    test_paths: TestPaths
    declarations: Mapping[str, Rule]
    elided_bodies: frozenset[str]
    block_bodies: frozenset[str]
    prompts: LanguagePrompts
    wrappers: Mapping[str, Wrapper] = field(default_factory=dict)
    containers: Mapping[str, str | None] = field(default_factory=dict)
    member_declarations: Mapping[str, Rule] | None = None
    leading: frozenset[str] = frozenset()
    ignored: frozenset[str] = frozenset()
    requires: Mapping[str, str] = field(default_factory=dict)
    separator: str = "."
    naming: Naming = field(default_factory=Naming)
    # Node types this language's grammar uses for comments, including doc
    # comments where those are a distinct node type. Used only to build the
    # repair voting key (``repair/patches.py``), never to render prompts.
    comment_node_types: frozenset[str] = frozenset()
