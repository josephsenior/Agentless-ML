"""Hold every tree-sitter language to its captured repository representation.

Two levels, matching ADR 0003:

- the structural contract (symbols, kinds, names, spans, hierarchy, order, and
  which files are rejected) must never change silently;
- rendering (signatures and skeleton text) is also pinned, but a deliberate,
  reviewed rendering change is allowed to re-capture it.
"""

import hashlib
import json
from dataclasses import replace
from importlib.metadata import version
from pathlib import Path

import pytest

from agentless_ml.adapters.languages import get_language_adapter
from agentless_ml.schemas import FileNode, SymbolNode
from agentless_ml.structure.contract import (
    assert_structurally_equivalent,
    file_from_record,
    observe,
    structural_differences,
)

ROOT = Path(__file__).parent / "fixtures" / "structure"
MANIFEST = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
ENTRIES = {entry["id"]: entry for entry in MANIFEST["files"]}
CAPTURE_HINT = "re-capture only after review: python tools/capture_structure_fixtures.py capture"


def _source(entry):
    if "inline" in entry:
        return entry["inline"].encode("utf-8")
    if "origin" in entry:
        origin = entry["origin"]
        return (
            ROOT / "sources" / origin["repository"].replace("/", "__") / origin["path"]
        ).read_bytes()
    return (ROOT / entry["source"]).read_bytes()


def _golden(entry_id):
    return json.loads((ROOT / "golden" / f"{entry_id}.json").read_text(encoding="utf-8"))


def _observe(entry):
    data = _source(entry)
    return data, observe(
        get_language_adapter(entry["language"]), entry["path"], data.decode("utf-8")
    )


def test_grammar_versions_match_capture():
    captured = json.loads((ROOT / "golden" / "_environment.json").read_text("utf-8"))
    installed = {package: version(package) for package in captured}
    assert installed == captured, (
        "A grammar or tree-sitter upgrade changes node types and can silently change "
        "which symbols exist. Treat it as a representation change: review the "
        f"corpus diff, then {CAPTURE_HINT}"
    )


@pytest.mark.parametrize("entry_id", ENTRIES)
def test_structural_contract(entry_id):
    entry = ENTRIES[entry_id]
    golden = _golden(entry_id)
    data, actual = _observe(entry)
    assert hashlib.sha256(data).hexdigest() == golden["source_sha256"], (
        f"corpus source for {entry_id} changed; {CAPTURE_HINT}"
    )
    expected = golden["parse"]
    if "error" in expected or "error" in actual["parse"]:
        # Whether a file is rejected decides if it can enter the repository
        # structure; the wording of the rejection is only rendering.
        rejected = lambda outcome: outcome.get("error", {}).get("type")  # noqa: E731
        assert rejected(actual["parse"]) == rejected(expected)
        assert isinstance(actual["skeleton"], dict) == isinstance(golden["skeleton"], dict)
        return
    assert_structurally_equivalent(
        file_from_record(expected), file_from_record(actual["parse"])
    )


@pytest.mark.parametrize("entry_id", ENTRIES)
def test_rendering_unchanged(entry_id):
    golden = _golden(entry_id)
    _, actual = _observe(ENTRIES[entry_id])
    assert actual["parse"] == golden["parse"], CAPTURE_HINT
    assert actual["skeleton"] == golden["skeleton"], CAPTURE_HINT


def test_path_policy_unchanged():
    captured = json.loads((ROOT / "golden" / "_path_policy.json").read_text("utf-8"))
    for language, expected in captured.items():
        adapter = get_language_adapter(language)
        actual = {
            path: [adapter.is_source_path(path), adapter.is_test_path(path)]
            for path in expected
        }
        # Test classification filters the localization project tree, so a change
        # here changes the prompt, not just a label.
        assert actual == expected, f"{language} path policy changed"


def _node(*symbols):
    return FileNode("a.go", "go", 20, symbols)


def _symbol(name, kind="function", start=1, end=2, children=(), signature="sig"):
    return SymbolNode(kind, name, name, signature, start, end, children)


def test_contract_ignores_rendering_only_fields():
    expected = _node(_symbol("A"), _symbol("B", start=3, end=4))
    actual = _node(
        _symbol("A", signature="func A()"),
        _symbol("B", start=3, end=4, signature="export B"),
    )
    assert structural_differences(expected, actual) == []


@pytest.mark.parametrize(
    "mutate,reason",
    [
        (lambda s: (replace(s[0], kind="method"), s[1]), "kind"),
        (lambda s: (replace(s[0], start_line=2), s[1]), "start_line"),
        (lambda s: (replace(s[0], end_line=5), s[1]), "end_line"),
        (lambda s: (replace(s[0], qualified_name="Z"), s[1]), "qualified_name"),
        (lambda s: (s[1], s[0]), "qualified_name"),
        (lambda s: (s[0],), "missing"),
        (lambda s: (*s, _symbol("C", start=9, end=9)), "unexpected"),
    ],
)
def test_contract_detects_workflow_changes(mutate, reason):
    symbols = (_symbol("A", end=2), _symbol("B", start=3, end=4))
    differences = structural_differences(_node(*symbols), _node(*mutate(symbols)))
    assert differences and any(reason in d for d in differences)
    with pytest.raises(AssertionError, match="workflow level"):
        assert_structurally_equivalent(_node(*symbols), _node(*mutate(symbols)))


def test_contract_detects_hierarchy_changes():
    child = _symbol("T.m", kind="method", start=2, end=2)
    nested = _node(_symbol("T", kind="class", end=3, children=(child,)))
    flat = _node(_symbol("T", kind="class", end=3), child)
    assert any("children" in d for d in structural_differences(nested, flat))
