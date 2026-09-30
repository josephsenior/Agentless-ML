"""Capture Python voting keys from the pinned Agentless normalizer.

The reference's normalization function runs unchanged. Its two shell-based Git
helpers are replaced with temporary, argument-list Git calls so this capture is
safe on Windows and never invokes the reference's ``rm -rf`` cleanup.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from types import ModuleType

from agentless_ml.repair import build_unified_diff, normalize_patch


PINNED_REVISION = "b150f28465a77a81a7f4776384957a4271f5bd69"
FILE = "example.py"
CASES = (
    ("simple_fix", "answer = 0\n", "answer = 1\n"),
    ("spacing_variant", "answer = 0\n", "answer=1\n"),
    (
        "inline_comment",
        "def answer():\n    return 0\n",
        "def answer():\n    return 1  # corrected\n",
    ),
    (
        "same_fix_no_comment",
        "def answer():\n    return 0\n",
        "def answer():\n    return 1\n",
    ),
    (
        "docstring_change",
        'def answer():\n    """Old."""\n    return 0\n',
        'def answer():\n    """New."""\n    return 1\n',
    ),
    (
        "new_function",
        "VALUE = 1\n\ndef existing():\n    return VALUE\n",
        "VALUE = 1\n\ndef existing():\n    return VALUE\n\ndef added():\n    return 2\n",
    ),
    (
        "new_function_before",
        "def first():\n    return 1\n\ndef last():\n    return 3\n",
        "def added():\n    return 2\n\ndef first():\n    return 1\n\ndef last():\n    return 3\n",
    ),
    (
        "new_function_between",
        "def first():\n    return 1\n\ndef last():\n    return 3\n",
        "def first():\n    return 1\n\ndef added():\n    return 2\n\ndef last():\n    return 3\n",
    ),
    (
        "comment_only",
        "def answer():\n    return 1\n",
        "def answer():\n    # explanation\n    return 1\n",
    ),
)


def _run_git(directory: Path, *args: str, input_bytes: bytes | None = None) -> bytes:
    result = subprocess.run(
        ["git", "-c", "core.autocrlf=false", *args],
        cwd=directory,
        input=input_bytes,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(f"git {' '.join(args)}: {result.stderr.decode(errors='replace')}")
    return result.stdout


def _safe_apply(_playground: str, file_path: str, old: str, patch: str) -> str:
    if file_path != FILE:
        raise ValueError(f"unexpected reference path: {file_path}")
    with tempfile.TemporaryDirectory(prefix="agentless-vote-") as temporary:
        root = Path(temporary)
        target = root / FILE
        target.write_text(old, encoding="utf-8", newline="")
        _run_git(root, "apply", "--whitespace=nowarn", "-", input_bytes=patch.encode())
        return target.read_bytes().decode("utf-8")


def _safe_diff(_playground: str, file_path: str, old: str, new: str) -> str:
    if file_path != FILE:
        raise ValueError(f"unexpected reference path: {file_path}")
    with tempfile.TemporaryDirectory(prefix="agentless-vote-") as temporary:
        root = Path(temporary)
        target = root / FILE
        _run_git(root, "init", "-q")
        target.write_text(old, encoding="utf-8", newline="")
        _run_git(root, "add", "--", FILE)
        target.write_text(new, encoding="utf-8", newline="")
        return _run_git(root, "diff", "--", FILE).decode("utf-8")


def _load_reference(upstream: Path) -> tuple[ModuleType, str]:
    revision = _run_git(upstream, "rev-parse", "HEAD").decode().strip()
    if revision != PINNED_REVISION:
        raise ValueError(f"expected Agentless {PINNED_REVISION}, got {revision}")
    source_path = upstream / "agentless" / "util" / "postprocess_data.py"
    source_digest = hashlib.sha256(source_path.read_bytes()).hexdigest()
    sys.path.insert(0, str(upstream))
    spec = importlib.util.spec_from_file_location("published_voting", source_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {source_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.fake_git_apply = _safe_apply
    module.fake_git_repo = _safe_diff
    return module, source_digest


def capture(upstream: Path) -> dict[str, object]:
    reference, digest = _load_reference(upstream)
    cases = []
    for case_id, old, new in CASES:
        patch = build_unified_diff({FILE: old}, {FILE: new})
        upstream_key = reference.normalize_patch(case_id, patch, old)
        cases.append(
            {
                "id": case_id,
                "original": old,
                "updated": new,
                "upstream_key": normalize_patch(upstream_key),
            }
        )
    return {
        "upstream_revision": PINNED_REVISION,
        "upstream_source_sha256": digest,
        "capture_method": "published normalize_patch with temporary Git apply/diff helpers",
        "cases": cases,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(capture(args.upstream.resolve()), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
