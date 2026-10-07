"""Opt-in offline-service diagnostic; never changes canonical validation."""

import argparse
from collections import Counter
import json
from pathlib import Path

from agentless_ml.adapters.benchmarks import deepswe_test_command
from agentless_ml.validation import DockerTestRunner
from agentless_ml.workspace import LocalGitWorkspaceProvider

ROOT = Path(__file__).resolve().parents[1]
HOSTS = ('pypi.org', 'httpbingo.org')


class OfflineServiceRunner(DockerTestRunner):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.user != 'travis':
            raise ValueError('Offline-service diagnostic requires the non-root travis image user')

    @staticmethod
    def _docker(*args, **kwargs):
        if args and args[0] == 'create':
            args = (args[0], *(f'--add-host={host}:127.0.0.1' for host in HOSTS), *args[1:])
        return DockerTestRunner._docker(*args, **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', default='agentless-ml/pwntools-services:2026-10-08')
    parser.add_argument('--artifacts', type=Path, required=True)
    parser.add_argument('--targets', nargs='+', default=['source/update.rst'])
    args = parser.parse_args()
    if any(target not in ('source/update.rst', 'source/util/web.rst') for target in args.targets):
        parser.error('Only the public update and download pages are supported')
    runner = OfflineServiceRunner(args.image, args.artifacts / 'logs', memory_mb=8192,
                                  cpus=2, tmpfs_mb=4096, pids_limit=2048, run_as_image_user=True)
    provider = LocalGitWorkspaceProvider(ROOT.parent / 'benchmarks/deepswe/repos/pwntools-tube-multiplexing',
                                        '76894a5404a65d2800b6d0adaf3485ecba275caa', args.artifacts / 'workspaces')
    with provider.create() as workspace:
        execution = runner.run(workspace.path, deepswe_test_command('pwntools-native-doctest',
                               tuple(args.targets), timeout_seconds=300))
    record = {'condition': 'offline-service diagnostic - modified environment',
              'hosts': {host: '127.0.0.1' for host in HOSTS}, 'network': 'none',
              'certificate_trust': 'ephemeral REQUESTS_CA_BUNDLE, no system trust change',
              'image_id': runner.image_id, 'targets': args.targets,
              'status': execution.result.status.value, 'message': execution.message,
              'groups': dict(Counter(case.status.value for case in execution.result.test_cases)),
              'artifacts': execution.artifact_directory}
    (Path(execution.artifact_directory) / 'offline-service-diagnostic.json').write_text(
        json.dumps(record, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(record, indent=2))
    return 0 if execution.result.status.value == 'pass' else 1


if __name__ == '__main__':
    raise SystemExit(main())
