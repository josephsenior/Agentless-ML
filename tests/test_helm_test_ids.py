"""Helm's four dynamic paths are matching metadata, not rewritten test output."""

import json
from pathlib import Path

import pytest

from agentless_ml.adapters.benchmarks.deepswe_execution import (
    TEST_COMMANDS, deepswe_test_command, deepswe_test_plan, load_test_overrides,
)
from agentless_ml.schemas import TestCaseStatus, ValidationResult, ValidationStatus
from agentless_ml.validation import ReportError, ReportFormat, TestReport, parse_report
from agentless_ml.validation.reports import HELM_SAVE_TEMPDIR_POLICY

PACKAGES = ("helm.sh/helm/v4/internal/chart/v3/util", "helm.sh/helm/v4/pkg/chart/v2/util")
OVERRIDES = Path(__file__).resolve().parents[1] / "experiments/deepswe/test_overrides.json"


def report(*entries):
    return json.dumps({"results": {"tests": [
        {"suite": suite, "name": name, "status": status}
        for suite, name, status in entries
    ]}}).encode()


def stable(data):
    return parse_report(data, ReportFormat.CTRF_JSON, id_policy=HELM_SAVE_TEMPDIR_POLICY)


@pytest.mark.parametrize("package", PACKAGES)
@pytest.mark.parametrize("suffix", ("", "/newdir"))
def test_exact_helm_cases_match_and_keep_status_and_raw_bytes(package, suffix):
    first = report((package, "TestSave/outDir=/tmp/TestSave12345/001" + suffix, "passed"))
    second = report((package, "TestSave/outDir=/tmp/TestSave98765/001" + suffix, "passed"))
    original = first[:]
    assert stable(first) == stable(second)
    assert first == original
    assert stable(first)[0].test_id == package + "::TestSave/outDir=/tmp/TestSave{random}/001" + suffix
    assert parse_report(first, ReportFormat.CTRF_JSON) != parse_report(second, ReportFormat.CTRF_JSON)


@pytest.mark.parametrize("package,name", [
    ("other/util", "TestSave/outDir=/tmp/TestSave12345/001"),
    (PACKAGES[0] + "/extra", "TestSave/outDir=/tmp/TestSave12345/001"),
    (PACKAGES[0], "TestSaveOther/outDir=/tmp/TestSave12345/001"),
    (PACKAGES[0], "TestSave/outDir=/var/tmp/TestSave12345/001"),
    (PACKAGES[0], "TestSave/outDir=/tmp/TestSaveabc/001"),
    (PACKAGES[0], "TestSave/outDir=/tmp/TestSave12345/002"),
    (PACKAGES[0], "TestSave/outDir=/tmp/TestSave12345/001/other"),
    (PACKAGES[0], "TestSave/outDir=/tmp/TestSave12345/001/newdir/child"),
    (PACKAGES[0], "TestSave/outDir=/tmp/TestSave12345/001#01"),
    (PACKAGES[0], "prefix/TestSave/outDir=/tmp/TestSave12345/001"),
        (PACKAGES[0], "TestSave/outDir=/tmp/TestSave12345/001\n/child"),
    (PACKAGES[0], "TestSave"),
])
def test_near_matches_remain_unchanged(package, name):
    data = report((package, name, "passed"))
    assert stable(data) == parse_report(data, ReportFormat.CTRF_JSON)


@pytest.mark.parametrize("second", ("67890", "{random}"))
def test_distinct_raw_cases_cannot_collapse(second):
    with pytest.raises(ReportError, match="normalization collision"):
        stable(report(
            (PACKAGES[0], "TestSave/outDir=/tmp/TestSave12345/001", "passed"),
            (PACKAGES[0], "TestSave/outDir=/tmp/TestSave" + second + "/001", "failed"),
        ))


def test_exact_raw_rerun_keeps_worst_status():
    name = "TestSave/outDir=/tmp/TestSave12345/001"
    cases = stable(report((PACKAGES[0], name, "passed"), (PACKAGES[0], name, "failed")))
    assert len(cases) == 1 and cases[0].status == TestCaseStatus.FAILED


def test_four_cases_stay_distinct_and_regressions_are_counted():
    def cases(digits, status="passed"):
        return stable(report(*[
            (package, "TestSave/outDir=/tmp/TestSave" + digits + "/001" + suffix, status)
            for package in PACKAGES for suffix in ("", "/newdir")
        ]))
    baseline = cases("12345")
    counted = tuple(case.test_id for case in baseline)
    assert len(set(counted)) == 4

    def failures(observed):
        return ValidationResult(
            status=ValidationStatus.FAIL,
            command=("go", "test"),
            duration_seconds=0,
            test_cases=observed,
            counted_test_ids=counted,
        ).failure_count()

    assert failures(cases("67890")) == 0
    assert failures(cases("67890", "failed")) == 4
    assert failures(cases("67890", "skipped")) == 4
    assert failures(cases("67890")[:-1]) == 1


@pytest.mark.parametrize("format", (ReportFormat.JUNIT_XML, ReportFormat.MOCHA_JSON))
def test_policy_refuses_other_formats(format):
    with pytest.raises(ValueError, match="unsupported test ID policy"):
        TestReport(format, "/tmp/report", id_policy=HELM_SAVE_TEMPDIR_POLICY)
    with pytest.raises(ValueError, match="unsupported test ID policy"):
        parse_report(b"{}", format, id_policy=HELM_SAVE_TEMPDIR_POLICY)


@pytest.mark.parametrize("task_id", ("helm-array-merge-strategies", "helm-unified-manifest-stream"))
def test_only_helm_overrides_change_matching_not_execution(tmp_path, task_id):
    overrides = load_test_overrides(OVERRIDES)
    assert {key for key, value in overrides.items() if value.get("runner") == "helm-go"} == {
        "helm-array-merge-strategies", "helm-unified-manifest-stream",
    }
    (tmp_path / "go.mod").write_text("module helm.sh/helm/v4\n")
    plan = deepswe_test_plan("go", tmp_path, overrides[task_id])
    assert plan.runner == "helm-go" and plan.targets == ("./...",)
    command = plan.command(timeout_seconds=123)
    ordinary = deepswe_test_command("go", plan.targets, timeout_seconds=123)
    assert command.argv == ordinary.argv
    assert command.failure_exit_codes == ordinary.failure_exit_codes
    assert command.timeout_seconds == ordinary.timeout_seconds
    assert command.report.path == ordinary.report.path
    assert command.report.format == ordinary.report.format
    assert command.report.id_policy == HELM_SAVE_TEMPDIR_POLICY
    assert ordinary.report.id_policy is None
    assert TEST_COMMANDS["go-module"].report.id_policy is None
    assert deepswe_test_plan("go", tmp_path).runner == "go"
    assert deepswe_test_command("helm-go", ("./pkg/chart/v2/util",)).argv[4:] == ("./pkg/chart/v2/util",)
