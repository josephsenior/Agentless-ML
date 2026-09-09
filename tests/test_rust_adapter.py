import pytest

from agentless_ml.adapters.languages import RustAdapter, get_language_adapter
from agentless_ml.localization.context import render_symbol_localization_prompt
from agentless_ml.localization.locations import (
    parse_locations_for_files,
    resolve_locations,
)
from agentless_ml.repair import build_repair_prompt

SOURCE = """#[derive(Debug)]
pub struct Counter { pub value: i32 }
trait Reset { fn reset(&mut self); }
impl Counter {
    fn reset(&mut self) { self.value = 1; }
}
impl Reset for Counter {
    fn reset(&mut self) { self.value = 0; }
}
mod helpers {
    pub const LABEL: &str = "café";
    pub fn add(a: i32, b: i32) -> i32 { a + b }
}
"""


def test_rust_structure_and_lexical_spans():
    node = RustAdapter().parse_file("lib.rs", SOURCE)
    assert [s.qualified_name for s in node.symbols] == [
        "Counter",
        "Reset",
        "Counter",
        "<Counter as Reset>",
        "helpers",
    ]
    assert node.symbols[0].start_line == 1
    assert node.symbols[0].children[0].qualified_name == "Counter::value"
    assert node.symbols[2].children[0].qualified_name == "Counter::reset"
    assert node.symbols[3].children[0].qualified_name == "<Counter as Reset>::reset"
    assert node.symbols[4].children[1].qualified_name == "helpers::add"


def test_rust_qualified_localization_and_ambiguity():
    node = RustAdapter().parse_file("lib.rs", SOURCE)
    locations = parse_locations_for_files(
        ["lib.rs\nmethod: <Counter as Reset>::reset\nconstant: helpers::LABEL"],
        ["lib.rs"],
        extension=".rs",
    )
    result = resolve_locations(locations["lib.rs"], node, SOURCE, context_window=0)
    assert result.is_valid and not result.unrecognized
    assert result.line_intervals == ((8, 8), (11, 11))
    assert resolve_locations("method: reset", node, SOURCE).unrecognized
    assert resolve_locations("trait: Reset", node, SOURCE).is_valid
    assert resolve_locations("module: helpers", node, SOURCE).is_valid


def test_rust_skeleton_and_prompts():
    adapter = get_language_adapter("Rust")
    skeleton = adapter.render_skeleton(SOURCE)
    assert "self.value =" not in skeleton and "café" in skeleton
    assert "fn reset(&mut self);" in skeleton
    assert skeleton.count("{ ... }") == 3
    assert adapter.render_skeleton(SOURCE.replace("\n", "\r\n")).count("{ ... }") == 3
    prompt = render_symbol_localization_prompt(
        "bug", {"lib.rs": SOURCE}, adapter=adapter
    )
    assert "```rust" in prompt and "method: Counter::add" in prompt
    repair = build_repair_prompt("bug", "source", language="rust")
    assert "src/lib.rs" in repair and "flask" not in repair


def test_rust_generics_macros_and_empty_source():
    source = "impl<T> Box<T> { fn get(&self) -> &T { &self.0 } }\nmake_items!();"
    node = RustAdapter().parse_file("lib.rs", source)
    assert node.symbols[0].children[0].qualified_name == "Box<T>::get"
    assert "make_items!();" in RustAdapter().render_skeleton(source)
    assert RustAdapter().parse_file("lib.rs", "").symbols == ()
    with pytest.raises(ValueError, match="syntax"):
        RustAdapter().parse_file("lib.rs", "fn broken( {")
    with pytest.raises(ValueError, match="compression"):
        RustAdapter().render_skeleton(SOURCE, compress_assign=True)


@pytest.mark.parametrize(
    "path", ["target/debug/generated.rs", "vendor/lib.rs", ".git/a.rs", "lib.py"]
)
def test_rust_excludes_non_source_paths(path):
    assert not RustAdapter().is_source_path(path)


def test_rust_path_policy():
    assert RustAdapter().is_source_path("src/lib.rs")
    assert RustAdapter().is_test_path("tests/integration.rs")
    assert not RustAdapter().is_test_path("src/lib.rs")
