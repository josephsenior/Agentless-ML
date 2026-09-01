"""Capture repository-tree and localization-context golden outputs."""

from __future__ import annotations

import argparse
import hashlib
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
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    metadata = json.loads(args.metadata.read_text(encoding="utf-8"))
    parser_module = _load(
        "published_repo_structure", args.upstream / "get_repo_structure/get_repo_structure.py"
    )
    sys.path.insert(0, str(args.upstream))
    preprocess = _load(
        "published_preprocess", args.upstream / "agentless/util/preprocess_data.py"
    )
    localization = _load("published_fl", args.upstream / "agentless/fl/FL.py")
    skeletons = _load(
        "published_compress_file", args.upstream / "agentless/util/compress_file.py"
    )

    structure = parser_module.create_structure(str(args.repository))
    actual_root = next(iter(structure))
    root_files = structure.pop(actual_root)
    package_files = structure.pop("requests")
    root_files.update(package_files)
    structure = {"requests": root_files, **structure}
    preprocess.filter_none_python(structure)
    preprocess.filter_out_test_files(structure)
    project_tree = preprocess.show_project_structure(structure)
    files, _, _ = preprocess.get_full_file_paths_and_classes_and_functions(structure)
    file_order = [path for path, _ in files]

    file_map = dict(files)
    session_paths = [path for path in file_map if path.endswith("/sessions.py")]
    if len(session_paths) != 1:
        raise RuntimeError(
            f"expected one sessions.py, found {session_paths}; files={file_order[:30]}"
        )
    selected_path = session_paths[0]
    selected_source = "\n".join(file_map[selected_path])
    selected_skeleton = skeletons.get_skeleton(selected_source)
    file_prompt = localization.LLMFL.obtain_relevant_files_prompt.format(
        problem_statement=metadata["problem_statement"],
        structure=project_tree.strip(),
    ).strip()
    block = localization.LLMFL.file_content_in_block_template.format(
        file_name=selected_path,
        file_content=selected_skeleton,
    )
    symbol_prompt = (
        localization.LLMFL.obtain_relevant_functions_and_vars_from_compressed_files_prompt_more.format(
            problem_statement=metadata["problem_statement"],
            file_contents=block,
        )
    )

    fixture = {
        "capture": {
            **metadata,
            "published_agentless_revision": "b150f28465a77a81a7f4776384957a4271f5bd69",
            "selected_file": selected_path,
            "selected_file_sha256": hashlib.sha256(selected_source.encode()).hexdigest(),
        },
        "ordered_python_files": file_order,
        "project_tree": project_tree,
        "selected_source": selected_source,
        "selected_skeleton": selected_skeleton,
        "file_localization_prompt": file_prompt,
        "symbol_localization_prompt": symbol_prompt,
    }
    args.output.write_text(json.dumps(fixture, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
