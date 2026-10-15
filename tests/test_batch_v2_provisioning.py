import importlib
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture
def module(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / 'tools'))
    return importlib.import_module('batch_v2_provisioning')


def task(name, repo, language='python'):
    return SimpleNamespace(instance_id=name, repository_url=repo, language=language,
                           container_image='image:' + name, base_commit='a' * 40)


def test_pilot_excludes_parked_repo_and_balances_repositories(module):
    tasks = [task('park', 'https://github.com/NodeBB/NodeBB.git'),
             task('a', 'repo-a'), task('b', 'repo-a'), task('c', 'repo-c', 'go')]
    selected = module.choose_pilot(tasks, {'image:b': 'sha'}, {'b': {}}, 5)
    assert {t.instance_id for t in selected} == {'b', 'c'}


@pytest.mark.parametrize('size', [0, 12])
def test_pilot_size_is_bounded(module, size):
    with pytest.raises(ValueError):
        module.choose_pilot([], {}, {}, size)


def test_missing_image_does_not_execute_or_claim_readiness(module, tmp_path):
    result = module.pilot_task(task('a', 'repo'), {}, {}, tmp_path, tmp_path)
    assert result['status'] == 'needs_local_image'
    assert not result['public_check_executed'] and not result['full_suite_ready']


def test_probe_does_not_run_package_scripts_or_tests(module):
    command = module.workspace_probe_command(task('a', 'repo'))
    assert command.timeout_seconds == 120
    assert 'archive --format=tar' in command.argv[2]
    assert 'mktemp' in command.argv[2]
    assert 'npm' not in command.argv[2] and 'pytest' not in command.argv[2]


def test_workspace_only_never_runs_reviewed_smoke(module, monkeypatch, tmp_path):
    from dataclasses import dataclass

    @dataclass
    class Status:
        value: str = 'pass'

    @dataclass
    class Result:
        status: Status

    @dataclass
    class Execution:
        result: Result

    class Runner:
        def __init__(self, *args, **kwargs):
            pass

        def run(self, *args):
            return Execution(Result(Status()))

    monkeypatch.setattr(module, 'DockerTestRunner', Runner)
    monkeypatch.setattr(module, 'survey_task', lambda *a, **kw: pytest.fail('smoke must not run'))
    selected = task('a', 'repo')
    selected.memory_megabytes = 4096
    record = module.pilot_task(selected, {'image:a': 'sha'},
                               {'a': {'image_id': 'sha', 'scope': 'selected_public_test'}},
                               tmp_path, tmp_path, workspace_only=True)
    assert record['status'] == 'workspace_probe_passed'
    assert not record['public_check_executed'] and not record['full_suite_ready']
