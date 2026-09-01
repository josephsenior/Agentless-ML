import hashlib
import json
from pathlib import Path

from agentless_ml.adapters.languages import PythonAdapter
from agentless_ml.adapters.languages.python import legacy_symbol_projection


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "python"
SOURCE_PATH = FIXTURE_DIR / "parity_sample.py"
GOLDEN_PATH = FIXTURE_DIR / "parity_sample.agentless-v1.5.0.json"
PINNED_AGENTLESS_REVISION = "b150f28465a77a81a7f4776384957a4271f5bd69"


def load_fixture() -> tuple[str, dict[str, object]]:
    source = SOURCE_PATH.read_text(encoding="utf-8")
    golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    return source, golden


def test_golden_fixture_is_bound_to_source_and_upstream_revision() -> None:
    source, golden = load_fixture()
    assert golden["upstream_revision"] == PINNED_AGENTLESS_REVISION
    assert golden["source_sha256"] == hashlib.sha256(source.encode()).hexdigest()


def test_legacy_symbol_projection_matches_published_agentless() -> None:
    source, golden = load_fixture()
    assert legacy_symbol_projection(source) == golden["projection"]


def test_default_skeleton_matches_published_agentless() -> None:
    source, golden = load_fixture()
    assert PythonAdapter().render_skeleton(source) == golden["skeletons"]["default"]


def test_indented_skeleton_matches_published_agentless() -> None:
    source, golden = load_fixture()
    actual = PythonAdapter().render_skeleton(source, keep_indent=True)
    assert actual == golden["skeletons"]["indented"]


def test_assignment_compression_matches_published_agentless() -> None:
    source, golden = load_fixture()
    actual = PythonAdapter().render_skeleton(
        source,
        compress_assign=True,
        total_lines=5,
        prefix_lines=2,
        suffix_lines=2,
    )
    assert actual == golden["skeletons"]["compressed"]


def test_normalized_structure_intentionally_repairs_legacy_omissions() -> None:
    source, _ = load_fixture()
    file_node = PythonAdapter().parse_file("package/sample.py", source)

    assert [symbol.name for symbol in file_node.symbols] == [
        "decorated",
        "fetch",
        "Worker",
        "run",
    ]
    worker = file_node.symbols[2]
    assert [child.name for child in worker.children] == [
        "__init__",
        "async_run",
        "run",
    ]
    assert worker.children[1].signature.startswith("async def async_run")
