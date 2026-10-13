"""Provisioning evidence must not turn a syntax smoke into test-suite readiness."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture
def survey(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / 'tools'))
    import survey_swe_bench_pro_v2
    return survey_swe_bench_pro_v2


def result(status, cases=()):
    return SimpleNamespace(status=SimpleNamespace(value=status),
                           test_cases=[SimpleNamespace(status=SimpleNamespace(value=s)) for s in cases])


def test_scope_and_outcomes_are_not_conflated(survey):
    assert survey.readiness_status('syntax_only', result('pass')) == 'smoke_checked'
    assert survey.readiness_status('selected_public_test', result('pass', ['passed'])) == 'smoke_checked'
    assert survey.readiness_status('full_public_suite', result('pass')) == 'no_passing_tests'
    assert survey.readiness_status('full_public_suite', result('fail', ['passed', 'failed'])) == 'public_suite_ready'
    assert survey.readiness_status('full_public_suite', result('timeout', ['passed'])) == 'timeout'


def test_existing_plans_reuse_four_reviewed_specs(survey):
    plans = survey.load_plans(survey.MANIFEST)
    assert len(plans) == 4
    assert {p['scope'] for p in plans.values()} == {'syntax_only', 'selected_public_test'}
    assert all(p['command'].report is None for p in plans.values())


def test_full_suite_label_requires_test_report(survey, tmp_path):
    data = json.loads(survey.MANIFEST.read_bytes())
    data['plans'][0]['scope'] = 'full_public_suite'
    path = tmp_path / 'plans.json'
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='individual test results'):
        survey.load_plans(path)


def test_duplicate_task_is_rejected(survey, tmp_path):
    data = json.loads(survey.MANIFEST.read_bytes())
    data['plans'].append(data['plans'][0])
    path = tmp_path / 'plans.json'
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='duplicate'):
        survey.load_plans(path)


def test_engine_block_does_not_touch_repo_or_claim_checks(survey, tmp_path, monkeypatch):
    task_id, plan = next(iter(survey.load_plans(survey.MANIFEST).items()))
    task = SimpleNamespace(instance_id=task_id, language='python', base_commit=plan['base_commit'])
    def unexpected(*args, **kwargs):
        raise AssertionError('Docker or repository access after known engine failure')
    monkeypatch.setattr(survey, 'DockerTestRunner', unexpected)
    monkeypatch.setattr(survey, 'verify_sealed_repository', unexpected)
    record = survey.survey_task(task, plan, selected=True, engine_error='stopped',
                               repositories=tmp_path, workspace_root=tmp_path, artifacts=tmp_path)
    assert record['status'] == 'docker_unavailable'
    assert not any(record[k] for k in ('image_checked', 'workspace_checked', 'public_check_executed'))


def test_image_mismatch_stops_before_workspace(survey, tmp_path, monkeypatch):
    task_id, plan = next(iter(survey.load_plans(survey.MANIFEST).items()))
    task = SimpleNamespace(instance_id=task_id, language='python', base_commit=plan['base_commit'], memory_megabytes=4096)
    monkeypatch.setattr(survey, 'DockerTestRunner', lambda *a, **kw: SimpleNamespace(image_id='wrong'))
    record = survey.survey_task(task, plan, selected=True, engine_error=None,
                               repositories=tmp_path, workspace_root=tmp_path, artifacts=tmp_path)
    assert record['status'] == 'image_blocked'
    assert not record['workspace_checked'] and not record['public_check_executed']


def test_probe_removes_owned_container_after_timeout(survey, monkeypatch):
    import subprocess
    calls = []
    def run(command, **kwargs):
        calls.append(command)
        if command[1] == 'run':
            raise subprocess.TimeoutExpired(command, 60)
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(survey.subprocess, 'run', run)
    with pytest.raises(subprocess.TimeoutExpired):
        survey.check_image_base('sha256:' + 'a'*64, 'b'*40, 4096)
    assert calls[1] == ['docker', 'rm', '--force', calls[0][calls[0].index('--name')+1]]
    assert '--pull=never' in calls[0]
