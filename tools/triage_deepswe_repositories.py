"""Inspect old repository blockers without cloning, patching, or running tests.

Preflight is not benchmark readiness. The report deliberately leaves the
append-only baseline survey unchanged. Only pinned Git trees are inspected;
symlink targets are read as blobs, never followed on the host filesystem.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import posixpath
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

from agentless_ml.workspace import LocalGitWorkspaceProvider, WorkspaceError, verify_sealed_repository

BLOCKED_STATUSES = {"unsupported_repository", "repository_failed"}


def latest_records(path: Path) -> dict[str, dict]:
    rows = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            record = json.loads(line)
            rows[record["task_id"]] = record
    return rows


def git_read(repository: Path, *args: str, timeout: float = 300) -> bytes:
    env = {key: value for key, value in os.environ.items()
           if not key.upper().startswith("GIT_")}
    env.update(GIT_OPTIONAL_LOCKS="0", GIT_CONFIG_NOSYSTEM="1")
    result = subprocess.run(("git", *args), cwd=repository, env=env,
                            capture_output=True, timeout=timeout)
    if result.returncode:
        raise WorkspaceError(result.stderr.decode("utf-8", errors="replace").strip())
    return result.stdout


def tree_entries(repository: Path, commit: str) -> list[dict]:
    result = []
    for record in git_read(repository, "ls-tree", "-rz", "--full-tree", commit).split(b"\0"):
        if record:
            metadata, raw_path = record.split(b"\t", 1)
            mode, kind, oid = metadata.decode("ascii").split()
            result.append({"path": raw_path.decode("utf-8"), "mode": mode,
                           "kind": kind, "oid": oid})
    return result


def direct_target(path: str, target: str, entries: dict[str, dict]) -> dict:
    """Classify only this link's direct target, not a chain's eventual safety."""
    if not target or "\0" in target or "\\" in target:
        return {"direct_target_kind": "nonportable_target"}
    if target.startswith("/") or (len(target) > 1 and target[1] == ":"):
        return {"direct_target_kind": "absolute_target"}
    resolved = posixpath.normpath(posixpath.join(posixpath.dirname(path), target))
    if resolved == ".." or resolved.startswith("../"):
        kind = "outside_checkout"
    elif resolved in entries:
        kind = {"120000": "symlink", "160000": "submodule"}.get(
            entries[resolved]["mode"], "file")
    elif resolved == "." or any(name.startswith(resolved + "/") for name in entries):
        kind = "directory"
    else:
        kind = "missing_target"
    return {"normalized_direct_target": resolved, "direct_target_kind": kind}


def inspect_record(record: dict, repositories: Path, *, timeout: float = 300) -> dict:
    task_id = record["task_id"]
    # IDs from the survey are untrusted path components.
    if not task_id or task_id in {".", ".."} or any(c in task_id for c in "/\\:"):
        raise ValueError("task_id must be a single portable path component")
    result = {"task_id": task_id, "base_commit": record["base_commit"],
              "previous_status": record["status"],
              "previous_message": record.get("message", "")}
    repository = repositories / task_id
    if repository.is_symlink():
        return {**result, "preflight": "repository_path_is_symlink"}
    if not repository.is_dir():
        return {**result, "preflight": "missing_repository"}
    try:
        verify_sealed_repository(repository, record["base_commit"], timeout_seconds=timeout)
    except (WorkspaceError, OSError, subprocess.TimeoutExpired) as error:
        return {**result, "preflight": "seal_failed", "message": str(error)[:1000]}
    try:
        entries = tree_entries(repository, record["base_commit"])
        indexed = {entry["path"]: entry for entry in entries}
        special = []
        for entry in entries:
            if entry["mode"] not in {"120000", "160000"}:
                continue
            info = dict(entry)
            if entry["mode"] == "120000":
                try:
                    target = git_read(repository, "cat-file", "blob", entry["oid"]).decode("utf-8")
                except UnicodeDecodeError:
                    info["direct_target_kind"] = "non_utf8_target"
                else:
                    info.update(target=target, **direct_target(entry["path"], target, indexed))
                host = repository / entry["path"]
                info["host_representation"] = (
                    "symlink" if host.is_symlink() else "regular_file" if host.is_file() else "absent")
            special.append(info)
        result.update(special_entries=special,
                      entry_modes=dict(Counter(entry["mode"] for entry in entries)))
        # Constructing the provider validates the tree; it creates no checkout.
        provider = LocalGitWorkspaceProvider(
            repository, record["base_commit"],
            Path(tempfile.gettempdir()) / "agentless-ml-triage-unused", timeout_seconds=timeout)
        result.update(preflight="accepted_by_current_workspace",
                      workspace_tracked_paths=len(provider.paths), excluded_symlink_paths=len(provider.symlink_paths))
    except (WorkspaceError, OSError, UnicodeDecodeError, subprocess.TimeoutExpired) as error:
        result.update(preflight="workspace_refused", message=str(error)[:1000])
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--survey", type=Path, required=True)
    parser.add_argument("--repositories", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=300)
    parser.add_argument("--output", type=Path, help="write generated audit evidence instead of printing its full JSON")
    args = parser.parse_args()
    if not math.isfinite(args.timeout_seconds) or args.timeout_seconds <= 0:
        parser.error("--timeout-seconds must be finite and positive")
    if args.output:
        output = args.output.resolve()
        if output == args.survey.resolve() or output.is_relative_to(args.repositories.resolve()):
            parser.error("--output must not overwrite the survey or write inside the repository collection")
    records = latest_records(args.survey)
    results = []
    for task_id, record in sorted(records.items()):
        if record["status"] not in BLOCKED_STATUSES:
            continue
        result = inspect_record(record, args.repositories, timeout=args.timeout_seconds)
        results.append(result)
        print(f"{result['preflight']:30} {task_id}", file=sys.stderr, flush=True)
    report = {"scope": "Read-only repository preflight; no baseline statuses changed",
              "model_calls": 0,
              "baseline_counts": dict(Counter(r["status"] for r in records.values())),
              "counts": dict(Counter(r["preflight"] for r in results)), "tasks": results}
    serialized = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized, encoding="utf-8", newline="\n")
        print(json.dumps({"counts": report["counts"], "output": str(args.output)}))
    else:
        print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
