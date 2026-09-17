"""Rust, described for the structure engine; no macro expansion or build scripts.

See ``docs/rust-adapter.md``.
"""

import tree_sitter_rust
from tree_sitter import Node

from agentless_ml.schemas.prompts import (
    LanguagePrompts,
    RepairExample,
    guided_symbol_localization,
)
from agentless_ml.structure.spec import (
    Context,
    Grammar,
    LanguageSpec,
    TestPaths,
    declares,
)


def _impl_name(node: Node, context: Context) -> str:
    """``impl Counter`` is ``Counter``; ``impl Reset for Counter`` is ``<Counter as Reset>``."""
    type_field = node.child_by_field_name("type")
    assert type_field is not None  # grammar: every impl_item has a type
    name = context.text(type_field)
    trait = node.child_by_field_name("trait")
    return f"<{name} as {context.text(trait)}>" if trait is not None else name


RUST = LanguageSpec(
    language="rust",
    display_name="Rust",
    extension=".rs",
    extensions=(".rs",),
    grammars={".rs": Grammar("rust", tree_sitter_rust.language)},
    skip_directories=frozenset({"target", "vendor"}),
    skip_prefixes=(".",),
    test_paths=TestPaths(directories=frozenset({"tests", "benches"})),
    # ``///``/``//!`` doc comments nest a ``doc_comment`` child inside a
    # ``line_comment`` node rather than being a sibling node type of their own,
    # so matching these two covers doc comments too without listing them.
    comment_node_types=frozenset({"line_comment", "block_comment"}),
    declarations={
        "function_item": declares(
            "function", kind_within={"impl": "method", "trait": "method"}
        ),
        "function_signature_item": declares("method"),
        "struct_item": declares("struct"),
        "enum_item": declares("enum"),
        "union_item": declares("type"),
        "trait_item": declares("trait"),
        "type_item": declares("type"),
        "associated_type": declares("type"),
        "const_item": declares("constant"),
        "static_item": declares("variable"),
        "mod_item": declares("module"),
        "field_declaration": declares("field"),
        "enum_variant": declares("variant"),
        "impl_item": declares("impl", name=_impl_name),
    },
    containers=dict.fromkeys(("impl", "trait", "module", "struct", "enum", "type"), "body"),
    # Attributes belong to the item they annotate: they extend its edit region.
    leading=frozenset({"attribute_item"}),
    ignored=frozenset({"line_comment", "block_comment"}),
    separator="::",
    elided_bodies=frozenset({"function_item"}),
    block_bodies=frozenset({"block"}),
    prompts=LanguagePrompts(
        symbol_localization=guided_symbol_localization(
            targets="functions, methods, types, traits, impl blocks, modules or constants",
            naming=(
                "Use source-spelled names with :: separators. Inherent methods use Counter::add;\n"
                "trait implementations use <Counter as Reset>::reset. Include generic arguments\n"
                "as written in the impl type. Inline modules add their name as a prefix.\n"
                "A struct does not include its separate impl blocks. Ambiguous names need qualification\n"
                "or an exact line location. Macro-generated declarations are not expanded."
            ),
            example=(
                "src/lib.rs\nfunction: add\nmethod: Counter::add\ntype: Counter\n"
                "trait: Reset\nimpl: <Counter as Reset>\nmodule: helpers\nconstant: LIMIT"
            ),
        ),
        repair_example=RepairExample(
            path="src/lib.rs",
            search="a - b",
            replace="a + b",
            indented_line="    dbg!(x);",
        ),
    ),
)
