"""A normal Mocha end event does not prove that bail ran the entire suite."""
import importlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture
def module(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / 'tools'))
    return importlib.import_module('v2_nodebb_public')


def evidence(names=('first', 'second'), ended=None, failed=(), hooks=(), aborted=False):
    ended = list(names) if ended is None else list(ended)
    key = lambda name: json.dumps(['/tmp/work/test/a.js', name], separators=(',', ':'))
    audit = dict(schema_version=1, run_started=True, run_ended=True, aborted=aborted,
                 runner_total=len(names), planned=[key(n) for n in names],
                 ended=[key(n) for n in ended], stats_tests=len(ended), hook_failures=list(hooks))
    report = dict(stats={'tests': len(ended)}, pending=[], passes=[], failures=[])
    for name in ended:
        report['failures' if name in failed else 'passes'].append(
            dict(file='/tmp/work/test/a.js', fullTitle=name))
    return audit, report


def assess(module, audit, report):
    return module.audit_completion(json.dumps(audit).encode(), json.dumps(report).encode())


def test_complete_pass_and_complete_failure_both_preserve_coverage(module):
    assert assess(module, *evidence())['complete']
    assert assess(module, *evidence(failed=('second',)))['complete']


def test_bail_with_normal_end_is_incomplete(module):
    audit, report = evidence(ended=['first'], failed=['first'])
    result = assess(module, audit, report)
    assert not result['complete'] and result['ended_tests'] == 1
    assert len(result['missing_tests']) == 1


@pytest.mark.parametrize('change', ['hook', 'abort', 'duplicate', 'missing_report', 'count', 'no_end'])
def test_hook_abort_and_conflicting_evidence_cannot_be_ready(module, change):
    audit, report = evidence()
    if change == 'hook':
        audit['hook_failures'] = [{'key': 'before all', 'message': 'setup failed'}]
    elif change == 'abort':
        audit['aborted'] = True
    elif change == 'duplicate':
        audit['planned'].append(audit['planned'][0])
    elif change == 'missing_report':
        report['passes'].pop()
    elif change == 'count':
        report['stats']['tests'] += 1
    else:
        audit['run_ended'] = False
    assert not assess(module, audit, report)['complete']


def test_pending_tests_count_as_completed_evidence(module):
    audit, report = evidence()
    report['pending'].append(report['passes'].pop())
    assert assess(module, audit, report)['complete']


@pytest.mark.parametrize('audit,report', [(None, None), (b'{}', b'{}'), (b'{', b'{}')])
def test_missing_or_malformed_evidence_fails_closed(module, audit, report):
    assert not module.audit_completion(audit, report)['complete']


def test_runner_retains_completion_even_when_individual_report_missing(module, monkeypatch, tmp_path):
    audit, _ = evidence(ended=[])
    raw = json.dumps(audit).encode()
    runner = object.__new__(module.NodeBBPublicSuiteRunner)
    monkeypatch.setattr(module.DockerTestRunner, '_docker', lambda *a, **kw: None)
    monkeypatch.setattr(runner, '_read_file', lambda name, path, limit:
                        raw if path.endswith('completion.json') else None)
    def execute(self, source, command):
        self._docker('inspect', 'owned-container')
        return SimpleNamespace(artifact_directory=str(tmp_path))
    monkeypatch.setattr(module.DockerTestRunner, 'run', execute)
    runner.run(tmp_path, module.public_command(1800))
    assert (tmp_path / 'mocha-completion.json').read_bytes() == raw
    assert not runner.completion_audit['complete']
