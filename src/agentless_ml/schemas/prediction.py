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


class TestCaseStatus(StrEnum):
    __test__ = False  # A result schema, not a pytest test class.

    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class TestCaseResult:
    """One individual test's outcome, read from a runner-written report."""

    __test__ = False

    test_id: str
    status: TestCaseStatus

    def __post_init__(self) -> None:
        if not self.test_id.strip() or any(c in self.test_id for c in "\r\n\0"):
            raise ValueError("test_id must be a nonempty single line")


@dataclass(frozen=True, slots=True)
class ValidationResult:
    status: ValidationStatus
    command: tuple[str, ...]
    duration_seconds: float
    exit_code: int | None = None
    stdout_digest: str | None = None
    stderr_digest: str | None = None
    kind: ValidationKind = ValidationKind.REGRESSION
    # Empty when the command declared no report: then the command is one unit.
    test_cases: tuple[TestCaseResult, ...] = ()
    # Test IDs whose failure counts during selection; None counts every test case.
    counted_test_ids: tuple[str, ...] | None = None

    def __post_init__(self) -> None:
        if self.duration_seconds < 0:
            raise ValueError("duration_seconds must not be negative")
        if not self.command:
            raise ValueError("validation command must not be empty")
        ids = [case.test_id for case in self.test_cases]
        if len(set(ids)) != len(ids):
            raise ValueError("test case IDs must be unique")
        # A FAIL with counted tests and no results is a patch that broke the
        # build; a PASS claiming counted tests with no results is never evidence.
        passed = self.status is ValidationStatus.PASS
        if self.counted_test_ids is not None and passed and not self.test_cases:
            raise ValueError("counted_test_ids requires per-test results")

    def failure_count(self) -> int:
        """How many selection units failed.

        Without a report the command is one unit. With a report, every failed or
        errored test counts. When ``counted_test_ids`` names the tests that passed
        on the unpatched code, each of those counts unless it passed again:
        skipped or missing from the report is not evidence that it still works.
        A failed run with no test results at all (a patch that broke the build)
        therefore counts every one of them.
        """
        if not self.test_cases:
            if self.status is ValidationStatus.PASS:
                return 0
            return len(self.counted_test_ids) if self.counted_test_ids else 1
        if self.counted_test_ids is None:
            return sum(
                case.status in (TestCaseStatus.FAILED, TestCaseStatus.ERROR)
                for case in self.test_cases
            )
        passed = {
            case.test_id
            for case in self.test_cases
            if case.status is TestCaseStatus.PASSED
        }
        return sum(test_id not in passed for test_id in self.counted_test_ids)


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
