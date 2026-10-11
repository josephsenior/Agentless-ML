import json
import subprocess
import sys

import pytest

from agentless_ml.schemas import (
    TestCaseResult, TestCaseStatus, ValidationKind, ValidationResult, ValidationStatus,
)
from agentless_ml.validation import PublicTestCommand, ReproductionSpec
from agentless_ml.validation.reproduction import python_reproduction_command
from agentless_ml.validation.reproduction_evidence import check_reproduction_result
from agentless_ml.validation.reports import ReportFormat, parse_report


def result(status, cases=(), kind=ValidationKind.REPRODUCTION):
    return ValidationResult(
        status, ("trusted-command",), 0, kind=kind,
        test_cases=tuple(TestCaseResult(str(i), TestCaseStatus(s))
                         for i, s in enumerate(cases)),
    )


@pytest.mark.parametrize("status,cases", [
    (ValidationStatus.FAIL, ()),
    (ValidationStatus.PASS, ()),
    (ValidationStatus.FAIL, ("error",)),
    (ValidationStatus.FAIL, ("failed", "error")),
    (ValidationStatus.FAIL, ("failed", "skipped")),
    (ValidationStatus.FAIL, ("passed",)),
    (ValidationStatus.PASS, ("failed",)),
    (ValidationStatus.PASS, ("error",)),
    (ValidationStatus.PASS, ("skipped",)),
    (ValidationStatus.PASS, ("passed", "skipped")),
])
def test_unclean_or_missing_test_evidence_is_not_reproduction(status, cases):
    original = result(status, cases)
    checked = check_reproduction_result(original, report_declared=True)
    assert checked.status is ValidationStatus.HARNESS_ERROR
    assert checked.test_cases == original.test_cases


@pytest.mark.parametrize("status,cases", [
    (ValidationStatus.FAIL, ("failed",)),
    (ValidationStatus.FAIL, ("passed", "failed")),
    (ValidationStatus.PASS, ("passed",)),
])
def test_clean_evidence_retains_real_outcome(status, cases):
    original = result(status, cases)
    assert check_reproduction_result(original, report_declared=True) == original
    assert check_reproduction_result(
        original, report_declared=False,
    ).status is ValidationStatus.HARNESS_ERROR


@pytest.mark.parametrize("status", [
    ValidationStatus.TIMEOUT, ValidationStatus.OUT_OF_MEMORY,
    ValidationStatus.HARNESS_ERROR, ValidationStatus.PATCH_ERROR,
])
def test_infrastructure_statuses_are_never_promoted(status):
    original = result(status, ("failed",))
    assert check_reproduction_result(original, report_declared=True) == original


def test_regression_results_are_unchanged():
    original = result(ValidationStatus.FAIL, ("failed", "error"), ValidationKind.REGRESSION)
    assert check_reproduction_result(original, report_declared=False) == original


def test_exit_only_generated_spec_is_refused():
    with pytest.raises(ValueError, match="structured report"):
        ReproductionSpec("reproduce.py", PublicTestCommand(
            ("python", "reproduce.py"), kind=ValidationKind.REPRODUCTION,
        ))


@pytest.mark.parametrize("source,status,code", [
    ("assert 1 == 2", "failed", 1),
    ("assert 1 == 1", "passed", 0),
    ("import agentless_nonexistent_reproduction_dependency", "error", 2),
    ("raise RuntimeError('setup failed')", "error", 2),
    ("raise SyntaxError('invalid source')", "error", 2),
    ("this is not valid python !", "error", 2),
    ("import sys; sys.exit(0)", "error", 2),
    ("import sys; sys.exit(1)", "error", 2),
])
def test_trusted_python_adapter_classifies_authored_fixtures(tmp_path, source, status, code):
    # Controlled authored fixtures only. Generated source must run in Docker.
    path = tmp_path / "reproduce.py"
    path.write_text(source, encoding="utf-8")
    report = tmp_path / "report.json"
    command = python_reproduction_command("reproduce.py")
    execution = subprocess.run(
        (sys.executable, *command.argv[1:-2], str(path), str(report)),
        cwd=tmp_path, capture_output=True, timeout=10,
    )
    assert execution.returncode == code
    cases = parse_report(report.read_bytes(), ReportFormat.CTRF_JSON)
    assert [case.status.value for case in cases] == [status]


def test_python_adapter_imports_candidate_sibling(tmp_path):
    (tmp_path / "helper.py").write_text("value = 42\n", encoding="utf-8")
    (tmp_path / "reproduce.py").write_text("from helper import value\nassert value == 42\n")
    report = tmp_path / "report.json"
    command = python_reproduction_command("reproduce.py")
    execution = subprocess.run(
        (sys.executable, *command.argv[1:-2], str(tmp_path / "reproduce.py"), str(report)),
        cwd=tmp_path.parent, capture_output=True, timeout=10,
    )
    assert execution.returncode == 0, execution.stderr
    assert json.loads(report.read_text())["results"]["tests"][0]["status"] == "passed"
