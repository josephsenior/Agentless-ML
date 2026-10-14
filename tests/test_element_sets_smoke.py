import importlib
from pathlib import Path


def module(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / 'tools'))
    return importlib.import_module('run_element_sets_smoke')


def test_selected_command_keeps_public_setup_and_bounds_execution(monkeypatch):
    m = module(monkeypatch)
    command = m.smoke_command()
    assert command.timeout_seconds == 180
    assert 'yarn test --runInBand --runTestsByPath ' + m.TEST in command.argv[2]
    assert '--config' not in command.argv[2]
    assert 'yarn install' not in command.argv[2]
    assert '--json' in command.argv[2] and '--cacheDirectory=/tmp/' in command.argv[2]


def test_report_requires_exact_five_passes_and_no_setup_errors(monkeypatch):
    m = module(monkeypatch)
    cases = [dict(fullName=name, status='passed') for name in m.EXPECTED]
    report = dict(success=True, numTotalTests=5, numPassedTests=5, numFailedTests=0,
                  numPendingTests=0, numRuntimeErrorTestSuites=0,
                  testResults=[dict(name='/tmp/work/' + m.TEST, assertionResults=cases)])
    assert m.verify_report(report)
    assert not m.verify_report({**report, 'numRuntimeErrorTestSuites': 1})
    assert not m.verify_report({**report, 'testResults': []})
    cases[0]['status'] = 'pending'
    assert not m.verify_report(report)
