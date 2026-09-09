from pathlib import Path

import pytest

from agentless_ml.adapters.languages import GoAdapter, get_language_adapter
from agentless_ml.localization.context import (
    render_file_localization_prompt,
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

SOURCE = (Path(__file__).parent / "fixtures/go/structure.go").read_text(
    encoding="utf-8"
)


def test_go_declarations_and_source_spans():
    node = GoAdapter().parse_file("sample.go", SOURCE)
    by_name = {s.qualified_name: s for s in node.symbols}
    assert list(by_name) == [
        "Counter",
        "Reader",
        "Alias",
        "First",
        "Second",
        "Message",
        "Zero",
        "One",
        "Counter.Add",
        "Format",
    ]
    assert by_name["Counter"].kind == "struct"
    assert by_name["Reader"].children[0].qualified_name == "Reader.Read"
    assert by_name["One"].kind == "constant"
    method = by_name["Counter.Add"]
    assert method.kind == "method"
    assert method.signature == "func (c *Counter[T]) Add(v T) T"
    assert SOURCE.splitlines()[method.start_line - 1] == method.signature + " {"
    assert SOURCE.splitlines()[method.end_line - 1] == "}"
    assert not by_name["Counter"].children  # Receiver ownership is not lexical nesting.


def test_go_skeleton_uses_syntax_spans_and_preserves_unicode():
    skeleton = GoAdapter().render_skeleton(SOURCE)
    assert "c.Value += v" not in skeleton
    assert "format := func()" not in skeleton
    assert "café" in skeleton
    assert "func (c *Counter[T]) Add(v T) T { ... }" in skeleton
    assert "Read(p []byte) (int, error)" in skeleton
    assert 'import "fmt"' in skeleton
    assert (
        GoAdapter().render_skeleton(SOURCE.replace("\n", "\r\n")).count("{ ... }") == 2
    )


@pytest.mark.parametrize(
    "source", ["func F() {}", "package p\nfunc F( {", "package p\nfunc F() {"]
)
def test_invalid_go_fails_explicitly(source):
    with pytest.raises(ValueError, match="Go source"):
        GoAdapter().parse_file("bad.go", source)


def test_grouped_types_value_receiver_and_bodyless_declaration():
    source = (
        "package p\ntype (\n ID int\n Alias = ID\n)\n"
        "func (id ID) Value() int { return int(id) }\n"
        "func external()\n"
    )
    node = GoAdapter().parse_file("id.go", source)
    assert [s.qualified_name for s in node.symbols] == [
        "ID",
        "Alias",
        "ID.Value",
        "external",
    ]
    skeleton = GoAdapter().render_skeleton(source)
    assert "func external()" in skeleton and "return int(id)" not in skeleton
    with pytest.raises(ValueError, match="compression"):
        GoAdapter().render_skeleton(source, compress_assign=True)


def test_go_localization_and_context():
    node = GoAdapter().parse_file("sample.go", SOURCE)
    locations = parse_locations_for_files(
        ["sample.go\nmethod: Counter.Add\nconstant: One"],
        ["sample.go"],
        extension=".go",
    )
    resolved = resolve_locations(locations["sample.go"], node, SOURCE, context_window=0)
    assert resolved.is_valid and not resolved.unrecognized
    assert len(resolved.line_intervals) == 2
    context, intervals = construct_selected_context(
        locations,
        {"sample.go": node},
        {"sample.go": SOURCE},
        context_window=0,
    )
    assert "c.Value += v" in context and "One" in context
    assert "fmt.Sprintf" not in context
    assert intervals["sample.go"]


def test_receiver_in_other_file_and_ambiguous_bare_method():
    source = "package p\nfunc (a A) Run() {}\nfunc (b *B) Run() {}\n"
    node = GoAdapter().parse_file("methods.go", source)
    assert resolve_locations("method: A.Run", node, source).line_intervals == ((2, 2),)
    assert not resolve_locations("method: Run", node, source).is_valid
    assert not resolve_locations("line: 0\nline: 999\nline:", node, source).is_valid
    assert not resolve_locations("type: A", node, source).is_valid


def test_go_paths_and_prompts():
    adapter = get_language_adapter("GO")
    paths = (
        "repo/main.go",
        "repo/main_test.go",
        "repo/vendor/x.go",
        "repo/testdata/x.go",
        "repo/_hidden.go",
        "repo/.cache/x.go",
        "repo/a.py",
    )
    tree = render_project_tree(paths, adapter=adapter)
    assert tree == "repo/\n    main.go\n"
    assert parse_file_locations(
        "repo/main.go\n../x.go\na.py\nunknown.go",
        ("main.go", "a.py"),
        repository_name="repo",
        extension=".go",
    ) == ("main.go",)
    assert "file1.go" in render_file_localization_prompt("bug", tree, extension=".go")
    prompt = render_symbol_localization_prompt(
        "bug", {"sample.go": SOURCE}, adapter=adapter
    )
    assert "method: Counter.Add" in prompt and "```go" in prompt
    assert "class:" not in prompt and "file1.py" not in prompt
    repair = build_repair_prompt("bug", "selected source", language="go")
    assert "```go" in repair and "format.go" in repair and "flask" not in repair
    with pytest.raises(ValueError, match="unsupported"):
        get_language_adapter("ruby")
