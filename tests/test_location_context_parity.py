import json
from pathlib import Path

import pytest

from agentless_ml.adapters.languages import PythonAdapter
from agentless_ml.localization import (
    construct_selected_context,
    extract_code_blocks,
    parse_locations_for_files,
    resolve_locations,
)


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "python"
REPOSITORY_FIXTURE = FIXTURE_DIR / "requests-2317.agentless-v1.5.0.json"
LOCATION_FIXTURE = FIXTURE_DIR / "requests-2317.locations.agentless-v1.5.0.json"


@pytest.fixture(scope="module")
def parity_data() -> tuple[dict[str, object], dict[str, object]]:
    repository = json.loads(REPOSITORY_FIXTURE.read_text(encoding="utf-8"))
    locations = json.loads(LOCATION_FIXTURE.read_text(encoding="utf-8"))
    return repository, locations


@pytest.mark.parametrize(
    "case",
    [
        "complete",
        "incomplete",
        "labelled_and_indented",
        "unknown_file",
        "reversed_files",
    ],
)
def test_model_output_parsing_matches_published_agentless(
    parity_data: tuple[dict[str, object], dict[str, object]], case: str
) -> None:
    _, golden = parity_data
    expected = golden["parsed_outputs"][case]
    blocks = extract_code_blocks(expected["raw"])
    assert blocks == expected["blocks"]
    assert parse_locations_for_files(blocks, golden["file_names"]) == expected[
        "locations"
    ]
    assert parse_locations_for_files(
        blocks, golden["file_names"], keep_old_order=True
    ) == expected["locations_keep_old_order"]


def test_keep_old_order_changes_only_dictionary_order(
    parity_data: tuple[dict[str, object], dict[str, object]],
) -> None:
    _, golden = parity_data
    case = golden["parsed_outputs"]["reversed_files"]
    assert list(case["locations"]) == ["requests/models.py", "requests/sessions.py"]
    assert list(case["locations_keep_old_order"]) == [
        "requests/sessions.py",
        "requests/models.py",
    ]


@pytest.mark.parametrize(
    "case",
    ["qualified_and_line", "class_scoped", "unique_unqualified", "mixed_invalid"],
)
def test_location_resolution_matches_published_agentless(
    parity_data: tuple[dict[str, object], dict[str, object]], case: str
) -> None:
    repository, golden = parity_data
    source = repository["selected_source"]
    path = repository["capture"]["selected_file"]
    file_node = PythonAdapter().parse_file(path, source)
    expected = golden["resolved_locations"][case]

    actual = resolve_locations(
        expected["locations"],
        file_node,
        source,
        context_window=10,
        separate_intervals=True,
    )
    assert [list(interval) for interval in actual.line_intervals] == expected[
        "line_intervals"
    ]
    assert [list(interval) for interval in actual.context_intervals] == expected[
        "context_intervals"
    ]


def test_selected_repair_context_matches_published_command_configuration(
    parity_data: tuple[dict[str, object], dict[str, object]],
) -> None:
    repository, golden = parity_data
    source = repository["selected_source"]
    path = repository["capture"]["selected_file"]
    file_node = PythonAdapter().parse_file(path, source)
    locations = golden["parsed_outputs"]["complete"]["locations"][path]

    context, intervals = construct_selected_context(
        {path: locations},
        {path: file_node},
        {path: source},
        context_window=10,
        separate_intervals=True,
        no_line_number=True,
    )
    assert context == golden["selected_context"]
    assert {key: [list(span) for span in value] for key, value in intervals.items()} == (
        golden["selected_intervals"]
    )


def test_global_assignment_and_line_number_locations() -> None:
    source = "CONFIG = {\n    'mode': 'safe',\n}\n\ndef run():\n    return CONFIG\n"
    file_node = PythonAdapter().parse_file("pkg/config.py", source)
    resolved = resolve_locations(
        "variable: CONFIG\nline: 6",
        file_node,
        source,
        context_window=0,
    )
    assert resolved.line_intervals == ((1, 3), (6, 6))
    assert resolved.context_intervals == ((1, 3), (6, 6))


def test_invalid_only_locations_produce_no_repair_context() -> None:
    source = "def valid():\n    return True\n"
    file_node = PythonAdapter().parse_file("valid.py", source)
    context, intervals = construct_selected_context(
        {"valid.py": ["function: Missing.nope"]},
        {"valid.py": file_node},
        {"valid.py": source},
    )
    assert context == ""
    assert intervals == {}
