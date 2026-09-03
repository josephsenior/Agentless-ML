"""Minimal workspace interface for future container-backed implementations."""

from pathlib import Path
from typing import Protocol, Self

from agentless_ml.schemas import PatchCandidate
from agentless_ml.workspace.records import PatchApplicationResult, WorkspaceProvenance


class CandidateWorkspace(Protocol):
    path: Path
    provenance: WorkspaceProvenance

    def apply_candidate(self, candidate: PatchCandidate) -> PatchApplicationResult: ...

    def close(self) -> None: ...

    def __enter__(self) -> Self: ...

    def __exit__(self, exc_type, exc_value, traceback) -> None: ...


class WorkspaceProvider(Protocol):
    def create(self) -> CandidateWorkspace: ...
