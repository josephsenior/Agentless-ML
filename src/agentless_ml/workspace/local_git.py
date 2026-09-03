"""Independent Git clones for patch checks; never execute repository code.

Only local repositories and full commit IDs are accepted. Each handle accepts
one patch attempt. Recreate rather than reset a dirty candidate workspace.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
import stat
import subprocess
import tempfile
import uuid
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Self

from agentless_ml.schemas import PatchCandidate
from agentless_ml.workspace.records import (
    PatchApplicationResult,
    PatchApplicationStatus,
    WorkspaceError,
    WorkspaceProvenance,
)


def _git(
    cwd: Path, *args: str, timeout: float, data: bytes | None = None
) -> subprocess.CompletedProcess[bytes]:
    # Do not inherit Git directory overrides, external diff drivers,
    # global filters, or executable hooks into a candidate checkout.
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
            "-c",
            "protocol.allow=never",
            "-c",
            "protocol.file.allow=always",
            *args,
        ],
        cwd=cwd,
        env=env,
        input=data,
        capture_output=True,
        timeout=timeout,
        check=False,
    )


def _require_git(cwd: Path, *args: str, timeout: float) -> bytes:
    try:
        result = _git(cwd, *args, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise WorkspaceError(f"Git operation failed: {type(exc).__name__}") from exc
    if result.returncode:
        raise WorkspaceError(result.stderr.decode("utf-8", errors="replace")[:2000])
    return result.stdout


def _safe_path(raw: str) -> str:
    path = PurePosixPath(raw)
    if not raw or path.is_absolute() or "\\" in raw:
        raise WorkspaceError(f"unsupported repository path: {raw!r}")
    for part in raw.split("/"):
        stem = part.split(".", 1)[0].upper()
        if (
            part in {"", ".", ".."}
            or part.casefold() in {".git", "git~1"}
            or part.endswith((" ", "."))
            or any(ord(char) < 32 or char in ':*?"<>|' for char in part)
            or stem in {"CON", "PRN", "AUX", "NUL"}
            or re.fullmatch(r"(?:COM|LPT)[1-9]", stem)
        ):
            raise WorkspaceError(f"unsupported repository path: {raw!r}")
    return path.as_posix()


def _tracked_paths(repository: Path, commit: str, timeout: float) -> frozenset[str]:
    listing = _require_git(
        repository, "ls-tree", "-rz", "--full-tree", commit, timeout=timeout
    )
    paths: set[str] = set()
    folded: set[str] = set()
    for record in listing.split(b"\0"):
        if not record:
            continue
        metadata, raw_path = record.split(b"\t", 1)
        mode, kind, _ = metadata.split()
        if mode not in {b"100644", b"100755"} or kind != b"blob":
            raise WorkspaceError(
                "symlinks and submodules are not supported by local-git-v1"
            )
        try:
            path = _safe_path(raw_path.decode("utf-8"))
        except UnicodeDecodeError as exc:
            raise WorkspaceError("non-UTF-8 repository path") from exc
        if path.casefold() in folded:
            raise WorkspaceError(f"case-colliding repository path: {path}")
        paths.add(path)
        folded.add(path.casefold())
    return frozenset(paths)


def _remove_owned(directory: Path, root: Path, token: str) -> None:
    # Never delete caller repositories, a workspace root, or a substituted link.
    if (
        directory.is_symlink()
        or directory.resolve() != directory
        or directory.parent != root
    ):
        raise WorkspaceError("refusing cleanup outside the owned workspace directory")
    marker = directory / ".owner"
    if marker.is_symlink() or marker.read_text(encoding="ascii") != token:
        raise WorkspaceError("workspace ownership marker changed; refusing cleanup")

    def remove_readonly(function, raw_path, error):
        target = Path(raw_path)
        if (
            not isinstance(error[1], PermissionError)
            or target.is_symlink()
            or not target.resolve().is_relative_to(directory)
            or not target.is_file()
        ):
            raise error[1]
        target.chmod(target.stat().st_mode | stat.S_IWUSR)
        function(raw_path)

    # Keep the ownership marker until the end so a failed cleanup can be retried.
    for child in directory.iterdir():
        if child == marker:
            continue
        if child.is_symlink() or child.is_file():
            child.unlink()
        else:
            shutil.rmtree(child, onerror=remove_readonly)
    marker.unlink()
    directory.rmdir()


class LocalGitWorkspaceProvider:
    """Provision trusted local fixtures at an immutable, explicitly selected commit."""

    def __init__(
        self,
        source_repository: Path,
        base_commit: str,
        workspace_root: Path,
        *,
        timeout_seconds: float = 60,
    ) -> None:
        if not re.fullmatch(r"[0-9a-fA-F]{40}|[0-9a-fA-F]{64}", base_commit):
            raise WorkspaceError("base_commit must be a full immutable commit ID")
        if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be finite and positive")
        self.source_repository = Path(source_repository).resolve(strict=True)
        self.workspace_root = Path(workspace_root).resolve()
        if self.workspace_root.is_relative_to(
            self.source_repository
        ) or self.source_repository.is_relative_to(self.workspace_root):
            raise WorkspaceError(
                "workspace root and source repository must be separate"
            )
        self.timeout_seconds = timeout_seconds
        top = _require_git(
            self.source_repository,
            "rev-parse",
            "--show-toplevel",
            timeout=timeout_seconds,
        )
        if Path(top.decode().strip()).resolve() != self.source_repository:
            raise WorkspaceError("source_repository must name the repository root")
        resolved = (
            _require_git(
                self.source_repository,
                "rev-parse",
                "--verify",
                base_commit + "^{commit}",
                timeout=timeout_seconds,
            )
            .decode()
            .strip()
        )
        if resolved != base_commit.lower():
            raise WorkspaceError("base_commit does not identify a commit object")
        self.base_commit = resolved
        self.base_tree = (
            _require_git(
                self.source_repository,
                "rev-parse",
                resolved + "^{tree}",
                timeout=timeout_seconds,
            )
            .decode()
            .strip()
        )
        self.paths = _tracked_paths(self.source_repository, resolved, timeout_seconds)

    def create(self) -> LocalGitWorkspace:
        """Create a detached, clean clone; ignore source working-tree modifications."""
        self.workspace_root.mkdir(parents=True, exist_ok=True)
        if self.workspace_root.resolve() != self.workspace_root:
            raise WorkspaceError("workspace root was replaced by a link")
        directory = Path(tempfile.mkdtemp(prefix="candidate-", dir=self.workspace_root))
        token = uuid.uuid4().hex
        (directory / ".owner").write_text(token, encoding="ascii")
        template = directory / "empty-template"
        template.mkdir()
        checkout = directory / "checkout"
        try:
            _require_git(
                directory,
                "clone",
                "--local",
                "--no-hardlinks",
                "--dissociate",
                "--no-checkout",
                "--no-recurse-submodules",
                "--template=" + str(template),
                "--",
                str(self.source_repository),
                str(checkout),
                timeout=self.timeout_seconds,
            )
            _require_git(
                checkout,
                "checkout",
                "--detach",
                self.base_commit,
                timeout=self.timeout_seconds,
            )
            # No remote fetches are part of this backend, including after provisioning.
            _require_git(
                checkout, "remote", "remove", "origin", timeout=self.timeout_seconds
            )
            version = (
                _require_git(checkout, "--version", timeout=self.timeout_seconds)
                .decode()
                .strip()
            )
            provenance = WorkspaceProvenance(
                workspace_id=directory.name,
                source_repository=str(self.source_repository),
                base_commit=self.base_commit,
                base_tree=self.base_tree,
                git_version=version,
                created_at=datetime.now(UTC).isoformat(),
            )
            workspace = LocalGitWorkspace(
                directory,
                self.workspace_root,
                token,
                provenance,
                self.paths,
                self.timeout_seconds,
            )
            workspace._require_pristine()
            (directory / "provenance.json").write_text(
                json.dumps(asdict(provenance), indent=2) + "\n",
                encoding="utf-8",
            )
            return workspace
        except BaseException:
            _remove_owned(directory, self.workspace_root, token)
            raise


class LocalGitWorkspace:
    """An owned candidate clone. Close it or use it as a context manager."""

    def __init__(
        self,
        directory: Path,
        root: Path,
        token: str,
        provenance: WorkspaceProvenance,
        paths: frozenset[str],
        timeout: float,
    ):
        self.path = directory / "checkout"
        self.provenance = provenance
        self._directory, self._root, self._token = directory, root, token
        self._paths, self._timeout = paths, timeout
        self._attempted = False
        self._closed = False

    def _require_pristine(self) -> None:
        if self._closed or self.path.is_symlink() or self.path.resolve() != self.path:
            raise WorkspaceError("workspace is closed or its checkout path changed")
        head = (
            _require_git(self.path, "rev-parse", "HEAD", timeout=self._timeout)
            .decode()
            .strip()
        )
        if head != self.provenance.base_commit:
            raise WorkspaceError("workspace HEAD differs from the pinned commit")
        status = _require_git(
            self.path,
            "status",
            "--porcelain",
            "--untracked-files=all",
            "--ignored",
            timeout=self._timeout,
        )
        if status:
            raise WorkspaceError("workspace is dirty; create a new workspace")

    def apply_candidate(self, candidate: PatchCandidate) -> PatchApplicationResult:
        if self._attempted:
            raise WorkspaceError(
                "one candidate attempt per workspace; create a new workspace"
            )
        self._require_pristine()
        self._attempted = True
        patch = candidate.diff.encode("utf-8")
        digest = hashlib.sha256(patch).hexdigest()

        def result(status: PatchApplicationStatus, message: str = "", paths=()):
            return PatchApplicationResult(
                candidate.candidate_id, digest, status, tuple(paths), message
            )

        if digest != candidate.diff_sha256:
            return result(
                PatchApplicationStatus.PATCH_ERROR, "candidate patch digest mismatch"
            )
        # This version accepts modifications to existing regular text files only.
        if any(
            line.startswith(
                (
                    "old mode ",
                    "new mode ",
                    "new file mode ",
                    "deleted file mode ",
                    "rename from ",
                    "copy from ",
                    "--- /dev/null",
                    "+++ /dev/null",
                    "GIT binary patch",
                    "Binary files ",
                )
            )
            for line in candidate.diff.splitlines()
        ):
            return result(
                PatchApplicationStatus.PATCH_ERROR, "unsupported file or mode change"
            )
        try:
            stat = _git(
                self.path,
                "apply",
                "--numstat",
                "-z",
                "-",
                timeout=self._timeout,
                data=patch,
            )
            if stat.returncode:
                return result(
                    PatchApplicationStatus.PATCH_ERROR,
                    stat.stderr.decode(errors="replace")[:2000],
                )
            paths = []
            for entry in stat.stdout.split(b"\0"):
                if not entry:
                    continue
                added, deleted, raw_path = entry.split(b"\t", 2)
                path = _safe_path(raw_path.decode("utf-8"))
                if added == b"-" or deleted == b"-" or path not in self._paths:
                    raise WorkspaceError(
                        "patch must modify existing regular text files"
                    )
                target = self.path / path
                if (
                    target.is_symlink()
                    or target.resolve() != target
                    or not target.is_file()
                ):
                    raise WorkspaceError("patch target is not an owned regular file")
                paths.append(path)
            if not paths:
                raise WorkspaceError("patch has no file changes")
            for options in (("--check", "--index"), ("--index",)):
                applied = _git(
                    self.path,
                    "apply",
                    *options,
                    "--whitespace=nowarn",
                    "-",
                    timeout=self._timeout,
                    data=patch,
                )
                if applied.returncode:
                    return result(
                        (
                            PatchApplicationStatus.PATCH_ERROR
                            if applied.returncode == 1
                            else PatchApplicationStatus.HARNESS_ERROR
                        ),
                        applied.stderr.decode(errors="replace")[:2000],
                    )
            changed = _git(
                self.path,
                "diff",
                "--cached",
                "--name-only",
                "-z",
                "--no-renames",
                timeout=self._timeout,
            )
            if changed.returncode:
                return result(
                    PatchApplicationStatus.HARNESS_ERROR, "cannot inspect applied patch"
                )
            actual = tuple(
                part.decode("utf-8") for part in changed.stdout.split(b"\0") if part
            )
            if not actual or set(actual) != set(paths):
                return result(
                    PatchApplicationStatus.HARNESS_ERROR,
                    "unexpected applied patch footprint",
                )
            return result(PatchApplicationStatus.APPLIED, paths=actual)
        except subprocess.TimeoutExpired:
            return result(
                PatchApplicationStatus.TIMEOUT,
                "Git patch operation timed out; discard workspace",
            )
        except (UnicodeError, ValueError, WorkspaceError) as exc:
            return result(PatchApplicationStatus.PATCH_ERROR, str(exc))
        except OSError as exc:
            return result(PatchApplicationStatus.HARNESS_ERROR, str(exc))

    def close(self) -> None:
        if not self._closed:
            _remove_owned(self._directory, self._root, self._token)
            self._closed = True

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()
