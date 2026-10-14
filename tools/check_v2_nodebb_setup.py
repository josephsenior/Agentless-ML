"""Bounded NodeBB Redis CI setup diagnostic; does not run or grade tests."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import shlex
import tempfile

from agentless_ml.adapters.benchmarks.deepswe_execution import _NODE_MODULES
from agentless_ml.validation import DockerTestRunner, PublicTestCommand
from agentless_ml.workspace import LocalGitWorkspaceProvider, verify_sealed_repository

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / 'experiments/swe_bench_pro/v2_js_nodebb_upload_path/experiment.json'
SETUP = {
    'url': 'http://127.0.0.1:4567/forum', 'secret': 'abcdef',
    'admin:username': 'admin', 'admin:email': 'test@example.org',
    'admin:password': 'hAN3Eg8W', 'admin:password:confirm': 'hAN3Eg8W',
    'database': 'redis', 'redis:host': '127.0.0.1', 'redis:port': 6379,
    'redis:password': '', 'redis:database': 0,
}
CI = {'host': '127.0.0.1', 'database': 1, 'port': 6379}


def setup_script(*, offline=True):
    return (
        'set -e; cd /tmp/work; '
        f'export TEST_ENV=production npm_config_offline={str(offline).lower()} npm_config_cache=/tmp/npm-cache; '
        'cp install/package.json package.json; '
        + _NODE_MODULES +
        'redis-server --version; '
        'redis-server --bind 127.0.0.1 --port 6379 --save "" --appendonly no '
        '--dir /tmp --pidfile /tmp/nodebb-redis.pid --logfile /tmp/nodebb-redis.log --daemonize yes; '
        'redis-cli -h 127.0.0.1 ping; '
        'node app --setup=' + shlex.quote(json.dumps(SETUP)) +
        ' --ci=' + shlex.quote(json.dumps(CI)) + '; '
        'node -e ' + shlex.quote(
            "const fs=require('fs'),p=require('path');"
            "const c=JSON.parse(fs.readFileSync('config.json','utf8'));"
            "if(c.database!=='redis'||Number(c.redis.database)!==0||"
            "Number(c.test_database.database)!==1) throw Error('unexpected database separation');"
            "console.log(JSON.stringify({setup_complete:true,source_root:process.cwd(),"
            "database:c.database,test_database:c.test_database.database}));"
        )
    )


def setup_command():
    return PublicTestCommand(('sh', '-c', setup_script()), timeout_seconds=300)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    spec = json.loads(SPEC.read_bytes())
    repository = ROOT.parent / 'benchmarks/swe-bench-pro-v2/repos' / spec['instance_id']
    verify_sealed_repository(repository, spec['base_commit'])
    runner = DockerTestRunner(spec['image_id'], args.output / 'executions',
                              memory_mb=4096, cpus=1, tmpfs_mb=4096,
                              pids_limit=2048, run_as_image_user=True)
    with LocalGitWorkspaceProvider(repository, spec['base_commit'],
                                    Path(tempfile.gettempdir()) / 'agentless-v2-survey-workspaces').create() as workspace:
        execution = runner.run(workspace.path, setup_command())
        evidence = dict(condition='NodeBB public Redis CI setup diagnostic only',
                        task_id=spec['instance_id'], base_commit=spec['base_commit'],
                        image_id=runner.image_id, workspace=asdict(workspace.provenance),
                        execution=asdict(execution), tests_run=False, full_suite_ready=False,
                        model_calls=0, verifier_run=False)
    (args.output / 'setup.json').write_text(json.dumps(evidence, indent=2, default=str) + '\n', encoding='utf-8')
    print(json.dumps(evidence, indent=2, default=str))


if __name__ == '__main__':
    main()
