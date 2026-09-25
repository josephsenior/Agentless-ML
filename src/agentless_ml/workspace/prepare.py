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
import tempfile
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

    # The clone is made and sealed in a temporary directory and moved into place
    # only once it is locked. While a clone still has its upstream address, an
    # editor that auto-fetches every repository in a folder it has open can
    # fetch into it: VS Code's git fetched 183,431 objects into a half-made
    # clone under benchmarks/, and held its files open so it could not be
    # removed.
    staging = Path(tempfile.mkdtemp(prefix="agentless-ml-seal-"))
    workdir = staging / destination.name
    try:
        branch, base_tree, git_version = _clone_and_seal(
            source, base_commit, workdir, timeout_seconds
        )
        shutil.move(str(workdir), str(destination))
        verify_sealed_repository(destination, base_commit, timeout_seconds=timeout_seconds)
    except BaseException:
        # A clone interrupted by a network drop or an unwritable path leaves a
        # partial repository behind. Left in place, the next run would mistake
        # it for a prepared one, so remove what this call created.
        _remove_tree(staging)
        _remove_tree(destination)
        raise
    _remove_tree(staging)
    sealed = SealedRepository(
        path=str(destination.resolve()),
        repository_url=repository_url,
        base_commit=base_commit,
        base_tree=base_tree,
        branch=branch,
        git_version=git_version,
        prepared_at=datetime.now(UTC).isoformat(),
    )
    (destination.parent / (destination.name + ".sealed.json")).write_text(
        json.dumps(asdict(sealed), indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    return sealed


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
    base_commit: str,
    destination: Path,
    timeout_seconds: float,
) -> tuple[str, str, str]:
    """Clone, seal and lock; return the branch, base tree and git version."""
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
    _prune_refs(destination, branch, timeout_seconds)
    _require(destination, "remote", "remove", "origin", timeout=timeout_seconds)
    lock_sealed_repository(destination)

    # Deleting refs only unlinks the later commits; the objects are still in the
    # repository, and reachable by ID, until the reflog is dropped and unreachable
    # objects are pruned.
    _require(destination, "reflog", "expire", "--expire=now", "--all", timeout=timeout_seconds)
    _require(destination, "gc", "--prune=now", timeout=timeout_seconds)

    verify_sealed_repository(destination, base_commit, timeout_seconds=timeout_seconds)
    return (
        branch,
        _require(destination, "rev-parse", base_commit + "^{tree}", timeout=timeout_seconds),
        _require(destination, "--version", timeout=timeout_seconds),
    )


def lock_sealed_repository(repository: Path) -> None:
    """Make any later network fetch into ``repository`` fail.

    Removing the remote is not enough. A sealed katex repository inside the
    folder an editor had open was fetched into 80 seconds after sealing and
    regained 268 later commits: the editor's git integration fetches every
    repository it finds, and did so while it still knew the upstream address.
    With every transport disallowed in the repository's own configuration,
    such a fetch fails whatever runs it. Cloning from the repository is
    unaffected, since that is governed by the cloning process's configuration.
    """
    _require(repository, "config", "protocol.allow", "never", timeout=30)


def _prune_refs(repository: Path, branch: str, timeout: float) -> None:
    """Delete every ref except ``branch`` and the tags already in its history.

    This is an allow-list. Deleting named kinds of ref (other branches, later
    tags, remote-tracking refs) left whatever a clone happened to contain
    beyond them: two DeepSWE clones made while upstream was being pushed to
    failed verification, one with later commits still referenced, one with
    ``refs/remotes/origin/HEAD`` pointing at nothing.
    """
    # A symbolic ref whose target is gone is skipped by for-each-ref but still
    # breaks later commands, so the remote's HEAD is removed without being
    # followed. It may not exist; that is not an error.
    _git(repository, "symbolic-ref", "--delete", "refs/remotes/origin/HEAD", timeout=30)
    keep = f"refs/heads/{branch}"
    for ref in _require(
        repository, "for-each-ref", "--format=%(refname)", timeout=timeout
    ).splitlines():
        if not ref or ref == keep:
            continue
        if ref.startswith("refs/tags/") and not _git(
            repository, "merge-base", "--is-ancestor", ref, "HEAD", timeout=60
        ).returncode:
            continue
        _require(repository, "update-ref", "--no-deref", "-d", ref, timeout=timeout)


def verify_sealed_repository(
    repository: Path, base_commit: str, *, timeout_seconds: float = 300
) -> None:
    """Raise unless nothing after ``base_commit`` remains in ``repository``."""
    repository = Path(repository)
    head = _require(repository, "rev-parse", "HEAD", timeout=timeout_seconds)
    if head != base_commit:
        raise WorkspaceError(f"sealed repository HEAD is {head}, not {base_commit}")
    listing = _git(
        repository, "for-each-ref", "--format=%(refname)", timeout=timeout_seconds
    )
    if listing.returncode or b"broken ref" in listing.stderr:
        raise WorkspaceError(
            "sealed repository has a broken ref: "
            + listing.stderr.decode("utf-8", errors="replace").strip()[:300]
        )
    stray = [
        ref
        for ref in listing.stdout.decode().split()
        if not ref.startswith(("refs/heads/", "refs/tags/"))
    ]
    if stray:
        raise WorkspaceError(f"sealed repository keeps refs it should not: {stray[:5]}")
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
    lock = _git(
        repository, "config", "--local", "--get", "protocol.allow", timeout=timeout_seconds
    )
    if lock.stdout.decode().strip() != "never":
        raise WorkspaceError(
            "sealed repository does not refuse network fetches (protocol.allow is not "
            "'never' in its own config); another program could fetch later history into it"
        )
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
