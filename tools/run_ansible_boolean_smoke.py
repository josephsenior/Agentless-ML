"""Six unchanged public Ansible unit tests; no installs or full suite."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import tempfile

from agentless_ml.validation import DockerTestRunner, PublicTestCommand
from agentless_ml.validation.reports import TestReport

IMAGE = 'sha256:7cae127d37e28600d08026f70cbc2aef029ab2c9daf0bba67c912cec5fb4d0d0'
BASE = 'f7234968d241d7171aadb1e873a67510753f3163'
TEST = 'test/units/module_utils/parsing/test_convert_bool.py'
REPORT = 'test/results/junit/python3.11-module_utils-units.xml'
EXPECTED = {'test.units.module_utils.parsing.test_convert_bool.TestBoolean::' + name
            for name in ('test_bools', 'test_none', 'test_numbers', 'test_strings',
                         'test_junk_values_nonstrict', 'test_junk_values_strict')}


def smoke_command():
    script = (
        'set -e; test "$(git -C /app rev-parse HEAD)" = ' + BASE + '; '
        'git -C /app archive --format=tar --output=/tmp/base.tar HEAD; '
        'tar --no-same-owner -xf /tmp/base.tar -C /tmp/work; cd /tmp/work; '
        'export HOME=/tmp PYTHONPATH=/tmp/work/lib:/tmp/work/test/lib; '
        'python3 --version; '
        'sha256sum bin/ansible-test test/lib/ansible_test/_internal/commands/units/__init__.py '
        'test/lib/ansible_test/_data/pytest/config/default.ini '
        'lib/ansible/module_utils/parsing/convert_bool.py ' + TEST + '; '
        'python3 bin/ansible-test units ' + TEST + ' --python 3.11 '
        '--num-workers 1 --requirements-mode skip --local'
    )
    return PublicTestCommand(('sh', '-c', script), timeout_seconds=180,
                             report=TestReport('junit-xml', REPORT))


def verify_cases(cases):
    return (len(cases) == 6 and {case.test_id for case in cases} == EXPECTED
            and all(case.status.value == 'passed' for case in cases))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    runner = DockerTestRunner(IMAGE, args.output / 'executions', memory_mb=4096,
                              cpus=1, tmpfs_mb=4096, pids_limit=2048, run_as_image_user=True,
                              execution_phase='trusted-baseline', network_mode='none')
    with tempfile.TemporaryDirectory(prefix='agentless-ansible-smoke-') as temporary:
        execution = runner.run(Path(temporary), smoke_command())
    verified = verify_cases(execution.result.test_cases)
    evidence = dict(condition='Ansible selected public boolean conversion smoke', image_id=IMAGE,
                    base_commit=BASE, selected_file=TEST, expected_tests=sorted(EXPECTED),
                    execution=asdict(execution), individual_report_verified=verified,
                    smoke_checked=execution.result.status.value == 'pass' and verified,
                    full_suite_ready=False, tests_modified=False, dependencies_installed=False,
                    model_calls=0, verifier_run=False)
    (args.output / 'result.json').write_text(json.dumps(evidence, indent=2, default=str) + '\n', encoding='utf-8')
    print(json.dumps(dict(status=execution.result.status.value, smoke_checked=evidence['smoke_checked'],
                         report_verified=verified, artifacts=execution.artifact_directory), indent=2))
    if not evidence['smoke_checked']:
        raise SystemExit('selected Ansible smoke did not pass with all six individual results')


if __name__ == '__main__':
    main()
