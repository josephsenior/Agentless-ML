"""Offline, resumable token census of all pinned DeepSWE source contexts.

No model calls or scoring material. Measures explicit inputs, not future model
output or experiment usage. Inspection choices are unknown, so report size bounds.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from collections import Counter
from pathlib import Path

import tiktoken

from agentless_ml.adapters.languages import source_adapter
from agentless_ml.localization.context import render_file_localization_prompt, render_project_tree
from agentless_ml.localization.source_index import build_source_index, walk_symbols
from agentless_ml.workspace.local_git import _require_git
from inspect_source_index import read_pinned_sources, write_json


def render_import_map(index) -> str:
    """One adjacency row per file; preserve every known target, no hop expansion."""
    targets = {file.path: set() for file in index.files}
    uncertain = Counter()
    for link in index.links:
        targets[link.path].update(link.targets)
        if link.status in {"unresolved", "dynamic", "ambiguous"}:
            uncertain[link.path] += 1
    lines = ["Static file-import map; not a resolved call graph. Uncertain links remain unresolved."]
    for path in sorted(targets):
        lines.append(f"{path} -> {', '.join(sorted(targets[path])) or '(no known local targets)'}"
                     f" [uncertain links: {uncertain[path]}]")
    return "\n".join(lines) + "\n"


def survey_task(repository: Path, commit: str, issue: str, *, graph_budget: int = 8000) -> dict:
    sources, metadata, provenance = read_pinned_sources(
        repository, commit, source_policy_only=True, allow_unreadable=True,
    )
    index = build_source_index(sources, metadata=metadata)
    encoding = tiktoken.get_encoding("o200k_base")

    def tokens(text):
        return len(encoding.encode(text, disallowed_special=()))

    paths = [file.path for file in index.files]
    tree = render_project_tree(
        [repository.name + "/" + path for path in paths],
        file_adapters={path: source_adapter(path) for path in paths},
    )
    names = index.render()
    graph = render_import_map(index)
    graph_lines = graph.splitlines(keepends=True)
    # A budget scenario, not a proposed relevance ranking: whole rows only,
    # lexical order, explicit omitted-row count, with the marker charged too.
    bounded_lines = [graph_lines[0]]
    used = tokens(graph_lines[0])
    for line in graph_lines[1:]:
        marker = f"[OMITTED FILE ROWS: {len(paths) - len(bounded_lines)}]\n"
        charge = tokens(line)
        if used + charge + tokens(marker) > graph_budget:
            break
        bounded_lines.append(line)
        used += charge
    omitted_rows = len(paths) - (len(bounded_lines) - 1)
    bounded_graph = "".join(bounded_lines) + f"[OMITTED FILE ROWS: {omitted_rows}]\n"
    while tokens(bounded_graph) > graph_budget and len(bounded_lines) > 1:
        bounded_lines.pop()
        omitted_rows += 1
        bounded_graph = "".join(bounded_lines) + f"[OMITTED FILE ROWS: {omitted_rows}]\n"

    def prompt(extra):
        return render_file_localization_prompt(issue, tree + extra, extension=None)

    # Each selectable file can expose its complete skeleton in one fixed
    # inspection phase. Bound the source payload without guessing model choices.
    skeletons = []
    skeleton_errors = []
    for path in paths:
        try:
            skeleton = source_adapter(path).render_skeleton(sources[path], path=path)
            block = f"### {path}\n{skeleton}\n"
            skeletons.append({"path": path, "tokens": tokens(block)})
        except (ValueError, SyntaxError) as exc:
            skeleton_errors.append({"path": path, "error": str(exc)[:400]})
    largest = sorted(skeletons, key=lambda row: (-row["tokens"], row["path"]))[:10]
    smallest = sorted(skeletons, key=lambda row: (row["tokens"], row["path"]))[:10]
    return {
        "task": repository.name, "status": "measured", **provenance,
        "input_coverage": "partial-unreadable" if provenance["unreadable_source_files"] else "all-policy-source-blobs",
        "encoding": "o200k_base", "live_model_calls": 0,
        "files": len(paths),
        "declarations": sum(1 for file in index.files for _ in walk_symbols(file.symbols)),
        "index_diagnostics": [vars_without_slots(item) for item in index.diagnostics],
        "import_status_counts": dict(sorted(Counter(link.status for link in index.links).items())),
        "tree_only_prompt_tokens": tokens(prompt("")),
        "index_tokens": tokens(names), "complete_import_map_tokens": tokens(graph),
        "index_prompt_tokens": tokens(prompt("\n" + names)),
        "index_plus_complete_map_prompt_tokens": tokens(prompt("\n" + names + "\n" + graph)),
        "bounded_map_budget": graph_budget,
        "bounded_map_tokens": tokens(bounded_graph), "bounded_map_omitted_file_rows": omitted_rows,
        "index_plus_bounded_map_prompt_tokens": tokens(prompt("\n" + names + "\n" + bounded_graph)),
        "inspection_skeleton_tokens_sum_smallest_10": sum(row["tokens"] for row in smallest),
        "inspection_skeleton_tokens_sum_largest_10": sum(row["tokens"] for row in largest),
        "inspection_largest_files": largest,
        "inspection_bounds_cover_all_indexed_files": not skeleton_errors,
        "inspection_skeleton_errors": skeleton_errors,
        "source_index_sha256": hashlib.sha256(names.encode()).hexdigest(),
        "import_map_sha256": hashlib.sha256(graph.encode()).hexdigest(),
    }


def vars_without_slots(item):
    return {"path": item.path, "kind": item.kind, "detail": item.detail[:400]}


def summarize(rows):
    measured = [row for row in rows if row["status"] == "measured"]
    result = {"measured": len(measured), "blocked": len(rows) - len(measured)}
    for key in ("tree_only_prompt_tokens", "index_prompt_tokens",
                "index_plus_complete_map_prompt_tokens", "index_plus_bounded_map_prompt_tokens",
                "inspection_skeleton_tokens_sum_largest_10"):
        values = sorted(row[key] for row in measured)
        if values:
            result[key] = {
                "min": values[0], "median": statistics.median(values),
                "p90_nearest_rank": values[math.ceil(.9 * len(values)) - 1], "max": values[-1],
                "over_threshold": {str(cap): sum(value > cap for value in values)
                                   for cap in (32000, 64000, 128000, 200000, 272000)},
            }
    result["tasks_with_unreadable_blobs"] = [row["task"] for row in measured if row.get("unreadable_source_files")]
    result["tasks_with_parse_errors"] = [row["task"] for row in measured
                                         if any(item["kind"] == "parse-error" for item in row["index_diagnostics"])]
    result["tasks_with_skeleton_errors"] = [row["task"] for row in measured if row["inspection_skeleton_errors"]]
    return result


def render_report(rows):
    lines = [
        "# Offline DeepSWE source-context token census",
        "", "Token estimates use o200k_base. No model calls; production workflow unchanged.",
        "", "Index/map columns are whole reconstructed file-localization prompts, including issue and tree.",
        "The 8k map is only an illustrative lexical whole-row cap; omitted edges may be needed.",
        "Inspection is the sum of the ten largest standalone source skeletons (or all files if fewer).",
        "It is a payload size scenario, not an actual selection or a complete second request.",
        "", "| Task | Index prompt | + full import map | + 8k map | Largest-10 skeleton payload | Caveats |",
        "| --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in rows:
        if row["status"] != "measured":
            lines.append(f"| {row['task']} | — | — | — | — | BLOCKED: {row['error'].replace('|', '/')} |")
            continue
        caveats = []
        if row.get("unreadable_source_files"):
            caveats.append(f"{len(row['unreadable_source_files'])} unreadable blobs; partial count")
        counts = Counter(item["kind"] for item in row["index_diagnostics"])
        if counts["parse-error"]:
            caveats.append(f"{counts['parse-error']} parse errors")
        if counts["unsupported-import-analysis"]:
            caveats.append("Rust import map unsupported")
        if row["inspection_skeleton_errors"]:
            caveats.append("skeleton payload partial")
        lines.append(f"| {row['task']} | {row['index_prompt_tokens']:,} | "
                     f"{row['index_plus_complete_map_prompt_tokens']:,} | "
                     f"{row['index_plus_bounded_map_prompt_tokens']:,} | "
                     f"{row['inspection_skeleton_tokens_sum_largest_10']:,} | {'; '.join(caveats)} |")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repositories", type=Path, default=Path("../benchmarks/deepswe/repos"))
    parser.add_argument("--corpus", type=Path, default=Path("../benchmarks/deepswe/corpus"))
    parser.add_argument("--pin", type=Path, default=Path("experiments/deepswe/corpus_pin.json"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tasks", nargs="*")
    parser.add_argument("--retry-blocked", action="store_true")
    args = parser.parse_args()
    pin = json.loads(args.pin.read_text(encoding="utf-8"))
    all_tasks = sorted(pin["container_digests"])
    tasks = args.tasks or all_tasks
    if set(tasks) - set(all_tasks):
        raise ValueError("tasks must belong to the pinned corpus")
    args.output.mkdir(parents=True, exist_ok=True)
    for number, task in enumerate(tasks, 1):
        destination = args.output / (task + ".json")
        if destination.exists() and not (
            args.retry_blocked and json.loads(destination.read_text(encoding="utf-8"))["status"] == "blocked"
        ):
            print(f"{number}/{len(tasks)} retained {task}", flush=True)
            continue
        try:
            sealed = json.loads((args.repositories / (task + ".sealed.json")).read_text(encoding="utf-8"))
            # Issue text comes from the pinned public corpus, not its working tree.
            issue = _require_git(args.corpus, "show", pin["revision"] + ":tasks/" + task + "/instruction.md",
                                 timeout=30).decode("utf-8")
            result = survey_task(args.repositories / task, sealed["base_commit"], issue)
            if result["base_tree"] != sealed["base_tree"]:
                raise ValueError("sealed base tree mismatch")
        except Exception as exc:
            result = {"task": task, "status": "blocked", "error": f"{type(exc).__name__}: {exc}", "live_model_calls": 0}
        write_json(destination, result)
        print(f"{number}/{len(tasks)} {task}: {result['status']}"
              f" index_prompt={result.get('index_prompt_tokens', '?')}", flush=True)
    rows = [json.loads((args.output / (task + ".json")).read_text(encoding="utf-8"))
            for task in all_tasks if (args.output / (task + ".json")).exists()]
    write_json(args.output / "survey.json", {
        "kind": "offline-source-context-census", "corpus_revision": pin["revision"],
        "expected_tasks": len(all_tasks), "completed_tasks": len(rows),
        "status_counts": dict(Counter(row["status"] for row in rows)),
        "live_model_calls": 0, "tasks": rows,
        "limits": [
            "Input token estimates, not actual provider usage or whole-workflow cost.",
            "Inspection choices unknown: standalone skeleton sums are payload size scenarios, not complete request costs.",
            "Eight-thousand-token import map is an illustrative whole-row lexical cap, not relevance selection.",
            "The declaration index is not capped in these scenarios; capped maps can omit needed links.",
            "Parser and static import limitations from the prototype still apply.",
        ],
    })
    write_json(args.output / "statistics.json", summarize(rows))
    (args.output / "report.md").write_text(render_report(rows), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
