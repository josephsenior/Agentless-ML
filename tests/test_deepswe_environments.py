"""Registration contracts only; no Docker, network or hidden benchmark files."""

import copy
import json
import sys
import shutil
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import pytest

from agentless_ml.adapters.benchmarks.deepswe_execution import MOCHA, DENO
from agentless_ml.schemas import Benchmark, TaskSpec

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import deepswe_environments as runtime
import run_testem_qunit_public_test as verified
sys.path.pop(0)


def published():
    entry = runtime.load_environments()[runtime.TASK]
    return TaskSpec(benchmark=Benchmark.DEEPSWE, benchmark_revision='test',
        instance_id=runtime.TASK, language='javascript', repository_url='https://example.test/repo',
        base_commit=entry['base_commit'], problem_statement='Public task',
        container_image='published:test', container_digest=entry['published_image_id'])


def test_registration_preserves_published_pins_and_uses_verified_image():
    task = published()
    entries = runtime.load_environments()
    environment = runtime.environment_for(task, entries)
    selected = runtime.runtime_task(task, environment)
    assert task.container_digest == environment['published_image_id']
    assert selected.container_image == selected.container_digest == environment['image_id']
    assert selected.base_commit == task.base_commit
    assert environment['condition'].startswith('modified environment:')
    pin = json.loads((ROOT / 'experiments/deepswe/corpus_pin.json').read_text())
    assert pin['container_digests'][task.instance_id] == task.container_digest
    for changed in (replace(task, base_commit='a' * 40), replace(task, container_digest='sha256:' + 'a' * 64)):
        with pytest.raises(ValueError, match='published task pins'):
            runtime.environment_for(changed, entries)


def test_unregistered_tasks_are_unchanged():
    task = replace(published(), instance_id='another-task')
    assert runtime.environment_for(task, runtime.load_environments()) is None
    assert runtime.runtime_task(task, None) is task
    command = MOCHA.command(('tests/*.js',))
    assert runtime.runtime_command(command, None) is command


def test_registered_full_command_is_identical_to_verified_full_command():
    environment = runtime.load_environments()[runtime.TASK]
    command = MOCHA.command(('tests/*_tests.js', 'tests/**/*_tests.js'), timeout_seconds=1800)
    wrapped = runtime.runtime_command(command, environment)
    assert wrapped == verified.selected_command(full=True)
    assert wrapped.report == command.report
    assert wrapped.failure_exit_codes == command.failure_exit_codes
    assert 125 not in wrapped.failure_exit_codes
    assert '--grep' not in wrapped.argv[2] and '--require' not in wrapped.argv[2]
    assert 'firefox-observer' not in wrapped.argv[2]
    compile(wrapped.argv[2], '<registered-full>', 'exec')


@pytest.mark.parametrize('change', ['profile', 'field', 'image', 'base', 'verification', 'reason', 'task'])
def test_invalid_registrations_fail_closed(tmp_path, change):
    entries = {runtime.TASK: copy.deepcopy(runtime.load_environments()[runtime.TASK])}
    entry = entries[runtime.TASK]
    if change == 'profile': entry['profile'] = 'arbitrary-shell'
    elif change == 'field': entry['network'] = 'host'
    elif change == 'image': entry['image'] = 'mutable:tag'
    elif change == 'base': entry['base_commit'] = 'short'
    elif change == 'verification': entry['verification'] = '../outside.json'
    elif change == 'reason': entry['reason'] = ''
    elif change == 'task': entries['other'] = entries.pop(runtime.TASK)
    registry = tmp_path / 'environments.json'
    registry.write_text(json.dumps(entries))
    with pytest.raises(ValueError): runtime.load_environments(registry)


@pytest.mark.parametrize('field,value', [('status', 'fail'), ('exit_code', 1),
    ('full_suite_run', False), ('image_id', 'sha256:' + '0' * 64),
    ('public_test_filter', 'narrow'), ('public_test_source_modified', True),
    ('diagnostic_prototype_observer', True)])
def test_registration_requires_full_passing_evidence(tmp_path, field, value):
    entries = {runtime.TASK: runtime.load_environments()[runtime.TASK]}
    entry = entries[runtime.TASK]
    evidence = json.loads((runtime.REGISTRY.parent / entry['verification']).read_text())
    evidence['result'][field] = value
    (tmp_path / entry['verification']).write_text(json.dumps(evidence))
    registry = tmp_path / 'environments.json'
    registry.write_text(json.dumps(entries))
    with pytest.raises(ValueError, match='passing unchanged full schedule'):
        runtime.load_environments(registry)


def test_registered_runner_keeps_limits_and_refuses_image_mismatch(tmp_path):
    environment = runtime.load_environments()[runtime.TASK]
    limits = dict(memory_mb=8192, cpus=2, tmpfs_mb=4096, pids_limit=2048, run_as_image_user=True)
    with patch.object(runtime, 'OfflineAssetRunner') as factory:
        factory.return_value.image_id = environment['image_id']
        assert runtime.runtime_runner(environment['image'], tmp_path, environment, **limits) is factory.return_value
        factory.assert_called_once_with(environment['image'], tmp_path, **limits)
        factory.return_value.image_id = 'sha256:' + '0' * 64
        with pytest.raises(ValueError, match='immutable ID'):
            runtime.runtime_runner(environment['image'], tmp_path, environment, **limits)


def test_cliffy_registration_is_image_only_and_preserves_deno_command(tmp_path):
    entry = runtime.load_environments()[runtime.CLIFFY]
    task = replace(published(), instance_id=runtime.CLIFFY, base_commit=entry['base_commit'],
                   container_digest=entry['published_image_id'], language='typescript')
    assert runtime.environment_for(task, runtime.load_environments()) == entry
    assert runtime.runtime_task(task, entry).container_digest == entry['image_id']
    pin = json.loads((ROOT / 'experiments/deepswe/corpus_pin.json').read_text())
    assert pin['container_digests'][runtime.CLIFFY] == task.container_digest
    command = DENO.command((), timeout_seconds=1800)
    assert runtime.runtime_command(command, entry) is command
    assert '--cached-only' in command.argv[2] and '--no-run' not in command.argv[2]
    assert 'offline-qunit' not in command.argv[2]
    with patch.object(runtime, 'RegisteredImageRunner') as image_runner, \
            patch.object(runtime, 'OfflineAssetRunner') as service_runner:
        image_runner.return_value.image_id = entry['image_id']
        runtime.runtime_runner(entry['image'], tmp_path, entry, memory_mb=8192)
        image_runner.assert_called_once_with(entry['image'], tmp_path, memory_mb=8192)
        service_runner.assert_not_called()


def test_image_only_runner_observes_without_changing_docker_arguments():
    with patch.object(runtime.DockerTestRunner, '_docker') as docker:
        runner = object.__new__(runtime.RegisteredImageRunner)
        runner._docker('create', '--network=none', '--cap-drop=ALL')
        assert docker.call_args.args == ('create', '--network=none', '--cap-drop=ALL')


@pytest.mark.parametrize('change', ['status', 'image', 'parent', 'manifest', 'graph'])
def test_cliffy_registration_refuses_mismatched_evidence(tmp_path, change):
    entry = runtime.load_environments()[runtime.CLIFFY]
    original = runtime.REGISTRY.parent
    for name in (entry['verification'], 'cliffy_offline_graph_2026_10_09.json'):
        shutil.copyfile(original / name, tmp_path / name)
    (tmp_path / 'cliffy').mkdir()
    shutil.copyfile(original / 'cliffy/public_dependencies_2026_10_09.json',
                    tmp_path / 'cliffy/public_dependencies_2026_10_09.json')
    evidence_path = tmp_path / entry['verification']
    graph_path = tmp_path / 'cliffy_offline_graph_2026_10_09.json'
    evidence = json.loads(evidence_path.read_text())
    graph = json.loads(graph_path.read_text())
    if change == 'status': evidence['status'] = 'fail'
    elif change == 'image': evidence['image_id'] = 'sha256:' + '0' * 64
    elif change == 'parent': graph['parent_image_id'] = 'sha256:' + '0' * 64
    elif change == 'manifest': graph['manifest_sha256_at_build'] = '0' * 64
    elif change == 'graph': graph['compile_time_import_graph_verified'] = False
    evidence_path.write_text(json.dumps(evidence))
    graph_path.write_text(json.dumps(graph))
    registry = tmp_path / 'environments.json'
    registry.write_text(json.dumps({runtime.CLIFFY: entry}))
    with pytest.raises(ValueError, match='Cliffy registration requires'):
        runtime.load_environments(registry)
