"""Run only Teleport TestCachedParser and verify its native Go result."""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import tempfile

from agentless_ml.validation import DockerTestRunner, PublicTestCommand

IMAGE = 'sha256:576147fc4357d7a6b4a6a347477e9a95f5e7fd01b277f25284589356350717e9'
BASE = '4d7c51b4f535cecfd139625e6af1746c46abc712'
PACKAGE = 'github.com/gravitational/teleport/lib/utils/typical'
TEST = 'TestCachedParser'
MAX_BYTES = 32 * 1024 * 1024


def smoke_command():
    script = (
        'set -e; test "$(git -C /app rev-parse HEAD)" = ' + BASE + '; '
        'git -C /app archive --format=tar --output=/tmp/base.tar HEAD; '
        'tar --no-same-owner -xf /tmp/base.tar -C /tmp/work; cd /tmp/work; '
        'export HOME=/tmp GOCACHE=/tmp/teleport-go-build GOTMPDIR=/tmp GOMODCACHE=/go/pkg/mod '
        'GOPROXY=off GOTOOLCHAIN=local GOMAXPROCS=1 GOFLAGS=-mod=readonly; '
        'unset TELEPORT_EXPRESSION_CACHE_SIZE; '
        'go version; sha256sum Makefile go.mod go.sum lib/utils/typical/*.go; '
        'set +e; go test -race -shuffle=on -cover -covermode=atomic '
        '-coverprofile=/tmp/teleport-parser-coverage.txt -json -v -count=1 -p 1 -timeout=60s '
        '-run \'^TestCachedParser$\' ./lib/utils/typical >/tmp/teleport-test.jsonl; '
        'outcome=$?; cat /tmp/teleport-test.jsonl; exit "$outcome"'
    )
    return PublicTestCommand(('sh', '-c', script), timeout_seconds=180)


def verify_events(raw):
    if not raw or len(raw) > MAX_BYTES:
        return False
    try:
        events = [json.loads(line) for line in raw.decode('utf-8').splitlines()]
    except (UnicodeError, ValueError):
        return False
    started = finished = False
    test_state = 'unseen'
    for event in events:
        if not isinstance(event, dict) or event.get('Package') != PACKAGE or finished:
            return False
        action, name = event.get('Action'), event.get('Test')
        if action == 'start' and name is None and not started:
            started = True
            continue
        if not started or action not in ('run', 'output', 'pass'):
            return False
        if name is not None:
            if name != TEST:
                return False
            if action == 'run':
                if test_state != 'unseen':
                    return False
                test_state = 'running'
            elif action == 'pass':
                if test_state != 'running':
                    return False
                test_state = 'passed'
        elif action == 'pass':
            if test_state != 'passed':
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
            for filename, path in (('go-native.jsonl', '/tmp/teleport-test.jsonl'),
                                   ('coverage.txt', '/tmp/teleport-parser-coverage.txt')):
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
    with tempfile.TemporaryDirectory(prefix='agentless-teleport-smoke-') as temporary:
        execution = runner.run(Path(temporary), smoke_command())
    verified = verify_events(runner.captured.get('go-native.jsonl'))
    coverage = runner.captured.get('coverage.txt')
    coverage_ok = bool(coverage and len(coverage) <= MAX_BYTES
                       and coverage.startswith(b'mode: atomic\n') and len(coverage.splitlines()) > 1)
    evidence = dict(condition='Teleport selected public cached-parser smoke', image_id=IMAGE,
                    base_commit=BASE, selected_package=PACKAGE, selected_test=TEST,
                    execution=asdict(execution), individual_report_verified=verified,
                    atomic_coverage_retained=coverage_ok,
                    individual_results=[dict(test_id=PACKAGE + '::' + TEST, status='passed')] if verified else [],
                    report_sha256={name: hashlib.sha256(data).hexdigest()
                                   for name, data in runner.captured.items() if data is not None},
                    smoke_checked=execution.result.status.value == 'pass' and verified and coverage_ok,
                    toolchain_note='Installed image Go 1.23.1; module declares Go 1.21.',
                    scope_note='One named test; its assertion loops are not separate reported cases. Direct untagged package smoke, not full tagged CI preparation.',
                    report_scope='Native diagnostic evidence, not a registered framework report adapter.',
                    full_suite_ready=False, tests_modified=False, dependencies_installed=False,
                    model_calls=0, verifier_run=False)
    (args.output / 'result.json').write_text(json.dumps(evidence, indent=2, default=str) + '\n', encoding='utf-8')
    print(json.dumps(dict(status=execution.result.status.value, smoke_checked=evidence['smoke_checked'],
                         report_verified=verified, artifacts=execution.artifact_directory), indent=2))
    if not evidence['smoke_checked']:
        raise SystemExit('selected Teleport smoke did not pass with native test/package results and coverage')


if __name__ == '__main__':
    main()
