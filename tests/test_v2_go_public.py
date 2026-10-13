"""Complete package coverage is separate from individual passing evidence."""
import json
from pathlib import Path

import pytest


@pytest.fixture
def module(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / 'tools'))
    import v2_go_public
    return v2_go_public


def events(*rows):
    return ('\n'.join(json.dumps(row) for row in rows) + '\n').encode()


def test_complete_mixed_baseline_and_package_without_tests(module):
    result = module.audit_packages(b'example/a\nexample/b\n', events(
        dict(Action='run', Package='example/a', Test='TestBad'),
        dict(Action='fail', Package='example/a', Test='TestBad'),
        dict(Action='fail', Package='example/a'),
        dict(Action='skip', Package='example/b')))
    assert result['complete']
    assert result['terminal_packages'] == 2


@pytest.mark.parametrize('rows,field', [
    ([dict(Action='pass', Package='example/a')], 'missing_packages'),
    ([dict(Action='pass', Package='example/a'), dict(Action='fail', Package='example/b')],
     'failed_packages_without_test_failure'),
    ([dict(Action='run', Package='example/a', Test='TestInterrupted'),
      dict(Action='pass', Package='example/a'), dict(Action='skip', Package='example/b')],
     'unfinished_tests'),
    ([dict(Action='pass', Package='example/a'), dict(Action='pass', Package='example/b'),
      dict(Action='pass', Package='unexpected')], 'unexpected_packages'),
])
def test_partial_or_build_failure_cannot_be_ready(module, rows, field):
    result = module.audit_packages(b'example/a\nexample/b\n', events(*rows))
    assert not result['complete'] and result[field]


@pytest.mark.parametrize('packages,raw', [
    (None, b''), (b'', b''), (b'x\nx\n', b''), (b'x\n', b'{'),
    (b'x\n', b'[]\n'), (b'x\n', b'\xff'),
])
def test_invalid_evidence_is_incomplete(module, packages, raw):
    assert not module.audit_packages(packages, raw)['complete']


def test_command_keeps_public_target_and_reports_offline(module):
    command = module.public_command(1800)
    assert command.argv[-1] == './...'
    assert 'go test -json -count=1 -cover -v "$@"' in command.argv[2]
    assert 'go list ./...' in command.argv[2]
    assert 'GO111MODULE=on GOPROXY=off' in command.argv[2]
    assert command.report.path == '/tmp/ctrf.json'
    assert command.timeout_seconds == 1800


def test_reviewed_manifest_is_full_target(module):
    import survey_swe_bench_pro_v2 as survey
    plans = survey.load_plans(survey.EXPERIMENTS / 'v2_full_public_plans.json')
    assert len(plans) == 1
    plan = next(iter(plans.values()))
    assert plan['scope'] == 'full_public_suite'
    assert plan['runner_kind'] == 'go-public-suite-v1'
    assert plan['command'].argv[-1] == './...'


def test_duplicate_terminal_and_oversized_capture_are_rejected(module, monkeypatch):
    raw = events(dict(Action='pass', Package='x'), dict(Action='pass', Package='x'))
    assert not module.audit_packages(b'x\n', raw)['complete']
    monkeypatch.setattr(module, 'LIMIT', 2)
    assert not module.audit_packages(b'x\n', raw)['complete']


def test_runner_retains_raw_events_and_audit_before_cleanup(module, monkeypatch, tmp_path):
    from types import SimpleNamespace
    raw = events(dict(Action='pass', Package='example'))
    captured = {'/tmp/go-packages.txt': b'example\n', '/tmp/go-test.json': raw}
    runner = object.__new__(module.GoPublicSuiteRunner)
    monkeypatch.setattr(module.DockerTestRunner, '_docker', lambda *a, **kw: None)
    monkeypatch.setattr(runner, '_read_file', lambda name, path, limit: captured[path])
    def execute(self, source, command):
        self._docker('inspect', 'owned-container')
        return SimpleNamespace(artifact_directory=str(tmp_path))
    monkeypatch.setattr(module.DockerTestRunner, 'run', execute)
    runner.run(tmp_path, module.public_command(1800))
    assert (tmp_path / 'go-events.jsonl').read_bytes() == raw
    assert json.loads((tmp_path / 'package-audit.json').read_text())['complete']
