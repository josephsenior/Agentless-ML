"""Clone a task's repository and cut off everything after its base commit.

A benchmark task names an upstream repository and one commit in it. An ordinary
clone of that repository also contains every commit made after that one,
including, for these tasks, the commit that actually fixes the issue. The fix
would then sit in the clone the workflow reads from, which is held-out material.

This module produces a *sealed* clone: the base commit is the tip of the only
branch, no other branch, tag or remote survives, and the objects for later
commits are deleted from the object database. It mirrors what every DeepSWE
task's own ``environment/Dockerfile`` does when it builds the official image
(all 113 use a byte-identical recipe), so a sealed local clone contains the
same history the benchmark intends the agent to see.

This is the one place in the workflow that touches the network. It runs once,
ahead of a run; :mod:`agentless_ml.workspace.local_git` then clones from the
sealed repository offline, with remote protocols disabled.
"""

from __future__ import annotations

import json
import math
import os
import re
import shutil
import stat
import subprocess
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from agentless_ml.workspace.records import WorkspaceError

_COMMIT = re.compile(r"[0-9a-f]{40}")
_HTTPS_URL = re.compile(r"https://[A-Za-z0-9.-]+/[A-Za-z0-9._/-]+")


def _git(
    cwd: Path, *args: str, timeout: float
) -> subprocess.CompletedProcess[bytes]:
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.upper().startswith("GIT_")
    }
    env.update(
        GIT_CONFIG_NOSYSTEM="1",
        GIT_CONFIG_GLOBAL=os.devnull,
        GIT_TERMINAL_PROMPT="0",
        GIT_LFS_SKIP_SMUDGE="1",
    )
    return subprocess.run(
        [
            "git",
            "-c",
            "core.hooksPath=" + os.devnull,
            "-c",
            "core.fsmonitor=false",
            "-c",
            "core.autocrlf=false",
            "-c",
            "core.attributesFile=" + os.devnull,
            # Benchmark repositories are built on Linux and contain paths longer
            # than Windows' default limit; actionlint's testdata alone fails a
            # clone here with "Filename too long" without this.
            "-c",
            "core.longpaths=true",
            # Only the transports this step needs: HTTPS for upstream, file for
            # fixtures. No ssh, no git://, no helper-invoked transports.
            "-c",
            "protocol.allow=never",
            "-c",
            "protocol.https.allow=always",
            "-c",
            "protocol.file.allow=always",
            *args,
        ],
        cwd=cwd,
        env=env,
        capture_output=True,
        timeout=timeout,
        check=False,
    )


def _require(cwd: Path, *args: str, timeout: float) -> str:
    try:
        result = _git(cwd, *args, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise WorkspaceError(f"Git operation failed: {type(exc).__name__}") from exc
    if result.returncode:
        raise WorkspaceError(result.stderr.decode("utf-8", errors="replace")[:2000])
    return result.stdout.decode("utf-8", errors="replace").strip()


@dataclass(frozen=True, slots=True)
class SealedRepository:
    """A prepared clone holding no history after ``base_commit``."""

    path: str
    repository_url: str
    base_commit: str
    base_tree: str
    branch: str
    git_version: str
    prepared_at: str


def _source(repository_url: str) -> str:
    if _HTTPS_URL.fullmatch(repository_url.removesuffix(".git")):
        return repository_url
    local = Path(repository_url)
    if local.is_dir():
        return str(local.resolve(strict=True))
    raise WorkspaceError(
        "repository_url must be an HTTPS URL or an existing local directory"
    )


def prepare_sealed_repository(
    repository_url: str,
    base_commit: str,
    destination: Path,
    *,
    timeout_seconds: float = 1800,
) -> SealedRepository:
    """Clone ``repository_url`` into ``destination`` sealed at ``base_commit``."""
    if not _COMMIT.fullmatch(base_commit):
        raise WorkspaceError("base_commit must be a full lowercase Git commit ID")
    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be finite and positive")
    source = _source(repository_url)
    destination = Path(destination)
    if destination.exists():
        raise WorkspaceError(f"destination already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)

    try:
        return _clone_and_seal(
            source, repository_url, base_commit, destination, timeout_seconds
        )
    except BaseException:
        # A clone interrupted by a network drop or an unwritable path leaves a
        # partial repository behind. Left in place, the next run would mistake
        # it for a prepared one, so remove what this call created.
        _remove_tree(destination)
        raise


def _remove_tree(directory: Path) -> None:
    if not directory.exists():
        return

    def force_writable(function, raw_path, error):
        target = Path(raw_path)
        if isinstance(error[1], PermissionError) and target.is_file():
            target.chmod(target.stat().st_mode | stat.S_IWUSR)
            function(raw_path)
        else:
            raise error[1]

    shutil.rmtree(directory, onerror=force_writable)


def _clone_and_seal(
    source: str,
    repository_url: str,
    base_commit: str,
    destination: Path,
    timeout_seconds: float,
) -> SealedRepository:
    _require(
        destination.parent,
        "clone",
        "--no-checkout",
        "--no-recurse-submodules",
        "--",
        source,
        str(destination),
        timeout=timeout_seconds,
    )
    # The clone recorded upstream's default branch; asking the remote again
    # would need the network a second time.
    head = _git(
        destination, "symbolic-ref", "--short", "refs/remotes/origin/HEAD", timeout=30
    )
    branch = (
        head.stdout.decode().strip().removeprefix("origin/")
        if not head.returncode
        else "main"
    ) or "main"

    # Point the default branch AT the base commit, exactly as the task images
    # do, so the checkout looks like an ordinary branch rather than a detached
    # HEAD that some build tooling treats as a broken repository.
    _require(destination, "checkout", "-B", branch, base_commit, timeout=timeout_seconds)
    _require(destination, "remote", "remove", "origin", timeout=timeout_seconds)

    for ref in _require(
        destination,
        "for-each-ref",
        "--format=%(refname:short)",
        "refs/heads",
        timeout=timeout_seconds,
    ).splitlines():
        if ref and ref != branch:
            _require(destination, "branch", "-D", ref, timeout=timeout_seconds)
    for tag in _require(destination, "tag", timeout=timeout_seconds).splitlines():
        if tag and _git(
            destination, "merge-base", "--is-ancestor", tag, "HEAD", timeout=60
        ).returncode:
            _require(destination, "tag", "-d", tag, timeout=timeout_seconds)
    for ref in _require(
        destination,
        "for-each-ref",
        "--format=%(refname)",
        "refs/remotes",
        timeout=timeout_seconds,
    ).splitlines():
        if ref:
            _require(destination, "update-ref", "-d", ref, timeout=timeout_seconds)

    # Deleting refs only unlinks the later commits; the objects are still in the
    # repository, and reachable by ID, until the reflog is dropped and unreachable
    # objects are pruned.
    _require(destination, "reflog", "expire", "--expire=now", "--all", timeout=timeout_seconds)
    _require(destination, "gc", "--prune=now", timeout=timeout_seconds)

    verify_sealed_repository(destination, base_commit, timeout_seconds=timeout_seconds)
    sealed = SealedRepository(
        path=str(destination.resolve()),
        repository_url=repository_url,
        base_commit=base_commit,
        base_tree=_require(
            destination, "rev-parse", base_commit + "^{tree}", timeout=timeout_seconds
        ),
        branch=branch,
        git_version=_require(destination, "--version", timeout=timeout_seconds),
        prepared_at=datetime.now(UTC).isoformat(),
    )
    (destination.parent / (destination.name + ".sealed.json")).write_text(
        json.dumps(asdict(sealed), indent=2) + "\n", encoding="utf-8"
    )
    return sealed


def verify_sealed_repository(
    repository: Path, base_commit: str, *, timeout_seconds: float = 300
) -> None:
    """Raise unless nothing after ``base_commit`` remains in ``repository``."""
    repository = Path(repository)
    head = _require(repository, "rev-parse", "HEAD", timeout=timeout_seconds)
    if head != base_commit:
        raise WorkspaceError(f"sealed repository HEAD is {head}, not {base_commit}")
    extra = _require(
        repository, "rev-list", "--all", "--not", "HEAD", timeout=timeout_seconds
    )
    if extra:
        raise WorkspaceError(
            "sealed repository still references commits outside the base commit's "
            "history: " + " ".join(extra.split()[:5])
        )
    remotes = _require(repository, "remote", timeout=timeout_seconds)
    if remotes:
        raise WorkspaceError(f"sealed repository still has remotes: {remotes}")
    unreachable = [
        line
        for line in _require(
            repository,
            "fsck",
            "--unreachable",
            "--no-reflogs",
            "--no-progress",
            timeout=timeout_seconds,
        ).splitlines()
        if line.startswith("unreachable commit")
    ]
    if unreachable:
        raise WorkspaceError(
            f"sealed repository keeps {len(unreachable)} unreachable commits; "
            "they were unlinked but not pruned"
        )
