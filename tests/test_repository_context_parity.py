import hashlib
import json
from pathlib import Path

from agentless_ml.adapters.languages import PythonAdapter
from agentless_ml.localization import (
    render_file_localization_prompt,
    render_legacy_project_tree,
    render_symbol_localization_prompt,
)


FIXTURE_PATH = (
    Path(__file__).parent
    / "fixtures"
    / "python"
    / "requests-2317.agentless-v1.5.0.json"
)


def load_fixture() -> dict[str, object]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_real_repository_fixture_has_pinned_provenance() -> None:
    fixture = load_fixture()
    capture = fixture["capture"]
    assert capture["published_agentless_revision"] == (
        "b150f28465a77a81a7f4776384957a4271f5bd69"
    )
    assert capture["dataset_revision"] == (
        "6ec7bb89b9342f664a54a6e0a6ea6501d3437cc2"
    )
    assert capture["base_commit"] == "091991be0da19de9108dbe5e3752917fea3d7fdc"
    assert hashlib.sha256(fixture["selected_source"].encode()).hexdigest() == capture[
        "selected_file_sha256"
    ]


def test_filtered_project_tree_matches_published_agentless() -> None:
    fixture = load_fixture()
    actual = render_legacy_project_tree(fixture["ordered_python_files"])
    assert actual == fixture["project_tree"]


def test_real_file_skeleton_matches_published_agentless() -> None:
    fixture = load_fixture()
    actual = PythonAdapter().render_skeleton(fixture["selected_source"])
    assert actual == fixture["selected_skeleton"]


def test_file_localization_prompt_matches_published_agentless() -> None:
    fixture = load_fixture()
    capture = fixture["capture"]
    actual = render_file_localization_prompt(
        capture["problem_statement"], fixture["project_tree"]
    )
    assert actual == fixture["file_localization_prompt"]


def test_symbol_localization_prompt_matches_published_agentless() -> None:
    fixture = load_fixture()
    capture = fixture["capture"]
    actual = render_symbol_localization_prompt(
        capture["problem_statement"],
        {capture["selected_file"]: fixture["selected_source"]},
    )
    assert actual == fixture["symbol_localization_prompt"]


def test_tree_renderer_excludes_tests_and_non_python_files() -> None:
    paths = [
        "repo/setup.py",
        "src/module.py",
        "tests/test_module.py",
        "src/test_helper.py",
        "docs/readme.md",
    ]
    assert render_legacy_project_tree(paths) == (
        "repo/\n    setup.py\nsrc/\n    module.py\n"
    )
