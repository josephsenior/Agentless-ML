"""Read per-test outcomes from the two report formats test runners write.

Benchmark images already ship reporters for one of two formats in every task
language: JUnit XML (pytest ``--junitxml``, cargo-nextest, vitest) and CTRF JSON
(``go-ctrf-json-reporter``, ``jest-ctrf-json-reporter``,
``mocha-ctrf-json-reporter``). Parsing the format, not the framework, keeps
language and framework knowledge in the command declaration.

Reports are written by repository code under test, so they are untrusted input:
size is capped before parsing, XML entities are refused, and anything malformed
raises ``ReportError`` instead of producing partial evidence.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import PurePosixPath
from xml.etree import ElementTree

from agentless_ml.schemas import TestCaseResult, TestCaseStatus

MAX_REPORT_BYTES = 32 * 1024 * 1024

_SEVERITY = {
    TestCaseStatus.SKIPPED: 0,
    TestCaseStatus.PASSED: 1,
    TestCaseStatus.FAILED: 2,
    TestCaseStatus.ERROR: 3,
}


class ReportError(ValueError):
    """A declared test report is missing, oversized or malformed."""


class ReportFormat(StrEnum):
    JUNIT_XML = "junit-xml"
    CTRF_JSON = "ctrf-json"


@dataclass(frozen=True, slots=True)
class TestReport:
    """Where a trusted command writes its report, and in which format.

    A relative ``path`` is inside the source copy; an absolute one must be under
    ``/tmp``, the only writable location in the container.
    """

    __test__ = False

    format: ReportFormat
    path: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "format", ReportFormat(self.format))
        pure = PurePosixPath(self.path)
        if (
            not self.path
            or any(c in self.path for c in "\0\r\n\\")
            or ".." in pure.parts
            or (pure.is_absolute() and pure.parts[:2] != ("/", "tmp"))
            or str(pure) in (".", "/tmp")
        ):
            raise ValueError("report path must be a file inside the work copy or /tmp")

    def container_path(self) -> str:
        pure = PurePosixPath(self.path)
        return str(pure if pure.is_absolute() else PurePosixPath("/tmp/work") / pure)


def parse_report(data: bytes, report_format: ReportFormat) -> tuple[TestCaseResult, ...]:
    """Parse report bytes into unique test outcomes, in report order."""
    if len(data) > MAX_REPORT_BYTES:
        raise ReportError(f"test report exceeds {MAX_REPORT_BYTES} bytes")
    if report_format is ReportFormat.JUNIT_XML:
        cases = _junit_cases(data)
    elif report_format is ReportFormat.CTRF_JSON:
        cases = _ctrf_cases(data)
    else:  # pragma: no cover - ReportFormat is closed
        raise ReportError(f"unsupported report format: {report_format}")
    if not cases:
        raise ReportError("test report contains no test cases")
    # The same test can appear twice (reruns, duplicated suites); keep the worst.
    merged: dict[str, TestCaseStatus] = {}
    for test_id, status in cases:
        previous = merged.get(test_id)
        if previous is None or _SEVERITY[status] > _SEVERITY[previous]:
            merged[test_id] = status
    return tuple(TestCaseResult(test_id, status) for test_id, status in merged.items())


def _test_id(*parts: object) -> str:
    text = [str(part).strip() for part in parts if isinstance(part, str) and part.strip()]
    if not text:
        raise ReportError("test case has no name")
    test_id = "::".join(text)
    if any(c in test_id for c in "\r\n\0"):
        raise ReportError("test case name must be a single line")
    return test_id


def _junit_cases(data: bytes) -> list[tuple[str, TestCaseStatus]]:
    # Refusing any DOCTYPE rules out entity-expansion and external-entity tricks.
    if b"<!DOCTYPE" in data[:4096].upper() or b"<!ENTITY" in data.upper():
        raise ReportError("JUnit report must not declare a DOCTYPE or entities")
    try:
        root = ElementTree.fromstring(data)
    except ElementTree.ParseError as exc:
        raise ReportError(f"malformed JUnit XML: {exc}") from exc
    if root.tag not in ("testsuites", "testsuite"):
        raise ReportError(f"unexpected JUnit root element: {root.tag}")
    cases = []
    for case in root.iter("testcase"):
        test_id = _test_id(case.get("classname"), case.get("name"))
        children = {child.tag for child in case}
        if "error" in children:
            status = TestCaseStatus.ERROR
        elif "failure" in children:
            status = TestCaseStatus.FAILED
        elif "skipped" in children:
            status = TestCaseStatus.SKIPPED
        else:
            status = TestCaseStatus.PASSED
        cases.append((test_id, status))
    return cases


_CTRF_STATUS = {
    "passed": TestCaseStatus.PASSED,
    "failed": TestCaseStatus.FAILED,
    "skipped": TestCaseStatus.SKIPPED,
    "pending": TestCaseStatus.SKIPPED,
    "other": TestCaseStatus.ERROR,
}


def _ctrf_cases(data: bytes) -> list[tuple[str, TestCaseStatus]]:
    try:
        document = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReportError(f"malformed CTRF JSON: {exc}") from exc
    tests = (
        document.get("results", {}).get("tests")
        if isinstance(document, dict) and isinstance(document.get("results"), dict)
        else None
    )
    if not isinstance(tests, list):
        raise ReportError("CTRF report has no results.tests list")
    cases = []
    for test in tests:
        if not isinstance(test, dict):
            raise ReportError("CTRF test entry must be an object")
        status = _CTRF_STATUS.get(test.get("status"))
        if status is None:
            raise ReportError(f"unknown CTRF test status: {test.get('status')!r}")
        suite = test.get("suite")
        if isinstance(suite, list):
            suite = "::".join(str(part) for part in suite)
        cases.append((_test_id(suite, test.get("name")), status))
    return cases
