import importlib
from pathlib import Path

from agentless_ml.schemas import TestCaseResult, TestCaseStatus


def module(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / 'tools'))
    return importlib.import_module('run_ansible_boolean_smoke')


def test_command_preserves_public_runner_and_disables_installs(monkeypatch):
    m = module(monkeypatch)
    command = m.smoke_command()
    assert command.timeout_seconds == 180
    assert 'python3 bin/ansible-test units ' + m.TEST in command.argv[2]
    assert '--python 3.11 --num-workers 1 --requirements-mode skip --local' in command.argv[2]
    assert 'pip install' not in command.argv[2]
    assert 'PYTHONPATH=/tmp/work/lib:/tmp/work/test/lib' in command.argv[2]
    assert command.report.path == m.REPORT


def test_exact_six_passes_required(monkeypatch):
    m = module(monkeypatch)
    cases = tuple(TestCaseResult(name, TestCaseStatus.PASSED) for name in sorted(m.EXPECTED))
    assert m.verify_cases(cases)
    assert not m.verify_cases(cases[:-1])
    assert not m.verify_cases(cases + cases[:1])
    assert not m.verify_cases((TestCaseResult(cases[0].test_id, TestCaseStatus.SKIPPED),) + cases[1:])
    assert not m.verify_cases((TestCaseResult('unexpected', TestCaseStatus.PASSED),) + cases[1:])
