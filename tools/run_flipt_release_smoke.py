"""One public Flipt TestIs run with six verified native Go child outcomes."""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import tempfile

from agentless_ml.validation import DockerTestRunner, PublicTestCommand

IMAGE = 'sha256:896e9e03b52384f2696043debe8cbf7c55334a6b5900570e6f4c91e0551d165c'
BASE = '85bb23a3571794c7ba01e61904bac6913c3d9729'
PACKAGE = 'go.flipt.io/flipt/internal/release'
EXPECTED = {'TestIs/' + name for name in (
    '0.17.1', '1.0.0', 'dev', '1.0.0-snapshot', '1.0.0-rc1', '1.0.0-rc.1',
)}
MAX_BYTES = 32 * 1024 * 1024


def smoke_command():
    script = (
        'set -e; test "$(git -C /app rev-parse HEAD)" = ' + BASE + '; '
        'git -C /app archive --format=tar --output=/tmp/base.tar HEAD; '
        'tar --no-same-owner -xf /tmp/base.tar -C /tmp/work; cd /tmp/work; '
        'export HOME=/tmp GOCACHE=/tmp/flipt-go-build GOTMPDIR=/tmp GOMODCACHE=/go/pkg/mod '
        'GOPROXY=off GOTOOLCHAIN=local GOMAXPROCS=1 GOFLAGS=-mod=readonly; '
        'go version; sha256sum .github/workflows/test.yml magefile.go build/testing/test.go '
        'go.mod go.sum go.work go.work.sum internal/release/check.go internal/release/check_test.go; '
        'set +e; go test -race -p 1 -coverprofile=/tmp/flipt-release-coverage.txt '
        '-covermode=atomic -v -json -count=1 -timeout=60s -run \'^TestIs$\' ./internal/release '
        '>/tmp/flipt-test.jsonl; outcome=$?; cat /tmp/flipt-test.jsonl; exit "$outcome"'
    )
    return PublicTestCommand(('sh', '-c', script), timeout_seconds=180)


def verify_events(raw):
    if raw is None or not raw or len(raw) > MAX_BYTES:
        return False
    try:
        events = [json.loads(line) for line in raw.decode('utf-8').splitlines()]
    except (UnicodeError, ValueError):
        return False
    states = {}
    started = finished = False
    for event in events:
        if not isinstance(event, dict) or event.get('Package') != PACKAGE or finished:
            return False
        action, name = event.get('Action'), event.get('Test')
        if name is not None and not isinstance(name, str):
            return False
        if action == 'start' and name is None and not started:
            started = True
            continue
        if not started or action not in ('run', 'output', 'pass'):
            return False
        if name is not None:
            if name not in EXPECTED | {'TestIs'}:
                return False
            if action == 'run':
                if name in states:
                    return False
                states[name] = 'run'
            elif action == 'pass':
                if states.get(name) != 'run':
                    return False
                if name == 'TestIs' and any(states.get(child) != 'pass' for child in EXPECTED):
                    return False
                states[name] = 'pass'
        elif action == 'pass':
            if set(states) != EXPECTED | {'TestIs'} or any(value != 'pass' for value in states.values()):
                return False
            finished = True
        elif action != 'output':
            return False
    return finished


class NativeCaptureRunner(DockerTestRunner):
    def run(self, source, command):
        self.captured = {}
        execution = super().run(source, command)
        for filename, content in self.captured.items():
            if content is not None:
                Path(execution.artifact_directory, filename).write_bytes(content)
        return execution

    def _docker(self, *args, **kwargs):
        result = super()._docker(*args, **kwargs)
        if args[0] == 'inspect':
            for filename, path in (('go-native.jsonl', '/tmp/flipt-test.jsonl'),
                                   ('coverage.txt', '/tmp/flipt-release-coverage.txt')):
                self.captured[filename] = self._read_file(args[1], path, MAX_BYTES + 1)
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    runner = NativeCaptureRunner(IMAGE, args.output / 'executions', memory_mb=4096,
                                 cpus=1, tmpfs_mb=4096, pids_limit=2048, run_as_image_user=True,
                                 execution_phase='trusted-baseline', network_mode='none')
    with tempfile.TemporaryDirectory(prefix='agentless-flipt-smoke-') as temporary:
        execution = runner.run(Path(temporary), smoke_command())
    verified = verify_events(runner.captured.get('go-native.jsonl'))
    coverage = runner.captured.get('coverage.txt')
    coverage_ok = bool(coverage and len(coverage) <= MAX_BYTES
                       and coverage.startswith(b'mode: atomic\n') and len(coverage.splitlines()) > 1)
    evidence = dict(condition='Flipt selected public TestIs smoke', image_id=IMAGE,
                    base_commit=BASE, selected_package=PACKAGE, selected_test='TestIs',
                    execution=asdict(execution), expected_child_tests=sorted(EXPECTED),
                    individual_report_verified=verified, atomic_coverage_retained=coverage_ok,
                    individual_results=[dict(test_id=PACKAGE + '::' + name, status='passed')
                                        for name in sorted(EXPECTED)] if verified else [],
                    report_sha256={name: hashlib.sha256(data).hexdigest()
                                   for name, data in runner.captured.items() if data is not None},
                    smoke_checked=execution.result.status.value == 'pass' and verified and coverage_ok,
                    toolchain_note='Image Go 1.24.3; pinned workflow variable 1.21; module toolchain go1.22.2.',
                    report_scope='Native diagnostic evidence, not a registered framework report adapter.',
                    full_suite_ready=False, tests_modified=False, dependencies_installed=False,
                    model_calls=0, verifier_run=False)
    (args.output / 'result.json').write_text(json.dumps(evidence, indent=2, default=str) + '\n', encoding='utf-8')
    print(json.dumps(dict(status=execution.result.status.value, smoke_checked=evidence['smoke_checked'],
                         report_verified=verified, artifacts=execution.artifact_directory), indent=2))
    if not evidence['smoke_checked']:
        raise SystemExit('selected Flipt smoke did not pass with all six child results and coverage')


if __name__ == '__main__':
    main()
