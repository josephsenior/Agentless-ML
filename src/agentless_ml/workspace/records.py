"""Workspace evidence is separate from test outcomes."""

from dataclasses import dataclass
from enum import StrEnum


class WorkspaceError(RuntimeError):
    """The workspace could not be prepared or is no longer safe to use."""


class PatchApplicationStatus(StrEnum):
    APPLIED = "applied"
    PATCH_ERROR = "patch_error"
    TIMEOUT = "timeout"
    HARNESS_ERROR = "harness_error"


@dataclass(frozen=True, slots=True)
class WorkspaceProvenance:
    workspace_id: str
    source_repository: str
    base_commit: str
    base_tree: str
    git_version: str
    created_at: str
    backend: str = "local-git-v1"


@dataclass(frozen=True, slots=True)
class PatchApplicationResult:
    candidate_id: str
    patch_sha256: str
    status: PatchApplicationStatus
    changed_paths: tuple[str, ...] = ()
    message: str = ""
