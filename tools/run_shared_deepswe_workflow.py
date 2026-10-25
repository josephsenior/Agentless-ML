"""Consume a shared DeepSWE record for preflight or a recorded Agentless run.

No model integration. A recorded run establishes a fresh public baseline; it
does not silently reuse historical reports with a different command.
"""

import argparse
import json
from dataclasses import asdict, replace
from pathlib import Path

from agentless_ml.adapters.benchmarks import deepswe_test_command
from agentless_ml.schemas import Benchmark, TaskSpec
from agentless_ml.shared_task import load_shared_task, preflight_manifest, canonical, digest
from agentless_ml.validation import RegressionTest
from agentless_ml.workflow import FixedWorkflowController
from agentless_ml.workspace import LocalGitWorkspaceProvider
from deepswe_environments import environment_for, load_environments, runtime_command, runtime_runner
from deepswe_environments import HELM_IMAGES, HELM_BASE, HELM_SETUP
from run_deepswe_workflow import _responses, _revision

ROOT = Path(__file__).resolve().parents[1]


def resolve(record):
    identity, environment = record['identity'], record['environment']
    supported = {'read_only_root': True, 'cap_drop': ['ALL'], 'no_new_privileges': True,
        'writable_paths': ['/tmp'], 'source_directory': '/tmp/work',
        'exec_working_directory': '/tmp', 'environment_variables': {'PYTHONDONTWRITEBYTECODE': '1'}}
    if any(environment.get(key) != value for key, value in supported.items()):
        raise ValueError('shared environment requests settings this launcher does not implement')
    if environment['network']['agent_and_candidate_validation'] != 'none':
        raise ValueError('shared candidate validation must remain offline')
    if environment['user']['run_as_image_user'] is not True:
        raise ValueError('shared launcher requires the pinned image user')
    if environment['limits']['timeout_seconds'] != record['timing']['public_command_timeout_seconds']:
        raise ValueError('shared public timeout fields disagree')
    published = TaskSpec(benchmark=Benchmark.DEEPSWE,
        benchmark_revision=identity['benchmark_revision'], instance_id=identity['task_id'],
        language=identity['language'], repository_url=identity['repository_url'],
        base_commit=identity['base_commit'], problem_statement=record['problem']['text'],
        container_image=environment['published_image'],
        container_digest=environment['published_image_id'],
        timeout_seconds=record['timing']['published_agent_timeout_seconds'],
        memory_megabytes=environment['limits']['memory_mb'])
    registration = environment_for(published, load_environments())
    if registration != environment['setup']['registration']:
        raise ValueError('shared environment registration differs from the reviewed registry')
    expected_image = registration['image_id'] if registration else published.container_digest
    if environment['effective_image_id'] != expected_image:
        raise ValueError('shared effective image differs from the reviewed image')
    profile = registration['profile'] if registration else 'published-image'
    if published.instance_id in HELM_IMAGES:
        if published.base_commit != HELM_BASE or published.container_digest != HELM_IMAGES[published.instance_id]:
            raise ValueError('shared Helm fixture pins differ')
        expected_profile, expected_setup = 'helm-container-fixtures-v1', HELM_SETUP
    else:
        expected_profile, expected_setup = profile, None
    if (environment['setup']['profile'] != expected_profile
            or environment['setup']['container_setup'] != expected_setup):
        raise ValueError('shared container setup differs from the supported profile')
    hosts = ({'code.jquery.com': '127.0.0.1'} if profile == 'testem-offline-qunit-v1'
             else {name: '127.0.0.1' for name in ('pypi.org', 'httpbingo.org', 'google.com')}
             if profile == 'pwntools-protocol-services-v1' else {})
    if environment['extra_hosts'] != hosts:
        raise ValueError('shared hostname setup differs from its registered profile')
    for name, expected in environment['setup']['setup_source_hashes'].items():
        path = (ROOT / name).resolve()
        if not path.is_relative_to(ROOT) or digest(path.read_bytes()) != expected:
            raise ValueError(f'shared setup code changed: {name}; review and re-export')
    validation = record['public_validation']
    command = runtime_command(deepswe_test_command(validation['runner'], tuple(validation['targets']),
        timeout_seconds=record['timing']['public_command_timeout_seconds']), registration)
    if canonical(asdict(command)) != canonical(validation['command']):
        raise ValueError('shared public command differs from the reviewed command builder')
    return published, registration, command


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--shared-task', type=Path, required=True)
    parser.add_argument('--source-repository', type=Path, required=True)
    parser.add_argument('--workspace-root', type=Path, required=True)
    parser.add_argument('--artifact-root', type=Path, required=True)
    parser.add_argument('--inspect-start', action='store_true')
    parser.add_argument('--experiment', type=Path, help='Recorded response directory, never a model provider')
    args = parser.parse_args(argv)
    record = load_shared_task(args.shared_task)
    published, registration, command = resolve(record)
    provider = LocalGitWorkspaceProvider(args.source_repository, published.base_commit, args.workspace_root)
    with provider.create() as checkout:
        manifest = preflight_manifest(record, checkout.path, 'agentless-ml', _revision())
    if args.inspect_start:
        print(json.dumps(manifest, indent=2, sort_keys=True))
        return 0
    if args.experiment is None:
        parser.error('--experiment is required for a recorded run')
    experiment = json.loads((args.experiment / 'experiment.json').read_bytes())
    if experiment['task_id'] != published.instance_id:
        raise ValueError('recorded responses belong to another task')
    if experiment.get('suite'):
        raise ValueError('shared runs cannot override the shared public schedule')
    environment = record['environment']
    limits = environment['limits']
    runner = runtime_runner(environment['effective_image_id'], args.artifact_root / 'executions',
        registration, task=published, memory_mb=limits['memory_mb'], cpus=limits['cpus'],
        pids_limit=limits['pids_limit'], tmpfs_mb=limits['scratch_mb'] or 4096,
        scratch_mode=limits['scratch_mode'], swap_policy=limits['swap_policy'], run_as_image_user=True)
    if runner.image_id != environment['effective_image_id'] or runner.user != environment['user']['user']:
        raise ValueError('observed image or user differs from the shared record')
    task = replace(published, container_image=runner.image_id, container_digest=runner.image_id)
    result = FixedWorkflowController(task=task, source_repository=args.source_repository,
        workspace_root=args.workspace_root, artifact_root=args.artifact_root, runner=runner,
        public_commands=(), regression_tests=(RegressionTest('suite', command),),
        implementation_revision=_revision(), harness_revision=task.benchmark_revision,
        model_name='recorded/manual-v1').run(_responses(args.experiment))
    (Path(result.artifact_directory) / 'shared-start.json').write_bytes(canonical(manifest))
    print(json.dumps({'artifacts': result.artifact_directory, 'spec_sha256': record['spec_sha256']}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
