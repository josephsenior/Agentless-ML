import importlib
from pathlib import Path

from agentless_ml.schemas import TestCaseResult, TestCaseStatus
from agentless_ml.validation.reports import ReportFormat, parse_report


def module(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / 'tools'))
    return importlib.import_module('run_navidrome_number_smoke')


def test_command_preserves_race_coverage_and_bounds_one_package(monkeypatch):
    m = module(monkeypatch)
    command = m.smoke_command()
    assert command.timeout_seconds == 180
    assert 'go test -race -cover -v -json -count=1 -p 1 -timeout 120s ./utils/number ' in command.argv[2]
    assert '-parallel' not in command.argv[2]  # Ginkgo rejects Go's parallel flag.
    assert '-ginkgo.junit-report=' + m.REPORT in command.argv[2]
    assert 'GOCACHE=/tmp/navidrome-go-build' in command.argv[2]
    assert 'GOPROXY=off GOTOOLCHAIN=local GOMAXPROCS=1 GOFLAGS=-mod=readonly' in command.argv[2]
    assert 'go mod download' not in command.argv[2] and './...' not in command.argv[2]
    assert command.report.path == m.REPORT


def test_exact_six_specs_required_not_single_go_wrapper(monkeypatch):
    m = module(monkeypatch)
    cases = tuple(TestCaseResult(name, TestCaseStatus.PASSED) for name in sorted(m.EXPECTED))
    assert m.verify_cases(cases)
    assert not m.verify_cases(cases[:-1])
    assert not m.verify_cases(cases + cases[:1])
    assert not m.verify_cases((TestCaseResult('TestNumber', TestCaseStatus.PASSED),))
    for status in (TestCaseStatus.SKIPPED, TestCaseStatus.FAILED, TestCaseStatus.ERROR):
        assert not m.verify_cases((TestCaseResult(cases[0].test_id, status),) + cases[1:])


def test_native_ginkgo_junit_maps_to_expected_spec_ids(monkeypatch):
    m = module(monkeypatch)
    xml = '<testsuites><testsuite>' + ''.join(
        '<testcase classname="Number Suite" name="' + name.split('::', 1)[1] + '"/>'
        for name in sorted(m.EXPECTED)) + '</testsuite></testsuites>'
    assert m.verify_cases(parse_report(xml.encode(), ReportFormat.JUNIT_XML))
