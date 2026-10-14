"""Verify the labelled service, then replay the unchanged public API test file."""
import argparse
from collections import Counter
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
import shlex
import tempfile

from agentless_ml.validation import PublicTestCommand
from agentless_ml.workspace import LocalGitWorkspaceProvider, verify_sealed_repository
from v2_nodebb_public import NodeBBPublicSuiteRunner, public_command

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT.parent / 'output/swe-bench-pro-v2-readiness/2026-10-14-nodebb-registry-image-v2/build.json'
TASK = 'instance_NodeBB__NodeBB-f9ce92df988db7c1ae55d9ef96d247d27478bc70-vf2cf3cbd463b7ad942381f1c6d077626485a1e9e'
BASE = '61d17c95e573f91ab5c65d25218451e9afd07d77'
TITLES = (
    'should have each path parameter defined in its context',
    'should have examples when parameters are present',
    'should contain a valid request body (if present) with application/json or multipart/form-data type if POST/PUT/DELETE',
    'should not error out when called',
    'response status code should match one of the schema defined responses',
    'response body should match schema definition',
    'should successfully re-login if needed',
)
START = ('node /opt/nodebb-registry/service.cjs > /tmp/registry-requests.jsonl 2>&1 & '
         'node /opt/nodebb-registry/verify.cjs; ')


class RegistryRunner(NodeBBPublicSuiteRunner):
    def _docker(self, *args, **kwargs):
        result = super()._docker(*args, **kwargs)
        if args[0] == 'inspect':
            for name, path in [('registry-requests.jsonl', '/tmp/registry-requests.jsonl'),
                               ('registry-verification.json', '/tmp/registry-verification.json'),
                               ('page-target.json', '/tmp/page-target.json')]:
                self.captured[name] = self._read_file(args[1], path, 32 * 1024 * 1024 + 1)
        return result


def page_command():
    command = public_command(1800)
    script = command.argv[2]
    needle = 'output=/tmp/nodebb-report.json; rc=$?'
    if script.count(needle) != 1:
        raise ValueError('public command changed; review API shard wrapper')
    script = script.replace(needle, 'output=/tmp/nodebb-report.json test/api.js; rc=$?')
    configure = (
        "const fs=require('fs');const c=JSON.parse(fs.readFileSync('config.json','utf8'));"
        "c.registry='http://127.0.0.1:8766';fs.writeFileSync('config.json',JSON.stringify(c));"
    )
    identify = (
        "const fs=require('fs'),Parser=require('@apidevtools/swagger-parser');"
        "Parser.dereference('public/openapi/read.yaml').then(api=>{"
        "const paths=Object.keys(api.paths).filter(p=>Object.keys(api.paths[p]).includes('get'));"
        "const index=paths.indexOf('/api/admin/extend/plugins');if(index<0)throw Error('page absent');"
        "fs.writeFileSync('/tmp/page-target.json',JSON.stringify({route:'/api/admin/extend/plugins',"
        "occurrence:index+1,source:'public/openapi/read.yaml'}));"
        "}).catch(e=>{console.error(e);process.exitCode=1;});"
    )
    needle = 'export PATH=/tmp/work/node_modules/.bin:$PATH; '
    if script.count(needle) != 1:
        raise ValueError('public setup boundary changed')
    script = script.replace(needle, START + 'node -e ' + shlex.quote(configure) + '; '
                            + 'node -e ' + shlex.quote(identify) + '; ' + needle)
    return replace(command, argv=('sh', '-c', script))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    build = json.loads(BUILD.read_bytes())
    runner = RegistryRunner(build['image_id'], args.output / 'executions',
                            memory_mb=4096, cpus=1, tmpfs_mb=4096,
                            pids_limit=2048, run_as_image_user=True)
    if args.verify_only:
        source = ROOT / 'tests/fixtures/nodebb_mocha_completion'
        execution = runner.run(source, PublicTestCommand(('sh', '-c', 'set -e; ' + START), timeout_seconds=60))
        provenance = None
        source_hashes = {}
    else:
        repository = ROOT.parent / 'benchmarks/swe-bench-pro-v2/repos' / TASK
        verify_sealed_repository(repository, BASE)
        source_hashes = {name: hashlib.sha256((repository / name).read_bytes()).hexdigest()
                         for name in ('test/api.js', 'public/openapi/read.yaml', '.mocharc.yml')}
        with LocalGitWorkspaceProvider(repository, BASE,
                                       Path(tempfile.gettempdir()) / 'agentless-v2-survey-workspaces').create() as workspace:
            provenance = asdict(workspace.provenance)
            execution = runner.run(workspace.path, page_command())
    directory = Path(execution.artifact_directory)
    verification = json.loads((directory / 'registry-verification.json').read_bytes()) if (directory / 'registry-verification.json').exists() else None
    page_result = None
    if not args.verify_only and (directory / 'page-target.json').exists() and (directory / 'mocha-individual.json').exists():
        target = json.loads((directory / 'page-target.json').read_bytes())
        report = json.loads((directory / 'mocha-individual.json').read_bytes())
        suffix = f" [occurrence {target['occurrence']}]"
        selected = []
        for field, status in [('passes', 'passed'), ('failures', 'failed'), ('pending', 'skipped')]:
            for test in report[field]:
                if test.get('rawFullTitle') in TITLES and test['fullTitle'] == test['rawFullTitle'] + suffix:
                    selected.append(dict(title=test['rawFullTitle'], status=status))
        page_result = dict(target, cases=selected, passed=len(selected) == len(TITLES)
                           and {row['title'] for row in selected} == set(TITLES)
                           and all(row['status'] == 'passed' for row in selected))
    evidence = dict(condition=build['condition'], image_id=runner.image_id,
                    parent_image=build['parent_image'], task_id=TASK, base_commit=BASE,
                    verify_only=args.verify_only, execution=asdict(execution), workspace=provenance,
                    public_source_sha256=source_hashes, service_verification=verification,
                    page_result=page_result, completion_audit=runner.completion_audit,
                    individual_counts=dict(Counter(case.status.value for case in execution.result.test_cases)),
                    full_suite_ready=False, model_calls=0, verifier_run=False)
    (args.output / 'result.json').write_text(json.dumps(evidence, indent=2, default=str) + '\n', encoding='utf-8')
    print(json.dumps({key: value for key, value in evidence.items()
                      if key not in ('execution', 'completion_audit', 'workspace')}, indent=2))
    print(json.dumps(dict(status=execution.result.status.value, message=execution.message,
                         artifacts=execution.artifact_directory), indent=2))
    if not verification or not verification.get('verified'):
        raise SystemExit('service verification failed')
    if not args.verify_only and (not page_result or not page_result['passed']):
        raise SystemExit('requested public page assertions did not all pass')


if __name__ == '__main__':
    main()
