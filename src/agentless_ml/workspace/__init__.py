"""Pinned, per-candidate workspaces (not a code-execution sandbox)."""

from agentless_ml.workspace.base import CandidateWorkspace, WorkspaceProvider
from agentless_ml.workspace.local_git import (
    LocalGitWorkspace,
    LocalGitWorkspaceProvider,
)
from agentless_ml.workspace.records import (
    PatchApplicationResult,
    PatchApplicationStatus,
    WorkspaceError,
    WorkspaceProvenance,
)

__all__ = [
    "CandidateWorkspace",
    "LocalGitWorkspace",
    "LocalGitWorkspaceProvider",
    "PatchApplicationResult",
    "PatchApplicationStatus",
    "WorkspaceError",
    "WorkspaceProvenance",
    "WorkspaceProvider",
]
