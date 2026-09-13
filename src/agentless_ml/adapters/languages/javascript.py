"""JavaScript and TypeScript, described for the structure engine.

See ``docs/javascript-typescript.md`` for naming rules and limitations.
"""

from dataclasses import replace

import tree_sitter_javascript
import tree_sitter_typescript
from tree_sitter import Node

from agentless_ml.structure.spec import (
    Context,
    Declaration,
    Grammar,
    LanguageSpec,
    Naming,
    TestPaths,
    Wrapper,
    binds,
    declares,
)

_JS_EXTENSIONS = (".js", ".jsx", ".mjs", ".cjs")
_TS_EXTENSIONS = (".ts", ".tsx", ".mts", ".cts")
_FUNCTIONS = (
    "function_declaration",
    "generator_function_declaration",
    "function_expression",
    "generator_function",
    "arrow_function",
    "function_signature",
)
_CLASSES = ("class", "class_declaration", "abstract_class_declaration")
_METHODS = ("method_definition", "method_signature", "abstract_method_signature")
_FIELDS = ("field_definition", "public_field_definition", "property_signature", "pair")
_MEMBER_NAME = ("name", "key", "property")
_VALUE_KINDS = {
    **dict.fromkeys(_FUNCTIONS, "function"),
    **dict.fromkeys(_CLASSES, "class"),
    "object": "object",
}


def _binding_kind(declarator: Node) -> str:
    return (
        "constant"
        if any(child.type == "const" for child in declarator.parent.children)
        else "variable"
    )


def _default_export(node: Node, context: Context):
    """``export default <value>``: named by the value if it has a name."""
    if node.child_by_field_name("declaration") is not None:
        return  # The export wrapper handles exported declarations.
    value = node.child_by_field_name("value")
    if value is not None:
        name = context.name(value.child_by_field_name("name")) or "default"
        yield Declaration(value, name, _VALUE_KINDS.get(value.type, "constant"), span=node)


def _commonjs_export(node: Node, context: Context):
    """``module.exports = ...`` and ``exports.name = ...`` at the top level."""
    if node.named_child_count != 1 or node.named_children[0].type != "assignment_expression":
        return
    assignment = node.named_children[0]
    name = context.name(assignment.child_by_field_name("left"))
    if name and (
        name == "module.exports" or name.startswith(("exports.", "module.exports."))
    ):
        value = assignment.child_by_field_name("right")
        yield Declaration(
            value, name, _VALUE_KINDS.get(value.type, "variable"), span=assignment
        )


_javascript_grammar = Grammar("javascript", tree_sitter_javascript.language)

JAVASCRIPT = LanguageSpec(
    language="javascript",
    display_name="JavaScript/TypeScript",
    extension=".js",
    extensions=_JS_EXTENSIONS,
    grammars=dict.fromkeys(_JS_EXTENSIONS, _javascript_grammar),
    skip_directories=frozenset({"node_modules", "vendor", "dist", "build", "coverage"}),
    skip_prefixes=(".",),
    test_paths=TestPaths(
        directories=frozenset({"test", "tests", "__tests__", "__mocks__"}),
        stem_suffixes=(".test", ".spec"),
    ),
    # Keep literal key spelling; computed keys and escapes are not evaluated.
    naming=Naming(
        literal=frozenset(
            {
                "identifier",
                "type_identifier",
                "property_identifier",
                "private_property_identifier",
                "number",
            }
        ),
        quoted=frozenset({"string"}),
        chains={"member_expression": ("object", "property")},
    ),
    declarations={
        **dict.fromkeys(_FUNCTIONS, declares("function")),
        **dict.fromkeys(_CLASSES, declares("class")),
        "interface_declaration": declares("interface"),
        "type_alias_declaration": declares("type"),
        "enum_declaration": declares("enum"),
        "variable_declarator": binds(_binding_kind, value_kinds=_VALUE_KINDS),
        "export_statement": _default_export,
        "expression_statement": _commonjs_export,
    },
    wrappers={
        "export_statement": Wrapper("declaration", widens_span=True),
        "ambient_declaration": Wrapper(widens_span=True),
        "lexical_declaration": Wrapper(),
        "variable_declaration": Wrapper(),
    },
    containers={"class": "body", "interface": "body", "object": None},
    member_declarations={
        **dict.fromkeys(_METHODS, declares("method", name_fields=_MEMBER_NAME)),
        **dict.fromkeys(
            _FIELDS,
            binds(
                "field",
                value_kinds=dict.fromkeys(_FUNCTIONS, "method"),
                name_fields=_MEMBER_NAME,
            ),
        ),
    },
    elided_bodies=frozenset(_FUNCTIONS + _METHODS),
    block_bodies=frozenset({"statement_block"}),
)

_typescript_grammar = Grammar("typescript", tree_sitter_typescript.language_typescript)

# Mixed JS/TS repositories are common; each file chooses its own grammar.
TYPESCRIPT = replace(
    JAVASCRIPT,
    language="typescript",
    extension=".ts",
    extensions=_TS_EXTENSIONS + _JS_EXTENSIONS,
    grammars={
        ".ts": _typescript_grammar,
        ".mts": _typescript_grammar,
        ".cts": _typescript_grammar,
        ".tsx": Grammar("typescript", tree_sitter_typescript.language_tsx),
        **JAVASCRIPT.grammars,
    },
)
