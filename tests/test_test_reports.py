import json

import pytest

from agentless_ml.repair import build_patch_candidate, select_candidate
from agentless_ml.schemas import (
    TestCaseResult,
    TestCaseStatus,
    ValidationResult,
    ValidationStatus,
)
from agentless_ml.validation import (
    PublicTestCommand,
    ReportError,
    ReportFormat,
    TestReport,
    parse_report,
)

P, F, S, E = (
    TestCaseStatus.PASSED,
    TestCaseStatus.FAILED,
    TestCaseStatus.SKIPPED,
    TestCaseStatus.ERROR,
)

# Shape written by `pytest --junitxml` (testsuites > testsuite > testcase).
PYTEST_JUNIT = b"""<?xml version="1.0" encoding="utf-8"?>
<testsuites name="pytest tests"><testsuite name="pytest" errors="1" failures="1" skipped="1" tests="4">
<testcase classname="tests.test_log.TestHideQtWarning" name="test_filter" time="0.001"/>
<testcase classname="tests.test_log.TestHideQtWarning" name="test_unfiltered[prefix]" time="0.001"><failure message="AssertionError">assert 1 == 2</failure></testcase>
<testcase classname="tests.test_log" name="test_setup" time="0"><error message="fixture failed"/></testcase>
<testcase classname="tests.test_log" name="test_windows_only" time="0"><skipped type="pytest.skip" message="windows"/></testcase>
</testsuite></testsuites>"""

# Shape written by cargo-nextest: one testsuite per test binary, root is testsuites.
NEXTEST_JUNIT = b"""<?xml version="1.0" encoding="UTF-8"?>
<testsuites name="nextest-run" tests="2" failures="0" errors="0">
<testsuite name="boa_engine" tests="2">
<testcase name="builtins::array::tests::push" classname="boa_engine" timestamp="2026-01-01T00:00:00Z" time="0.010"/>
<testcase name="builtins::array::tests::pop" classname="boa_engine" timestamp="2026-01-01T00:00:00Z" time="0.010"/>
</testsuite></testsuites>"""

# Shape written by go-ctrf-json-reporter: suite is the Go package.
GO_CTRF = json.dumps(
    {
        "results": {
            "tool": {"name": "gotest"},
            "summary": {"tests": 3},
            "tests": [
                {"name": "TestRequire", "status": "passed", "suite": "github.com/abs-lang/abs/evaluator"},
                {"name": "TestSource", "status": "failed", "suite": "github.com/abs-lang/abs/evaluator"},
                {"name": "TestFlaky", "status": "skipped", "suite": "github.com/abs-lang/abs/repl"},
            ],
        }
    }
).encode()


def statuses(cases):
    return [(case.test_id, case.status) for case in cases]


def test_pytest_junit_ids_and_statuses():
    assert statuses(parse_report(PYTEST_JUNIT, ReportFormat.JUNIT_XML)) == [
        ("tests.test_log.TestHideQtWarning::test_filter", P),
        ("tests.test_log.TestHideQtWarning::test_unfiltered[prefix]", F),
        ("tests.test_log::test_setup", E),
        ("tests.test_log::test_windows_only", S),
    ]


def test_nextest_junit():
    assert statuses(parse_report(NEXTEST_JUNIT, ReportFormat.JUNIT_XML)) == [
        ("boa_engine::builtins::array::tests::push", P),
        ("boa_engine::builtins::array::tests::pop", P),
    ]


def test_go_ctrf_ids_and_statuses():
    assert statuses(parse_report(GO_CTRF, ReportFormat.CTRF_JSON)) == [
        ("github.com/abs-lang/abs/evaluator::TestRequire", P),
        ("github.com/abs-lang/abs/evaluator::TestSource", F),
        ("github.com/abs-lang/abs/repl::TestFlaky", S),
    ]


def test_ctrf_other_and_pending_statuses_and_missing_suite():
    report = json.dumps(
        {"results": {"tests": [{"name": "a", "status": "other"}, {"name": "b", "status": "pending"}]}}
    ).encode()
    assert statuses(parse_report(report, ReportFormat.CTRF_JSON)) == [("a", E), ("b", S)]


def test_duplicate_test_keeps_the_worst_outcome():
    report = json.dumps(
        {
            "results": {
                "tests": [
                    {"name": "t", "status": "passed"},
                    {"name": "t", "status": "failed"},
                    {"name": "t", "status": "passed"},
                ]
            }
        }
    ).encode()
    assert statuses(parse_report(report, ReportFormat.CTRF_JSON)) == [("t", F)]


@pytest.mark.parametrize(
    "data,report_format,message",
    [
        (b"<testsuites></testsuites>", ReportFormat.JUNIT_XML, "no test cases"),
        (b"<testsuites><testcase", ReportFormat.JUNIT_XML, "malformed JUnit"),
        (b"<html/>", ReportFormat.JUNIT_XML, "unexpected JUnit root"),
        (
            b'<!DOCTYPE x [<!ENTITY a "aaaa">]><testsuites><testcase name="&a;"/></testsuites>',
            ReportFormat.JUNIT_XML,
            "DOCTYPE",
        ),
        (b"{", ReportFormat.CTRF_JSON, "malformed CTRF"),
        (b'{"results": {}}', ReportFormat.CTRF_JSON, "no results.tests"),
        (b'{"results": {"tests": [{"name": "a", "status": "flaky"}]}}', ReportFormat.CTRF_JSON, "unknown CTRF"),
        (b'{"results": {"tests": [{"status": "passed"}]}}', ReportFormat.CTRF_JSON, "no name"),
    ],
)
def test_malformed_reports_are_rejected(data, report_format, message):
    with pytest.raises(ReportError, match=message):
        parse_report(data, report_format)


def test_oversized_report_is_rejected(monkeypatch):
    from agentless_ml.validation import reports

    monkeypatch.setattr(reports, "MAX_REPORT_BYTES", 10)
    with pytest.raises(ReportError, match="exceeds"):
        parse_report(NEXTEST_JUNIT, ReportFormat.JUNIT_XML)


@pytest.mark.parametrize(
    "path,container_path",
    [("report.xml", "/tmp/work/report.xml"), ("out/r.json", "/tmp/work/out/r.json"), ("/tmp/r.xml", "/tmp/r.xml")],
)
def test_report_paths(path, container_path):
    assert TestReport(ReportFormat.JUNIT_XML, path).container_path() == container_path


@pytest.mark.parametrize("path", ["", "../r.xml", "/etc/r.xml", "/tmp", "a\\b.xml", "/tmp/../etc/r"])
def test_unsafe_report_paths_are_rejected(path):
    with pytest.raises(ValueError):
        TestReport(ReportFormat.JUNIT_XML, path)


def test_counted_test_ids_need_a_report():
    with pytest.raises(ValueError, match="requires a test report"):
        PublicTestCommand(("pytest",), counted_test_ids=("a",))


def result(cases, counted=None, status=ValidationStatus.FAIL):
    return ValidationResult(
        status=status,
        command=("pytest",),
        duration_seconds=0,
        test_cases=tuple(TestCaseResult(i, s) for i, s in cases),
        counted_test_ids=counted,
    )


def test_failure_count_rules():
    cases = [("a", P), ("b", F), ("c", E), ("d", S)]
    # Every failed or errored test counts; a skip is not a failure.
    assert result(cases).failure_count() == 2
    # Counted tests passed on the unpatched code: each counts unless it passed again.
    assert result(cases, counted=("a", "d")).failure_count() == 1
    assert result(cases, counted=("a", "missing")).failure_count() == 1
    # Without a report the command is one unit.
    assert result([], status=ValidationStatus.FAIL).failure_count() == 1
    assert result([], status=ValidationStatus.PASS).failure_count() == 0
    # A failed run with no results at all broke the build: every counted test.
    assert result([], counted=("a", "b", "c")).failure_count() == 3


def test_a_pass_claiming_counted_tests_needs_results():
    with pytest.raises(ValueError, match="requires per-test results"):
        result([], counted=("a",), status=ValidationStatus.PASS)


def candidate(candidate_id, diff_line, cases):
    base = build_patch_candidate(
        candidate_id=candidate_id,
        raw_response="",
        diff=f"--- a/x.py\n+++ b/x.py\n@@ -1 +1 @@\n-old\n+{diff_line}\n",
        localization_rank=0,
        sample_index=int(candidate_id[-1]),
    )
    from dataclasses import replace

    return replace(base, validation=(result(cases),))


def test_selection_counts_individual_failing_tests():
    many = [(f"t{i}", P) for i in range(98)]
    # Both candidates fail their suite command; one breaks two tests, one breaks one.
    worse = candidate("c0", "worse", many + [("x", F), ("y", F)])
    better = candidate("c1", "better", many + [("x", P), ("y", F)])
    selection = select_candidate([worse, better])
    assert selection.candidate.candidate_id == "c1"
    assert selection.considered_candidate_ids == ("c1",)
