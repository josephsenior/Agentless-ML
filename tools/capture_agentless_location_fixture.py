"""Capture published parsing, resolution, and repair-context outputs."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--upstream", type=Path, required=True)
    parser.add_argument("--repository-fixture", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    repository_fixture = json.loads(
        args.repository_fixture.read_text(encoding="utf-8")
    )
    source = repository_fixture["selected_source"]
    file_name = repository_fixture["capture"]["selected_file"]
    file_names = [file_name, "requests/models.py"]
    sys.path.insert(0, str(args.upstream))
    postprocess = _load(
        "published_postprocess", args.upstream / "agentless/util/postprocess_data.py"
    )
    preprocess = _load(
        "published_preprocess", args.upstream / "agentless/util/preprocess_data.py"
    )
    repair = _load("published_repair", args.upstream / "agentless/repair/repair.py")

    outputs = {
        "complete": (
            "Candidate locations:\n```\n"
            f"{file_name}\nfunction: Session.request\nline: 405\n"
            "requests/models.py\nclass: PreparedRequest\n```\n"
        ),
        "incomplete": f"Locations:\n```\n{file_name}\nfunction: Session.prepare_request",
        "labelled_and_indented": (
            "```python\n"
            f"{file_name}\n function: Session.request\nline: 405\n```"
        ),
        "unknown_file": "```\nmissing.py\nfunction: nope\n```",
        "reversed_files": (
            "```\nrequests/models.py\nclass: PreparedRequest\n"
            f"{file_name}\nfunction: Session.request\n```"
        ),
    }
    parsed_outputs = {}
    for name, raw_output in outputs.items():
        blocks = postprocess.extract_code_blocks(raw_output)
        parsed_outputs[name] = {
            "raw": raw_output,
            "blocks": blocks,
            "locations": postprocess.extract_locs_for_files(blocks, file_names),
            "locations_keep_old_order": postprocess.extract_locs_for_files(
                blocks, file_names, keep_old_order=True
            ),
        }

    location_groups = {
        "qualified_and_line": ["function: Session.request\nline: 405"],
        "class_scoped": ["class: Session\nfunction: prepare_request"],
        "unique_unqualified": ["function: prepare_request"],
        "mixed_invalid": ["function: Missing.nope\nline: not-a-number\nline: 405"],
    }
    resolved = {}
    for name, locations in location_groups.items():
        line_intervals, context_intervals = preprocess.transfer_arb_locs_to_locs(
            locations,
            None,
            file_name,
            context_window=10,
            loc_interval=True,
            fine_grain_only=False,
            file_content=source,
        )
        resolved[name] = {
            "locations": locations,
            "line_intervals": line_intervals,
            "context_intervals": context_intervals,
        }

    selected_locations = parsed_outputs["complete"]["locations"][file_name]
    selected_context, selected_intervals = repair.construct_topn_file_context(
        {file_name: selected_locations},
        [file_name],
        {file_name: source},
        None,
        context_window=10,
        loc_interval=True,
        fine_grain_loc_only=False,
        add_space=False,
        sticky_scroll=False,
        no_line_number=True,
    )

    fixture = {
        "capture": repository_fixture["capture"],
        "file_names": file_names,
        "parsed_outputs": parsed_outputs,
        "resolved_locations": resolved,
        "selected_context": selected_context,
        "selected_intervals": selected_intervals,
    }
    args.output.write_text(json.dumps(fixture, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
