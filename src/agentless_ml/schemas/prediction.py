"""Candidate and final-output contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ValidationStatus(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    PATCH_ERROR = "patch_error"
    TIMEOUT = "timeout"
    OUT_OF_MEMORY = "out_of_memory"
    HARNESS_ERROR = "harness_error"


class ValidationKind(StrEnum):
    REGRESSION = "regression"
    REPRODUCTION = "reproduction"


@dataclass(frozen=True, slots=True)
class ValidationResult:
    status: ValidationStatus
    command: tuple[str, ...]
    duration_seconds: float
    exit_code: int | None = None
    stdout_digest: str | None = None
    stderr_digest: str | None = None
    kind: ValidationKind = ValidationKind.REGRESSION

    def __post_init__(self) -> None:
        if self.duration_seconds < 0:
            raise ValueError("duration_seconds must not be negative")
        if not self.command:
            raise ValueError("validation command must not be empty")


@dataclass(frozen=True, slots=True)
class PatchCandidate:
    candidate_id: str
    diff: str
    diff_sha256: str
    localization_rank: int
    sample_index: int
    validation: tuple[ValidationResult, ...] = ()
    raw_response: str = ""
    normalized_diff: str = ""

    def __post_init__(self) -> None:
        if not self.candidate_id.strip() or not self.diff.strip():
            raise ValueError("candidate_id and diff must not be empty")
        if self.localization_rank < 0 or self.sample_index < 0:
            raise ValueError("candidate ranks must not be negative")
        if not self.normalized_diff:
            object.__setattr__(self, "normalized_diff", self.diff.strip())


@dataclass(frozen=True, slots=True)
class FinalPrediction:
    instance_id: str
    model_patch: str
    selected_candidate_id: str
    model_name: str

    def __post_init__(self) -> None:
        if not all(
            value.strip()
            for value in (
                self.instance_id,
                self.model_patch,
                self.selected_candidate_id,
                self.model_name,
            )
        ):
            raise ValueError("final prediction fields must not be empty")
