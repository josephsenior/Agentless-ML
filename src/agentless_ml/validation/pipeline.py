"""Connect independent candidate checkouts to a fixed public validation schedule."""

import json
from collections.abc import Sequence
from dataclasses import asdict, replace
from pathlib import Path

from agentless_ml.schemas import PatchCandidate, ValidationResult, ValidationStatus
from agentless_ml.workspace import PatchApplicationStatus, WorkspaceError
from agentless_ml.workspace.base import WorkspaceProvider

from .docker import DockerTestRunner, PublicTestCommand


def validate_candidate(
    candidate: PatchCandidate,
    provider: WorkspaceProvider,
    runner: DockerTestRunner,
    commands: Sequence[PublicTestCommand],
    *,
    artifact_root: Path | None = None,
) -> PatchCandidate:
    """Replace prior evidence; every command gets a fresh container.

    Call with the same frozen command schedule for every candidate. Public test
    commands and images are trusted controller inputs, never model outputs.
    """
    if not commands:
        raise ValueError("at least one public test command is required")
    evidence = []
    try:
        with provider.create() as workspace:
            application = workspace.apply_candidate(candidate)
            if application.status is not PatchApplicationStatus.APPLIED:
                evidence.append(
                    ValidationResult(
                        status=ValidationStatus(application.status.value),
                        command=("git", "apply", "--check"),
                        duration_seconds=0,
                    )
                )
            else:
                for command in commands:
                    execution = runner.run(
                        workspace.path, command, artifact_root=artifact_root
                    )
                    evidence.append(execution.result)
                    Path(execution.artifact_directory, "candidate.json").write_text(
                        json.dumps(
                            {
                                "candidate_id": candidate.candidate_id,
                                "patch_sha256": candidate.diff_sha256,
                                "workspace": asdict(workspace.provenance),
                                "application": asdict(application),
                            },
                            indent=2,
                        )
                        + "\n",
                        encoding="utf-8",
                    )
    except WorkspaceError:
        evidence.append(
            ValidationResult(
                status=ValidationStatus.HARNESS_ERROR,
                command=("workspace",),
                duration_seconds=0,
            )
        )
    return replace(candidate, validation=tuple(evidence))
