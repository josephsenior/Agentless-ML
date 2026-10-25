"""Exercise both real CLI preflight paths with independent pinned workspaces."""

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from agentless_ml.shared_task import canonical, load_shared_task
from agentless_ml.workspace import LocalGitWorkspaceProvider

ROOT = Path(__file__).resolve().parents[1]


def compare(args):
    record = load_shared_task(args.shared_task)
    if args.output.exists():
        raise ValueError('output must be a new directory')
    args.output.mkdir(parents=True)
    environment = dict(os.environ, PYTHONPATH=str(ROOT / 'src'), PYTHONDONTWRITEBYTECODE='1')
    grinta_revision = subprocess.check_output(['git', '-C', str(args.grinta_root),
        'rev-parse', 'HEAD']).decode().strip()

    def run(argv, cwd):
        result = subprocess.run([sys.executable, *argv], cwd=cwd, env=environment,
            capture_output=True, check=True, timeout=180)
        return json.loads(result.stdout)

    with tempfile.TemporaryDirectory(prefix='shared-start-comparison-') as temporary:
        workspace_root = Path(temporary)
        agentless = run([str(ROOT / 'tools/run_shared_deepswe_workflow.py'),
            '--shared-task', str(args.shared_task.resolve()),
            '--source-repository', str(args.source_repository.resolve()),
            '--workspace-root', str(workspace_root / 'agentless'),
            '--artifact-root', str(args.output.resolve() / 'unused'), '--inspect-start'], ROOT)
        provider = LocalGitWorkspaceProvider(args.source_repository,
            record['identity']['base_commit'], workspace_root / 'grinta')
        with provider.create() as checkout:
            grinta = run(['-m', 'evaluation.deepswe.run_grinta',
                '--shared-task', str(args.shared_task.resolve()), '--workspace', str(checkout.path),
                '--task-id', record['identity']['task_id'], '--grinta-commit', grinta_revision,
                '--output-dir', str(args.output.resolve() / 'unused'), '--dry-run'], args.grinta_root)
    for system, manifest in (('agentless', agentless), ('grinta', grinta)):
        (args.output / (system + '-start.json')).write_bytes(canonical(manifest))
    matched = (agentless['starting_conditions'] == grinta['starting_conditions']
               and agentless['spec_sha256'] == grinta['spec_sha256']
               and agentless['workspace_verified'] and grinta['workspace_verified'])
    result = {'task_id': record['identity']['task_id'], 'configured_starting_conditions_match': matched,
        'spec_sha256': record['spec_sha256'],
        'starting_conditions_sha256': agentless['starting_conditions_sha256'],
        'agentless_revision': agentless['implementation_revision'], 'grinta_revision': grinta_revision,
        'independent_clean_workspaces_verified': True,
        'compared_sections': list(agentless['starting_conditions']),
        'observed_container_match': False, 'capability_enforcement_verified': False,
        'model_calls': 0, 'benchmark_tests_run': 0,
        'scope': 'real launcher preflights; configured inputs and prepared source, not installed runtime equivalence'}
    (args.output / 'comparison.json').write_bytes(canonical(result))
    if not matched:
        raise ValueError('starting conditions differ; inspect saved manifests')
    print(json.dumps(result))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--shared-task', type=Path, required=True)
    parser.add_argument('--source-repository', type=Path, required=True)
    parser.add_argument('--grinta-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    compare(parser.parse_args())


if __name__ == '__main__':
    main()
