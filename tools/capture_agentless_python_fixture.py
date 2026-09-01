"""Capture a golden fixture from an explicitly pinned Agentless checkout."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
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
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    revision = subprocess.run(
        ["git", "-C", args.upstream, "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    parser_module = _load(
        "published_repo_structure", args.upstream / "get_repo_structure/get_repo_structure.py"
    )
    skeleton_module = _load(
        "published_compress_file", args.upstream / "agentless/util/compress_file.py"
    )

    source = args.source.read_text(encoding="utf-8")
    classes, functions, text = parser_module.parse_python_file(str(args.source), source)
    fixture = {
        "upstream_revision": revision,
        "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
        "projection": {"classes": classes, "functions": functions, "text": text},
        "skeletons": {
            "default": skeleton_module.get_skeleton(source),
            "indented": skeleton_module.get_skeleton(source, keep_indent=True),
            "compressed": skeleton_module.get_skeleton(
                source,
                keep_indent=False,
                compress_assign=True,
                total_lines=5,
                prefix_lines=2,
                suffix_lines=2,
            ),
        },
    }
    args.output.write_text(json.dumps(fixture, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
