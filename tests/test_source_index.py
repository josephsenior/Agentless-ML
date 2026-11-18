"""The source-discovery prototype must expose uncertainty, not hide it."""

import importlib.util
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from agentless_ml.adapters.languages import get_language_adapter
from agentless_ml.localization.source_index import build_source_index, walk_symbols


def test_declaration_only_index_does_not_build_an_import_graph(monkeypatch):
    from agentless_ml.localization import source_index

    def forbidden(*args, **kwargs):
        raise AssertionError("declaration indexing must not analyze imports")

    monkeypatch.setattr(source_index, "_python_links", forbidden)
    monkeypatch.setattr(source_index, "_javascript_links", forbidden)
    index = source_index.build_declaration_index({
        "a.py": "import other\nSETTING = 1\ndef api(): pass\n",
        "b.ts": "import './a';\nexport const value = 1;\n",
        "lib.rs": "pub fn rust_api() {}\n",
    })
    assert index.links == () and index.diagnostics == ()
    text = index.render_declarations()
    assert "SETTING" in text and "rust_api" in text and "value" in text
    assert "Import links" not in text and "unsupported-import-analysis" not in text


def declarations(index, path):
    return {symbol.qualified_name: symbol for file in index.files if file.path == path
            for symbol in walk_symbols(file.symbols)}


def test_index_preserves_prototype_assignments_and_types_without_bodies():
    index = build_source_index({
        "src/entity.ts": (
            "Number.prototype.changed = function (trait: Trait) {\n return setChanged(trait);\n};\n"
        ),
        "src/types.ts": "export type Trait = number;\n",
    })
    symbol = declarations(index, "src/entity.ts")["Number.prototype.changed"]
    assert (symbol.start_line, symbol.end_line) == (1, 3)
    text = index.render()
    assert "function Number.prototype.changed" in text
    assert "type Trait" in text
    assert "return setChanged" not in text


def test_python_globals_include_conditional_destructuring_but_not_locals():
    source = """LIMIT = 10
if TYPE_CHECKING:
    Left, Right = pair
class C:
    class_only = 2
    def method(self):
        method_only = 3
def f():
    function_only = 4
"""
    before = get_language_adapter("python").parse_file("a.py", source)
    index = build_source_index({"a.py": source})
    assert set(declarations(index, "a.py")) == {"LIMIT", "Left", "Right", "C", "C.method", "f"}
    assert get_language_adapter("python").parse_file("a.py", source) == before
    assert "LIMIT" not in {symbol.name for symbol in before.symbols}


def test_import_closure_handles_barrels_side_effects_cycles_without_a_hop_limit():
    sources = {"src/start.ts": "import './index';\n"}
    sources.update({f"src/step{number}.ts": f"import './step{number + 1}';\n" for number in range(40)})
    sources["src/index.ts"] = "export * from './step0';\n"
    sources["src/step40.ts"] = "import './start';\n"
    index = build_source_index(sources)
    steps = index.expand(["src/start.ts", "src/start.ts"])
    assert {step.path for step in steps} == set(sources)
    assert next(step for step in steps if step.path == "src/step40.ts").via == "src/step39.ts"
    with pytest.raises(ValueError, match="absent"):
        index.expand(["not-indexed.ts"])


def test_javascript_ambiguous_static_candidates_are_all_kept():
    index = build_source_index({
        "a.js": (
            "import './b';\nimport '@/alias';\nrequire(computed);\n"
            "import(`./${name}`);\nrequire('./b' + suffix);\n"
        ),
        "b.ts": "export const b = 1;\n", "b.js": "export const b = 2;\n",
    })
    link = next(link for link in index.links if link.module == "./b")
    assert link.targets == ("b.js", "b.ts")
    assert link.status == "ambiguous"
    assert {step.path for step in index.expand(["a.js"])} == {"a.js", "b.js", "b.ts"}
    assert len([link for link in index.links if link.status == "dynamic"]) == 3
    assert any(link.module == "@/alias" and link.status == "unresolved" for link in index.links)


def test_javascript_literal_calls_and_transpiled_extensions():
    index = build_source_index({
        "src/a.ts": "const b = require('./b.js');\nimport('./nested');\n",
        "src/b.ts": "export function b() {}\n",
        "src/nested/index.ts": "export const c = 1;\n",
    })
    assert {step.path for step in index.expand(["src/a.ts"])} == {
        "src/a.ts", "src/b.ts", "src/nested/index.ts",
    }


def test_javascript_current_directory_import_reaches_root_index():
    index = build_source_index({
        "a.ts": "import './';\n", "index.ts": "export const setting = 1;\n",
    })
    assert {step.path for step in index.expand(["a.ts"])} == {"a.ts", "index.ts"}


def test_python_imports_follow_packages_aliases_relative_and_conditional_imports():
    index = build_source_index({
        "src/pkg/__init__.py": "SETTING = 1\n",
        "src/pkg/api.py": (
            "from .backend import Impl as Backend\nfrom . import helper\n"
            "if TYPE_CHECKING:\n    from pkg import types\n"
        ),
        "src/pkg/backend.py": "from pkg import api\nclass Impl: pass\n",
        "src/pkg/helper.py": "pass\n", "src/pkg/types.py": "pass\n",
        "src/pkg/unrelated.py": "pass\n",
    })
    paths = {step.path for step in index.expand(["src/pkg/api.py"])}
    assert paths == {
        "src/pkg/__init__.py", "src/pkg/api.py", "src/pkg/backend.py",
        "src/pkg/helper.py", "src/pkg/types.py",
    }
    assert "src/pkg/unrelated.py" not in paths


def test_python_dynamic_import_and_ambiguous_module_roots_are_visible():
    index = build_source_index({
        "a.py": "import pkg\nimportlib.import_module(name)\n__import__(name)\n",
        "pkg.py": "pass\n", "src/pkg.py": "pass\n",
    })
    link = next(link for link in index.links if link.module == "pkg")
    assert link.status == "ambiguous" and link.targets == ("pkg.py", "src/pkg.py")
    assert len([link for link in index.links if link.status == "dynamic"]) == 2


def test_python_relative_import_cannot_escape_module_root():
    index = build_source_index({"pkg/a.py": "from ...secret import value\n", "secret.py": "value = 1\n"})
    assert index.links[0].status == "unresolved"
    assert index.links[0].targets == ()
    assert len(index.expand(["pkg/a.py"])) == 1


def test_go_same_package_and_module_imports_include_factory_types():
    index = build_source_index({
        "parsing/format.go": (
            'package parsing\nimport "example.org/project/model"\nfunc Read(fn NewReaderFn) {}\n'
        ),
        "parsing/reader.go": (
            "package parsing\ntype NewReaderFn func() error\nvar readers = map[string]NewReaderFn{}\n"
        ),
        "model/value.go": "package model\ntype Value struct {}\n",
        "parsing/reader_test.go": "package parsing\nfunc TestAnything() {}\n",
    }, metadata={"go.mod": "module example.org/project\n"})
    assert {step.path for step in index.expand(["parsing/format.go"])} == {
        "parsing/format.go", "parsing/reader.go", "model/value.go",
    }
    assert {"NewReaderFn", "readers"} <= set(declarations(index, "parsing/reader.go"))
    assert "reader_test.go" not in index.render()


def test_nested_go_module_uses_nearest_config():
    index = build_source_index({
        "nested/a/a.go": 'package a\nimport "inner/b"\n',
        "nested/b/b.go": "package b\n", "b/b.go": "package b\n",
    }, metadata={"go.mod": "module outer\n", "nested/go.mod": "module inner\n"})
    assert {step.path for step in index.expand(["nested/a/a.go"])} == {"nested/a/a.go", "nested/b/b.go"}


def test_parse_errors_stay_visible_and_rust_import_analysis_is_not_claimed():
    index = build_source_index({"broken.py": "def invalid(:", "lib.rs": "pub fn api() {}\n"})
    assert {item.kind for item in index.diagnostics} == {"parse-error", "unsupported-import-analysis"}
    assert {file.path for file in index.files} == {"broken.py", "lib.rs"}
    assert "parse-error" in index.render()
    assert "api" in declarations(index, "lib.rs")


def test_index_and_expansion_are_stable_across_input_order():
    sources = {"b.py": "B = 2\n", "a.py": "import b\nA = 1\n"}
    first = build_source_index(sources)
    second = build_source_index(dict(reversed(list(sources.items()))))
    assert first == second
    assert first.render() == second.render()
    assert first.expand(["a.py", "b.py"]) == second.expand(["b.py", "a.py"])


def test_a_graph_fixed_point_does_not_guarantee_dynamic_implementation_coverage():
    index = build_source_index({
        "api.py": "def rolling(backend):\n    return getattr(backend, 'rolling')()\n",
        "plugin.py": "def rolling():\n    return 1\n",
    })
    assert "rolling" in declarations(index, "plugin.py")
    assert [step.path for step in index.expand(["api.py"])] == ["api.py"]
    assert "plugin.py" in index.render()


@pytest.mark.parametrize("path", ["/absolute.py", "../escape.py", "x\\a.py", "a//b.py"])
def test_index_rejects_non_repository_paths(path):
    with pytest.raises(ValueError, match="repository-relative"):
        build_source_index({path: "pass\n"})


def test_pinned_reader_ignores_dirty_and_untracked_files_and_never_follows_links(tmp_path):
    spec = importlib.util.spec_from_file_location(
        "inspect_source_index", Path(__file__).parents[1] / "tools/inspect_source_index.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    def git(*args, data=None):
        return subprocess.run(
            ["git", *args], cwd=tmp_path, input=data, check=True, capture_output=True
        ).stdout.decode().strip()

    git("init", "-q")
    git("config", "user.name", "Test")
    git("config", "user.email", "test@example.org")
    (tmp_path / "base.py").write_text("ORIGINAL = 1\n", encoding="utf-8")
    git("add", "base.py")
    link_oid = git("hash-object", "-w", "--stdin", data=b"../secret.py")
    git("update-index", "--add", "--cacheinfo", f"120000,{link_oid},link.py")
    git("commit", "-qm", "base")
    commit = git("rev-parse", "HEAD")
    (tmp_path / "base.py").write_text("CHANGED = 2\n", encoding="utf-8")
    (tmp_path / "untracked.py").write_text("SECRET = 3\n", encoding="utf-8")
    sources, metadata, provenance = module.read_pinned_sources(tmp_path, commit)
    assert sources == {"base.py": "ORIGINAL = 1\n"} and metadata == {}
    assert provenance["nonregular_entries_not_followed"] == [
        {"path": "link.py", "mode": "120000", "kind": "blob"}
    ]
    with pytest.raises(ValueError, match="full lowercase"):
        module.read_pinned_sources(tmp_path, "HEAD")
    (tmp_path / "coarse-context.json").write_text('{"files": ["base.py"]}', encoding="utf-8")
    issue = tmp_path / "issue.md"
    issue.write_text("Change the original setting.", encoding="utf-8")
    summary = module.inspect(SimpleNamespace(
        repository=tmp_path, base_commit=commit, recorded_run=tmp_path,
        issue=issue, output=tmp_path / "output",
        expect_declaration=["base.py::ORIGINAL", "untracked.py::SECRET"],
    ))
    assert summary["live_model_calls"] == 0
    assert summary["production_workflow_changed"] is False
    assert summary["expanded_files"] == ["base.py"]
    assert [check["in_repository_index"] for check in summary["checks"]] == [True, False]
    rendered = (tmp_path / "output/file-localization-with-index.txt").read_text(encoding="utf-8")
    assert "ORIGINAL" in rendered and "CHANGED" not in rendered and "SECRET" not in rendered
    assert json.loads((tmp_path / "output/summary.json").read_text()) == summary
