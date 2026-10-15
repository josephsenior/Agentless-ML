"""Run only Navidrome's six public number specs; no installs or full suite."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import tempfile

from agentless_ml.validation import DockerTestRunner, PublicTestCommand
from agentless_ml.validation.reports import TestReport

IMAGE = 'sha256:e02e944a8d412a74f87549ac6e61c31ae628503f253cde75bd1634c6e491937b'
BASE = '2f90fc9bd40e24afd900b5ee85426f32684b960b'
PACKAGE = './utils/number'
REPORT = '/tmp/navidrome-number.xml'
EXPECTED = {'Number Suite::[It] ' + name for name in (
    'Min returns zero value if no arguments are passed',
    'Min returns the smallest int', 'Min returns the smallest float',
    'Max returns zero value if no arguments are passed',
    'Max returns the biggest int', 'Max returns the biggest float',
)}


def smoke_command():
    script = (
        'set -e; test "$(git -C /app rev-parse HEAD)" = ' + BASE + '; '
        'git -C /app archive --format=tar --output=/tmp/base.tar HEAD; '
        'tar --no-same-owner -xf /tmp/base.tar -C /tmp/work; cd /tmp/work; '
        'export HOME=/tmp GOCACHE=/tmp/navidrome-go-build GOTMPDIR=/tmp '
        'GOMODCACHE=/go/pkg/mod GOPROXY=off GOTOOLCHAIN=local GOMAXPROCS=1 GOFLAGS=-mod=readonly; '
        'go version; sha256sum Makefile .github/workflows/pipeline.yml go.mod go.sum '
        'utils/number/number.go utils/number/number_test.go; '
        'go test -race -cover -v -json -count=1 -p 1 -timeout 120s '
        + PACKAGE + ' -args -ginkgo.junit-report=' + REPORT
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
    with tempfile.TemporaryDirectory(prefix='agentless-navidrome-smoke-') as temporary:
        execution = runner.run(Path(temporary), smoke_command())
    verified = verify_cases(execution.result.test_cases)
    evidence = dict(condition='Navidrome selected public number-package smoke', image_id=IMAGE,
                    base_commit=BASE, selected_package=PACKAGE, expected_tests=sorted(EXPECTED),
                    execution=asdict(execution), individual_report_verified=verified,
                    smoke_checked=execution.result.status.value == 'pass' and verified,
                    toolchain_note='Image Go 1.24.3 differs from pinned CI Go 1.18/1.19.',
                    build_cache='fresh writable scratch; no precompiled image cache copied',
                    full_suite_ready=False, tests_modified=False, dependencies_installed=False,
                    model_calls=0, verifier_run=False)
    (args.output / 'result.json').write_text(json.dumps(evidence, indent=2, default=str) + '\n', encoding='utf-8')
    print(json.dumps(dict(status=execution.result.status.value, smoke_checked=evidence['smoke_checked'],
                         report_verified=verified, artifacts=execution.artifact_directory), indent=2))
    if not evidence['smoke_checked']:
        raise SystemExit('selected Navidrome smoke did not pass with all six individual specs')


if __name__ == '__main__':
    main()
