"""Go, described for the structure engine. See ``docs/go-adapter.md``."""

import tree_sitter_go
from tree_sitter import Node

from agentless_ml.structure.spec import (
    Context,
    Grammar,
    LanguageSpec,
    TestPaths,
    Wrapper,
    declares,
    declares_each,
)


def _receiver(node: Node, context: Context) -> str:
    """The receiver type that owns a method, without pointer or type arguments.

    Methods are top-level declarations whose owner need not be in the same file,
    so ``func (c *Counter[T]) Add`` is ``Counter.Add`` rather than a child of
    ``Counter``.
    """
    receiver = node.child_by_field_name("receiver")
    parameter = next(
        n for n in receiver.named_children if n.type == "parameter_declaration"
    )
    receiver_type = parameter.child_by_field_name("type")
    if receiver_type.type == "pointer_type":
        receiver_type = receiver_type.named_children[0]
    if receiver_type.type == "generic_type":
        receiver_type = receiver_type.child_by_field_name("type")
    return context.text(receiver_type)


_TYPE = declares(
    "type",
    kind_by_field=("type", {"struct_type": "struct", "interface_type": "interface"}),
)

GO = LanguageSpec(
    language="go",
    display_name="Go",
    extension=".go",
    extensions=(".go",),
    grammars={".go": Grammar("go", tree_sitter_go.language)},
    skip_directories=frozenset({"vendor", "testdata"}),
    skip_prefixes=(".", "_"),
    test_paths=TestPaths(suffixes=("_test.go",)),
    requires={"package_clause": "a package"},
    declarations={
        "function_declaration": declares("function"),
        "method_declaration": declares("method", qualifier=_receiver),
        "type_spec": _TYPE,
        "type_alias": _TYPE,
        "var_spec": declares_each("variable", skip=frozenset({"_"})),
        "const_spec": declares_each("constant", skip=frozenset({"_"})),
    },
    # Grouped declarations: only var groups add a list node; const groups do not.
    wrappers={
        "type_declaration": Wrapper(),
        "var_declaration": Wrapper(),
        "var_spec_list": Wrapper(),
        "const_declaration": Wrapper(),
    },
    containers={"interface": "type"},
    member_declarations={"method_elem": declares("method")},
    elided_bodies=frozenset({"function_declaration", "method_declaration"}),
    block_bodies=frozenset({"block"}),
)
