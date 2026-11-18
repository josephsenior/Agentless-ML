"""Measure the offline declaration/import prototype on one pinned public base.

Reads Git blobs, public issue text and a saved file selection. Does not invoke a
model, run repository code, read scoring tests or change the fixed controller.
Large rendered inputs stay in the caller's output directory; a compact summary
can be copied into experiments for review.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from dataclasses import asdict
from pathlib import Path, PurePosixPath

import tiktoken

from agentless_ml.adapters.languages import get_language_adapter, source_adapter
from agentless_ml.localization.context import (
    render_file_localization_prompt,
    render_project_tree,
)
from agentless_ml.localization.source_index import (
    build_source_index,
    walk_symbols,
)
from agentless_ml.workspace.local_git import _git, _require_git


def read_pinned_sources(repository: Path, commit: str):
    """Read regular source blobs at a full commit ID, ignoring working-tree edits.

    Gitlinks and symlinks are reported, never followed. Reading by blob ID also
    avoids checkout filters, line-ending conversion and per-file process costs.
    """
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("base commit must be a full lowercase SHA-1")
    tree = _require_git(repository, "rev-parse", "--verify", commit + "^{tree}", timeout=30).decode().strip()
    listing = _require_git(repository, "ls-tree", "-rz", "--full-tree", commit, timeout=30)
    extensions = {extension for language in ("python", "go", "javascript", "typescript", "rust")
                  for extension in get_language_adapter(language).extensions}
    blobs = []
    omitted = []
    tracked = 0
    for record in listing.split(b"\0"):
        if not record:
            continue
        tracked += 1
        info, raw_path = record.split(b"\t", 1)
        mode, kind, oid = info.decode("ascii").split()
        path = raw_path.decode("utf-8")
        if mode not in {"100644", "100755"} or kind != "blob":
            omitted.append({"path": path, "mode": mode, "kind": kind})
        elif PurePosixPath(path).suffix in extensions or PurePosixPath(path).name == "go.mod":
            blobs.append((path, oid))
    result = _git(repository, "cat-file", "--batch", timeout=60,
                  data="".join(oid + "\n" for _, oid in blobs).encode("ascii"))
    if result.returncode:
        raise ValueError(result.stderr.decode("utf-8", errors="replace"))
    offset = 0
    sources, metadata, blob_ids = {}, {}, {}
    for path, oid in blobs:
        end = result.stdout.index(b"\n", offset)
        actual_oid, kind, size = result.stdout[offset:end].decode("ascii").split()
        if actual_oid != oid or kind != "blob":
            raise ValueError("Git blob reply does not match request")
        offset = end + 1
        raw = result.stdout[offset:offset + int(size)]
        offset += int(size)
        if result.stdout[offset:offset + 1] != b"\n":
            raise ValueError("invalid Git blob framing")
        offset += 1
        # Invalid source encoding is a visible blocker, never silently skipped.
        source = raw.decode("utf-8-sig")
        destination = metadata if PurePosixPath(path).name == "go.mod" else sources
        destination[path] = source
        blob_ids[path] = oid
    return sources, metadata, {
        "base_commit": commit, "base_tree": tree, "tracked_entries": tracked,
        "read_blobs": len(blobs), "nonregular_entries_not_followed": omitted,
        "blob_manifest_sha256": hashlib.sha256(json.dumps(blob_ids, sort_keys=True).encode()).hexdigest(),
    }


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def inspect(args) -> dict:
    sources, metadata, provenance = read_pinned_sources(args.repository, args.base_commit)
    index = build_source_index(sources, metadata=metadata)
    coarse_bytes = (args.recorded_run / "coarse-context.json").read_bytes()
    coarse = json.loads(coarse_bytes)
    steps = index.expand(coarse["files"])
    expanded = [step.path for step in steps]
    rendered = index.render()
    expanded_index = index.render(expanded)
    accepted = {file.path for file in index.files}
    tree = render_project_tree(
        [f"{args.repository.name}/{path}" for path in sorted(accepted)],
        file_adapters={path: source_adapter(path) for path in accepted},
    )
    issue = args.issue.read_text(encoding="utf-8")
    baseline = render_file_localization_prompt(issue, tree, extension=None)
    proposed = render_file_localization_prompt(issue, tree + "\n" + rendered, extension=None)
    encoding = tiktoken.get_encoding("o200k_base")

    def measure(text: str) -> dict:
        return {"characters": len(text), "tokens": len(encoding.encode(text, disallowed_special=())),
                "sha256": hashlib.sha256(text.encode()).hexdigest()}

    checks = []
    for expected in args.expect_declaration:
        path, separator, name = expected.partition("::")
        if not separator:
            raise ValueError("expected declarations use path::qualified_name")
        matches = [symbol for file in index.files if file.path == path
                   for symbol in walk_symbols(file.symbols) if symbol.qualified_name == name]
        checks.append({
            "path": path, "qualified_name": name,
            "spans": [[symbol.start_line, symbol.end_line] for symbol in matches],
            "in_original_files": path in coarse["files"],
            "in_repository_index": bool(matches),
            "in_import_expansion": bool(matches) and path in expanded,
        })
    unresolved = [
        asdict(link) for link in index.links
        if link.path in expanded and link.status in {"unresolved", "dynamic", "ambiguous"}
    ]
    summary = {
        "kind": "offline-source-index-prototype", "live_model_calls": 0,
        "production_workflow_changed": False, "task": args.repository.name,
        **provenance,
        "recorded_run_id": args.recorded_run.name,
        "recorded_selection_sha256": hashlib.sha256(coarse_bytes).hexdigest(),
        "public_issue_sha256": hashlib.sha256(issue.encode()).hexdigest(),
        "file_prompt_is_reconstructed_with_current_defaults": True,
        "token_encoding": "o200k_base", "token_counts_are_estimates_for_model_input": True,
        "index_policy": "existing source/test filters; adapter declarations plus Python module assignments",
        "dependency_policy": (
            "outgoing syntactic file imports; Python/src, relative JS/TS, "
            "Go modules and same-package files; no hop/file cutoff"
        ),
        "files_indexed": len(index.files),
        "declarations_indexed": sum(1 for file in index.files for _ in walk_symbols(file.symbols)),
        "diagnostic_counts": dict(sorted(Counter(item.kind for item in index.diagnostics).items())),
        "import_status_counts": dict(sorted(Counter(link.status for link in index.links).items())),
        "original_files": coarse["files"], "expanded_files": expanded,
        "tree_only_file_prompt": measure(baseline),
        "file_localization_with_index": measure(proposed),
        "repository_declaration_index": measure(rendered),
        "expanded_declaration_index": measure(expanded_index),
        "selected_files_full_source": measure("\n".join(f"### {path}\n{sources[path]}" for path in sorted(coarse["files"]))),
        "expanded_full_source": measure("\n".join(f"### {path}\n{sources[path]}" for path in expanded)),
        "unresolved_dynamic_or_ambiguous_links_in_expansion": len(unresolved),
        "checks": checks,
        "limits": [
            "Names recognized by parsers, not every local binding or computed declaration.",
            "A file import graph, not a resolved call/type graph; dynamic dispatch remains incomplete.",
            "Unresolved imports can be external packages, aliases, excluded files, or missing relationships.",
            "Known missing declarations are audit checks only, never expansion seeds.",
            "Source visibility is measured; model localization and repair success are not tested.",
            "Full-source measurement does not change editable regions or production repair prompts.",
        ],
    }
    args.output.mkdir(parents=True, exist_ok=True)
    for filename, value in (("source-index.txt", rendered), ("expanded-index.txt", expanded_index),
                            ("file-localization-with-index.txt", proposed)):
        (args.output / filename).write_text(value, encoding="utf-8", newline="\n")
    write_json(args.output / "graph.json", {
        "links": [asdict(link) for link in index.links],
        "diagnostics": [asdict(item) for item in index.diagnostics],
    })
    write_json(args.output / "expansion.json", {
        "steps": [asdict(step) for step in steps], "unresolved_links": unresolved,
    })
    write_json(args.output / "summary.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--base-commit", required=True)
    parser.add_argument("--recorded-run", type=Path, required=True)
    parser.add_argument("--issue", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expect-declaration", action="append", default=[])
    args = parser.parse_args()
    summary = inspect(args)
    print(json.dumps({key: summary[key] for key in (
        "task", "files_indexed", "declarations_indexed", "diagnostic_counts",
        "repository_declaration_index", "file_localization_with_index", "checks",
    )}, indent=2))


if __name__ == "__main__":
    main()
