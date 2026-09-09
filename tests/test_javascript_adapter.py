from pathlib import Path

import pytest

from agentless_ml.adapters.languages import (
    JavaScriptAdapter,
    TypeScriptAdapter,
    get_language_adapter,
)
from agentless_ml.localization.context import (
    render_project_tree,
    render_symbol_localization_prompt,
)
from agentless_ml.localization.locations import (
    construct_selected_context,
    parse_file_locations,
    parse_locations_for_files,
    resolve_locations,
)
from agentless_ml.repair import build_repair_prompt

SOURCE = (Path(__file__).parent / "fixtures/javascript/structure.ts").read_text(
    encoding="utf-8"
)


def test_typescript_declarations_and_lexical_children():
    node = TypeScriptAdapter().parse_file("structure.ts", SOURCE)
    symbols = {s.name: s for s in node.symbols}
    assert list(symbols) == [
        "Reader",
        "ID",
        "State",
        "Counter",
        "add",
        "fetchValue",
        "api",
        "external",
    ]
    assert symbols["Reader"].kind == "interface"
    assert symbols["ID"].kind == "type"
    assert symbols["State"].kind == "enum"
    assert symbols["add"].kind == "function"
    assert symbols["Counter"].signature == "export default class Counter<T>"
    assert [(c.qualified_name, c.kind) for c in symbols["Counter"].children] == [
        ("Counter.value", "field"),
        ("Counter.constructor", "method"),
        ("Counter.add", "method"),
        ("Counter.create", "method"),
        ("Counter.size", "method"),
    ]
    assert [c.qualified_name for c in symbols["api"].children] == [
        "api.run",
        "api.stop",
        "api.label",
    ]
    method = symbols["Counter"].children[2]
    assert "add =" in SOURCE.splitlines()[method.start_line - 1]
    assert method.start_line == method.end_line


@pytest.mark.parametrize(
    "adapter,path",
    [(JavaScriptAdapter(), "example.js"), (TypeScriptAdapter(), "example.ts")],
)
def test_exports_bound_functions_and_class_expressions(adapter, path):
    source = (
        "export function* items() { yield 1; }\n"
        "const f = function inner() { return 2; };\n"
        "const C = class { #value = 1; run() { return this.#value; } };\n"
        "export default (x) => ({ value: x });\n"
        "exports.add = (a, b) => a + b;\n"
        "module.exports.api = { run() { return 1; } };\n"
        "export { items as values };\n"
    )
    node = adapter.parse_file(path, source)
    assert [s.qualified_name for s in node.symbols] == [
        "items",
        "f",
        "C",
        "default",
        "exports.add",
        "module.exports.api",
    ]
    assert node.symbols[2].children[0].qualified_name == "C.#value"
    assert resolve_locations("method: module.exports.api.run", node, source).is_valid
    assert resolve_locations("function: default", node, source).is_valid
    assert not resolve_locations("function: inner", node, source).is_valid


def test_typescript_and_tsx_use_different_grammars():
    adapter = TypeScriptAdapter()
    source = "export const Component = (p: {label: string}) => <div>{p.label}</div>;"
    node = adapter.parse_file("component.tsx", source)
    assert node.symbols[0].name == "Component"
    assert "<div>" not in adapter.render_skeleton(source, path="component.tsx")
    # Angle-bracket type assertions require TS, not TSX.
    assert (
        adapter.parse_file("cast.ts", "const x = <number>value;").symbols[0].name == "x"
    )
    with pytest.raises(ValueError, match="syntax"):
        adapter.parse_file("cast.tsx", "const x = <number>value;")
    assert (
        JavaScriptAdapter()
        .parse_file("component.jsx", "const View = () => <div/>;")
        .symbols
    )


def test_skeleton_hides_bodies_and_keeps_declarations_and_unicode():
    source = 'const café = "} 😀";\n' + SOURCE
    skeleton = TypeScriptAdapter().render_skeleton(source)
    assert "café" in skeleton and "😀" in skeleton
    assert "import type" in skeleton and "export interface Reader" in skeleton
    assert "return this.value" not in skeleton and "a + b" not in skeleton
    assert "add = (amount: number): number => ..." in skeleton
    assert "declare function external" in skeleton
    crlf = TypeScriptAdapter().render_skeleton(source.replace("\n", "\r\n"))
    assert crlf.replace("\r\n", "\n") == skeleton


def test_locations_resolve_types_fields_methods_and_ambiguity():
    adapter = TypeScriptAdapter()
    node = adapter.parse_file("structure.ts", SOURCE)
    locations = "method: Counter.add\nfield: Counter.value\ntype: ID"
    result = resolve_locations(locations, node, SOURCE, context_window=0)
    assert len(result.line_intervals) == 3 and not result.unrecognized
    context, intervals = construct_selected_context(
        {"structure.ts": locations},
        {"structure.ts": node},
        {"structure.ts": SOURCE},
        context_window=0,
    )
    assert "amount" in context and "private value" in context and "type ID" in context
    assert "fetchValue" not in context and intervals["structure.ts"]
    ambiguous = "class C { get x() { return 1; } set x(v) {} }"
    assert not resolve_locations(
        "method: C.x", adapter.parse_file("a.ts", ambiguous), ambiguous
    ).is_valid


def test_mixed_repository_paths_and_prompts():
    adapter = get_language_adapter("typescript")
    paths = (
        "repo/main.ts",
        "repo/view.tsx",
        "repo/helper.js",
        "repo/helper.mjs",
        "repo/main.test.ts",
        "repo/tests/a.js",
        "repo/node_modules/a.js",
        "repo/dist/a.ts",
        "repo/schema.d.ts",
        "repo/python.py",
    )
    tree = render_project_tree(paths, adapter=adapter)
    assert all(
        p in tree
        for p in ("main.ts", "view.tsx", "helper.js", "helper.mjs", "schema.d.ts")
    )
    assert all(
        p not in tree for p in ("node_modules", "main.test", "tests", "dist", "python")
    )
    assert not JavaScriptAdapter().is_source_path("main.ts")
    chosen = parse_file_locations(
        "main.ts\nhelper.js\n../view.tsx",
        ("main.ts", "helper.js"),
        extension=adapter.extensions,
    )
    assert chosen == ("main.ts", "helper.js")
    parsed = parse_locations_for_files(
        ["main.ts\nfunction: add\nmissing.js\nfunction: wrong\nhelper.js\nconstant: n"],
        chosen,
        extension=adapter.extensions,
    )
    assert parsed == {"main.ts": ["function: add"], "helper.js": ["constant: n"]}
    prompt = render_symbol_localization_prompt(
        "bug",
        {
            "view.tsx": "export const View = () => <div/>;",
            "helper.js": "const n = 1;",
        },
        adapter=adapter,
    )
    assert (
        "```tsx" in prompt
        and "```javascript" in prompt
        and "method: Counter.add" in prompt
    )
    for language in ("javascript", "typescript"):
        repair = build_repair_prompt("bug", "source", language=language)
        assert "flask" not in repair and "```" + language in repair


@pytest.mark.parametrize(
    "source", ["function broken( {", "const x = ;", "class A { run() {"]
)
def test_syntax_errors_fail_explicitly(source):
    for adapter, path in (
        (JavaScriptAdapter(), "bad.js"),
        (TypeScriptAdapter(), "bad.ts"),
    ):
        with pytest.raises(ValueError, match="syntax"):
            adapter.parse_file(path, source)


def test_ambient_abstract_and_anonymous_default_declarations():
    source = (
        "export abstract class Base { abstract run(x: number): void; }\n"
        "export default class { value = 1; }\n"
        "declare const api: string;\nconst\nlimit = 1;\n"
    )
    node = TypeScriptAdapter().parse_file("declarations.ts", source)
    assert [(s.name, s.kind) for s in node.symbols] == [
        ("Base", "class"),
        ("default", "class"),
        ("api", "constant"),
        ("limit", "constant"),
    ]
    assert node.symbols[0].children[0].qualified_name == "Base.run"
    assert node.symbols[1].children[0].qualified_name == "default.value"
    assert resolve_locations(
        "constant: limit", node, source, context_window=0
    ).line_intervals == ((5, 5),)


def test_unsupported_constructs_are_visible_without_invented_symbols():
    source = "const {x, y: alias} = value;\nconst api = { [key]() { return 1; } };"
    adapter = JavaScriptAdapter()
    node = adapter.parse_file("a.js", source)
    assert [s.name for s in node.symbols] == ["api"]
    assert not node.symbols[0].children
    assert "{x, y: alias}" in adapter.render_skeleton(source)
    assert resolve_locations("line: 1", node, source).is_valid
