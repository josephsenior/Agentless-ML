"""One unchanged Element Web public Jest file; no installs or full suite."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import tempfile

from agentless_ml.validation import DockerTestRunner, PublicTestCommand

IMAGE = 'sha256:019f091af3b25701ad36458202da68a1ffeeba294b06768d3e1fee45c01e044e'
BASE = '4f32727829c1087e9d3d9955785d8a6255457c7d'
TEST = 'test/unit-tests/utils/sets-test.ts'
EXPECTED = {'sets setHasDiff ' + title for title in (
    'should flag true on A length > B length', 'should flag true on A length < B length',
    'should flag true on element differences', 'should flag false if same but order different',
    'should flag false if same',
)}


def smoke_command():
    script = (
        'set -e; test "$(git -C /app rev-parse HEAD)" = ' + BASE + '; '
        'git -C /app archive --format=tar --output=/tmp/base.tar HEAD; '
        'tar --no-same-owner -xf /tmp/base.tar -C /tmp/work; '
        'cd /tmp/work; test ! -e node_modules; ln -s /app/node_modules node_modules; '
        'sha256sum package.json jest.config.ts test/globalSetup.ts test/setupTests.ts '
        + TEST + ' src/utils/sets.ts; '
        'yarn test --runInBand --runTestsByPath ' + TEST + ' --json '
        '--outputFile=/tmp/element-jest.json --cacheDirectory=/tmp/element-jest-cache'
    )
    return PublicTestCommand(('sh', '-c', script), timeout_seconds=180)


def verify_report(report):
    suites = report.get('testResults', [])
    cases = [case for suite in suites for case in suite.get('assertionResults', [])]
    titles = [case.get('fullName') for case in cases]
    return bool(len(suites) == 1 and suites[0].get('name', '').endswith('/' + TEST)
                and len(cases) == 5 and set(titles) == EXPECTED
                and all(case.get('status') == 'passed' for case in cases)
                and report.get('success') is True and report.get('numTotalTests') == 5
                and report.get('numPassedTests') == 5 and report.get('numFailedTests') == 0
                and report.get('numPendingTests') == 0 and report.get('numRuntimeErrorTestSuites') == 0)


class JestCaptureRunner(DockerTestRunner):
    def run(self, source, command):
        self.raw_report = None
        execution = super().run(source, command)
        if self.raw_report is not None:
            Path(execution.artifact_directory, 'jest-native.json').write_bytes(self.raw_report)
        return execution

    def _docker(self, *args, **kwargs):
        result = super()._docker(*args, **kwargs)
        if args[0] == 'inspect':
            self.raw_report = self._read_file(args[1], '/tmp/element-jest.json', 32 * 1024 * 1024 + 1)
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    runner = JestCaptureRunner(IMAGE, args.output / 'executions', memory_mb=4096,
                              cpus=1, tmpfs_mb=4096, pids_limit=2048, run_as_image_user=True,
                              execution_phase='trusted-baseline', network_mode='none')
    with tempfile.TemporaryDirectory(prefix='agentless-element-smoke-') as temporary:
        execution = runner.run(Path(temporary), smoke_command())
    report = (json.loads(runner.raw_report) if runner.raw_report is not None
              and len(runner.raw_report) <= 32 * 1024 * 1024 else {})
    verified = verify_report(report)
    evidence = dict(condition='Element Web selected public sets utility smoke', image_id=IMAGE,
                    base_commit=BASE, selected_file=TEST, expected_tests=sorted(EXPECTED),
                    execution=asdict(execution), individual_report_verified=verified,
                    individual_results=report.get('testResults', []),
                    smoke_checked=execution.result.status.value == 'pass' and verified,
                    full_suite_ready=False, tests_modified=False, dependencies_installed=False,
                    model_calls=0, verifier_run=False)
    (args.output / 'result.json').write_text(json.dumps(evidence, indent=2, default=str) + '\n', encoding='utf-8')
    print(json.dumps(dict(status=execution.result.status.value, smoke_checked=evidence['smoke_checked'],
                         report_verified=verified, artifacts=execution.artifact_directory), indent=2))
    if not evidence['smoke_checked']:
        raise SystemExit('selected Jest smoke did not pass with all five individual results')


if __name__ == '__main__':
    main()
