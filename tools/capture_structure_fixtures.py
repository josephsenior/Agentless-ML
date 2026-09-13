"""Vendor the pinned structure corpus and capture its golden representations.

    python tools/capture_structure_fixtures.py fetch    # download pinned sources
    python tools/capture_structure_fixtures.py capture  # rewrite goldens

Capturing overwrites goldens with whatever the current implementation produces.
Run it deliberately: before a refactor to record the baseline, or after a
reviewed representation change. Never to make a failing comparison pass.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import urllib.request
from importlib.metadata import version
from pathlib import Path
from typing import Any

from agentless_ml.adapters.languages import get_language_adapter
from agentless_ml.structure.contract import observe

ROOT = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "structure"
PACKAGES = (
    "tree-sitter",
    "tree-sitter-go",
    "tree-sitter-rust",
    "tree-sitter-javascript",
    "tree-sitter-typescript",
)


def load_manifest() -> dict[str, Any]:
    return json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))


def source_file(entry: dict[str, Any]) -> Path | None:
    origin = entry.get("origin")
    if origin:
        return ROOT / "sources" / origin["repository"].replace("/", "__") / origin["path"]
    if "source" in entry:
        return (ROOT / entry["source"]).resolve()
    return None


def read_source(entry: dict[str, Any]) -> bytes:
    path = source_file(entry)
    return entry["inline"].encode("utf-8") if path is None else path.read_bytes()


def golden_file(entry_id: str) -> Path:
    return ROOT / "golden" / f"{entry_id}.json"


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Explicit LF: goldens must be byte-stable when re-captured on Windows.
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
    )


def fetch() -> None:
    manifest = load_manifest()
    notices = []
    for entry in manifest["files"]:
        origin = entry.get("origin")
        if not origin:
            continue
        target = source_file(entry)
        assert target is not None
        if not target.exists():
            url = (
                "https://raw.githubusercontent.com/"
                f"{origin['repository']}/{origin['commit']}/{origin['path']}"
            )
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(urllib.request.urlopen(url, timeout=60).read())
            print(f"fetched {url}")
        notices.append(
            f"| `{target.relative_to(ROOT / 'sources').as_posix()}` "
            f"| [{origin['repository']}](https://github.com/{origin['repository']}) "
            f"| `{origin['tag']}` (`{origin['commit']}`) | {origin['license']} |"
        )
    (ROOT / "sources" / "NOTICE.md").write_text(
        "# Vendored corpus sources\n\n"
        "Unmodified files copied from the repositories below at the listed commits, "
        "kept only as parser regression inputs. Each file remains under its "
        "project's license.\n\n"
        "| File | Repository | Pinned revision | License |\n|---|---|---|---|\n"
        + "\n".join(notices)
        + "\n",
        encoding="utf-8",
        newline="\n",
    )


def capture() -> None:
    manifest = load_manifest()
    for entry in manifest["files"]:
        data = read_source(entry)
        adapter = get_language_adapter(entry["language"])
        golden = {
            "id": entry["id"],
            "language": entry["language"],
            "path": entry["path"],
            "source_sha256": hashlib.sha256(data).hexdigest(),
            **observe(adapter, entry["path"], data.decode("utf-8")),
        }
        write_json(golden_file(entry["id"]), golden)
    policy = manifest["path_policy"]
    write_json(
        ROOT / "golden" / "_path_policy.json",
        {
            language: {
                path: [
                    get_language_adapter(language).is_source_path(path),
                    get_language_adapter(language).is_test_path(path),
                ]
                for path in policy["paths"]
            }
            for language in policy["languages"]
        },
    )
    write_json(
        ROOT / "golden" / "_environment.json",
        {package: version(package) for package in PACKAGES},
    )
    print(f"captured {len(manifest['files'])} files into {ROOT / 'golden'}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=("fetch", "capture"))
    {"fetch": fetch, "capture": capture}[parser.parse_args().command]()


if __name__ == "__main__":
    main()
