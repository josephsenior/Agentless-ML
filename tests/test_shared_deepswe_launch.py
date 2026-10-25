import json

import pytest

from agentless_ml.shared_task import canonical, digest, load_shared_task, preflight_manifest
from test_shared_deepswe_specs import inputs as input_fixture, build
from test_local_workspace import git
import run_shared_deepswe_workflow as launcher

inputs = input_fixture


@pytest.fixture
def bundle(inputs):
    record, native = build(inputs)
    directory = inputs[-1]
    repo = directory / 'repo'
    repo.mkdir()
    git(repo, 'init')
    (repo / 'a.py').write_bytes(b'x = 1\n')
    (repo / '.gitignore').write_bytes(b'ignored.cache\n')
    git(repo, 'add', '.')
    git(repo, 'commit', '-m', 'base')
    record['identity']['base_commit'] = git(repo, 'rev-parse', 'HEAD').decode().strip()
    record['identity']['source_snapshot'] = {
        'git_tree': git(repo, 'rev-parse', 'HEAD^{tree}').decode().strip(),
        'tree_listing_sha256': digest(git(repo, 'ls-tree', '-rz', '--full-tree', 'HEAD'))}
    record.pop('spec_sha256')
    record['spec_sha256'] = digest(canonical(record))
    path = directory / 'task.json'
    path.write_bytes(canonical(record))
    (directory / 'baseline-report.json').write_bytes(native)
    return path, repo


def test_preflight_uses_exact_text_and_keeps_model_unresolved(bundle):
    path, repo = bundle
    record = load_shared_task(path)
    result = preflight_manifest(record, repo, 'agentless-ml', 'test')
    assert result['starting_conditions']['problem']['text'] == 'Fix the public issue'
    assert result['workspace_verified'] is True
    assert result['model'] is None
    assert result['launch_authorized'] is False
    assert result['container_observed'] is False


@pytest.mark.parametrize('change', ['tracked', 'untracked', 'ignored', 'commit'])
def test_changed_starting_checkout_is_rejected(bundle, change):
    path, repo = bundle
    name = {'tracked': 'a.py', 'untracked': 'extra.py', 'ignored': 'ignored.cache', 'commit': 'a.py'}[change]
    (repo / name).write_bytes(b'changed\n')
    if change == 'commit':
        git(repo, 'add', '.')
        git(repo, 'commit', '-m', 'changed')
    with pytest.raises(ValueError, match='clean|commit mismatch'):
        preflight_manifest(load_shared_task(path), repo, 'test', 'test')


def test_corrupted_record_is_rejected(bundle):
    path, _ = bundle
    record = json.loads(path.read_bytes())
    record['problem']['text'] = 'different task'
    path.write_bytes(canonical(record))
    with pytest.raises(ValueError, match='hash mismatch'):
        load_shared_task(path)


@pytest.mark.parametrize('key,value', [('read_only_root', False), ('extra_hosts', {'example.com': '127.0.0.1'})])
def test_launcher_rejects_environment_fields_it_would_not_apply(inputs, monkeypatch, key, value):
    record, _ = build(inputs)
    record['environment'][key] = value
    with pytest.raises(ValueError, match='settings|hostname'):
        launcher.resolve(record)


def test_launcher_resolves_command_and_task_from_record(inputs, monkeypatch):
    record, _ = build(inputs)
    directory = inputs[-1]
    (directory / 'fixture.py').write_bytes(b'# setup\n')
    record['environment']['setup']['setup_source_hashes'] = {'fixture.py': digest(b'# setup\n')}
    monkeypatch.setattr(launcher, 'ROOT', directory)
    task, registration, command = launcher.resolve(record)
    assert task.problem_statement == record['problem']['text']
    assert task.base_commit == record['identity']['base_commit']
    assert registration is None
    assert canonical(command.argv) == canonical(record['public_validation']['command']['argv'])
    (directory / 'fixture.py').write_bytes(b'# changed\n')
    with pytest.raises(ValueError, match='setup code changed'):
        launcher.resolve(record)
