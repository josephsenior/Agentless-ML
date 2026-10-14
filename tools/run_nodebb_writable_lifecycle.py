"""Run only NodeBB's unchanged public plugin lifecycle group with private deps."""
import argparse
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
import tempfile

from agentless_ml.adapters.benchmarks.deepswe_execution import _NODE_MODULES
from agentless_ml.workspace import LocalGitWorkspaceProvider, verify_sealed_repository
from check_v2_nodebb_setup import ROOT, SPEC
from v2_nodebb_public import NodeBBPublicSuiteRunner, public_command

GROUP = 'Plugins install/activate/uninstall'
EXPECTED = {GROUP + ' ' + title for title in (
    'should install a plugin', 'should activate plugin',
    'should error if plugin id is invalid', 'should upgrade plugin',
    'should uninstall a plugin',
)}
COPY = ('test ! -e /tmp/work/node_modules; '
        'cp -a --no-preserve=ownership /app/node_modules /tmp/work/node_modules; ')


def lifecycle_command():
    # Use the helper's unchanged default interface; do not overwrite local edits.
    command = public_command(1800)
    script = command.argv[2]
    changes = (
        (_NODE_MODULES, COPY),
        ('npm_config_offline=true', 'npm_config_offline=false'),
        ('output=/tmp/nodebb-report.json; rc=$?',
         "output=/tmp/nodebb-report.json test/plugins.js --grep '^Plugins install/activate/uninstall '; rc=$?"),
    )
    for before, after in changes:
        if script.count(before) != 1:
            raise ValueError('public setup boundary changed; review lifecycle wrapper')
        script = script.replace(before, after)
    return replace(command, argv=('sh', '-c', 'export CI=true; ' + script))


def assess_group(report, audit):
    entries = [(status, entry) for field, status in (
        ('passes', 'passed'), ('failures', 'failed'), ('pending', 'skipped'))
        for entry in report.get(field, [])]
    titles = [entry.get('rawFullTitle') for _, entry in entries]
    return dict(expected=sorted(EXPECTED),
                outcomes=[dict(title=entry.get('rawFullTitle'), status=status,
                               error=entry.get('err')) for status, entry in entries],
                passed=(len(entries) == len(EXPECTED) and set(titles) == EXPECTED
                        and all(status == 'passed' for status, _ in entries)
                        and audit.get('hook_failures') == []
                        and audit.get('run_ended') is True
                        and audit.get('aborted') is False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    spec = json.loads(SPEC.read_bytes())
    repository = ROOT.parent / 'benchmarks/swe-bench-pro-v2/repos' / spec['instance_id']
    verify_sealed_repository(repository, spec['base_commit'])
    hashes = {name: hashlib.sha256((repository / name).read_bytes()).hexdigest()
              for name in ('test/plugins.js', '.mocharc.yml', 'install/package.json')}
    args.output.mkdir(parents=True, exist_ok=False)
    runner = NodeBBPublicSuiteRunner(spec['image_id'], args.output / 'executions',
                                    memory_mb=4096, cpus=1, tmpfs_mb=4096, pids_limit=2048,
                                    run_as_image_user=True, execution_phase='trusted-baseline',
                                    network_mode='bridge')
    with LocalGitWorkspaceProvider(repository, spec['base_commit'],
                                   Path(tempfile.gettempdir()) / 'agentless-v2-survey-workspaces').create() as workspace:
        execution = runner.run(workspace.path, lifecycle_command())
        provenance = asdict(workspace.provenance)
    directory = Path(execution.artifact_directory)
    report = json.loads((directory / 'mocha-individual.json').read_bytes()) if (directory / 'mocha-individual.json').exists() else {}
    audit = json.loads((directory / 'mocha-completion.json').read_bytes()) if (directory / 'mocha-completion.json').exists() else {}
    group = assess_group(report, audit)
    evidence = dict(condition='NodeBB writable-dependency public lifecycle diagnostic',
                    task_id=spec['instance_id'], base_commit=spec['base_commit'],
                    image_id=runner.image_id, workspace=provenance, execution=asdict(execution),
                    public_source_sha256=hashes, group=group, full_completion_audit=runner.completion_audit,
                    full_suite_run=False, full_suite_ready=False, network_mode='bridge',
                    candidate_selection_eligible=False, verifier_run=False, model_calls=0)
    (args.output / 'result.json').write_text(json.dumps(evidence, indent=2, default=str) + '\n', encoding='utf-8')
    print(json.dumps(dict(status=execution.result.status.value, group_passed=group['passed'],
                         outcomes=group['outcomes'], artifacts=str(directory)), indent=2))
    if execution.result.status.value != 'pass' or not group['passed']:
        raise SystemExit('public lifecycle diagnostic did not pass all five unchanged cases')


if __name__ == '__main__':
    main()
