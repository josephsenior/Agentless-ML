"""Fail-closed interpretation of controller-declared reproduction reports."""

from dataclasses import replace

from agentless_ml.schemas import (
    TestCaseStatus, ValidationKind, ValidationResult, ValidationStatus,
)


def check_reproduction_result(
    result: ValidationResult, *, report_declared: bool,
) -> ValidationResult:
    if result.kind is not ValidationKind.REPRODUCTION:
        return result
    if result.status not in (ValidationStatus.PASS, ValidationStatus.FAIL):
        return result
    cases = result.test_cases
    invalid = (
        not report_declared or not cases
        or any(case.status in (TestCaseStatus.ERROR, TestCaseStatus.SKIPPED)
               for case in cases)
        or (result.status is ValidationStatus.FAIL
            and not any(case.status is TestCaseStatus.FAILED for case in cases))
        or (result.status is ValidationStatus.PASS
            and any(case.status is not TestCaseStatus.PASSED for case in cases))
    )
    return replace(result, status=ValidationStatus.HARNESS_ERROR) if invalid else result
