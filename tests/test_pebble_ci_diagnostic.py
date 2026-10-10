import json
from pathlib import Path
from types import SimpleNamespace

from agentless_ml.adapters.benchmarks import deepswe_test_plan
from agentless_ml.schemas import TestCaseResult, TestCaseStatus, ValidationStatus


def load(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "tools"))
    import run_pebble_ci_diagnostic
    return run_pebble_ci_diagnostic


def test_ci_full_command_only_adds_environment(monkeypatch, tmp_path):
    diagnostic = load(monkeypatch)
    plan = deepswe_test_plan("go", tmp_path)
    command = diagnostic.ci_command(plan)
    original = diagnostic.diagnostic_command(plan)
    assert command.argv[:2] == ("env", "CI=1")
    assert command.argv[2:] == original.argv
    assert command.report == original.report
    assert command.argv[-1] == "./..."
    assert "-run" not in command.argv
    assert command.timeout_seconds == 1800


def test_verification_selects_exact_three_tests_and_retains_report(monkeypatch, tmp_path):
    diagnostic = load(monkeypatch)
    plan = deepswe_test_plan("go", tmp_path)
    command = diagnostic.ci_command(plan, verify_only=True)
    assert command.argv[-3:] == (
        "-run", "^(" + "|".join(diagnostic.SKIP_NAMES) + ")$", "./sstable/rowblk",
    )
    assert command.report == plan.command().report


def test_gate_requires_three_skips_and_original_memory_reasons(monkeypatch):
    diagnostic = load(monkeypatch)
    cases = tuple(TestCaseResult(diagnostic.PACKAGE + "::" + name, TestCaseStatus.SKIPPED)
                  for name in diagnostic.SKIP_NAMES)
    result = SimpleNamespace(status=ValidationStatus.PASS, exit_code=0, test_cases=cases)
    execution = SimpleNamespace(result=result)
    tail = b"\n".join(json.dumps({
        "Package": diagnostic.PACKAGE, "Test": name,
        "Output": "Skipping test: requires too much memory for CI now.",
    }).encode() for name in diagnostic.SKIP_NAMES)
    assert diagnostic.verified_skips(execution, tail)
    assert not diagnostic.verified_skips(execution, b"")
    result.test_cases = cases[:-1]
    assert not diagnostic.verified_skips(execution, tail)
    result.test_cases = cases[:2] + (TestCaseResult(cases[2].test_id, TestCaseStatus.PASSED),)
    assert not diagnostic.verified_skips(execution, tail)


def test_failed_gate_never_starts_full_schedule(monkeypatch):
    diagnostic = load(monkeypatch)
    phases = []
    monkeypatch.setattr(diagnostic, "verify_sealed_repository", lambda *args: None)
    monkeypatch.setattr(diagnostic, "run_phase", lambda repository, phase: phases.append(phase) or False)
    assert diagnostic.main() == 1
    assert phases == ["verify-skips"]
