"""Full Go public-target reporting, with a separate package-completion audit."""
from collections import Counter
from dataclasses import replace
import json
from pathlib import Path

from agentless_ml.adapters.benchmarks.deepswe_execution import GO
from agentless_ml.validation import DockerTestRunner

LIMIT = 32 * 1024 * 1024


def public_command(timeout_seconds):
    # Reuse the existing streaming CTRF converter; retain Vuls make test's
    # package set, coverage and verbosity. JSON and count=1 add reporting and
    # prevent cached successes, not test selection.
    command = GO.command(('./...',), timeout_seconds=timeout_seconds)
    script = command.argv[2]
    needle = 'go test -json -count=1 "$@"'
    if script.count(needle) != 1:
        raise ValueError('Go reporting command changed; review the V2 wrapper')
    script = script.replace(needle, 'go test -json -count=1 -cover -v "$@"')
    prefix = ('cd /tmp/work || exit 125; '
              'export GO111MODULE=on GOPROXY=off GOCACHE=/tmp/go-build; '
              'go list ./... > /tmp/go-packages.txt || exit 125; ')
    return replace(command, argv=('sh', '-c', prefix + script, 'v2-public-tests', './...'))


def audit_packages(packages, events):
    """A report with some passes cannot hide an unbuilt or interrupted package."""
    if packages is None or events is None:
        return {'complete': False, 'reason': 'missing package inventory or event stream'}
    if len(packages) > LIMIT or len(events) > LIMIT:
        return {'complete': False, 'reason': 'evidence exceeds capture limit'}
    try:
        expected = packages.decode('utf-8').splitlines()
        if not expected or len(set(expected)) != len(expected) or any(not p.strip() for p in expected):
            raise ValueError('empty or duplicate package inventory')
        terminal, started, ended, failures = {}, set(), set(), set()
        for line in events.decode('utf-8').splitlines():
            event = json.loads(line)
            action, package, test = event.get('Action'), event.get('Package'), event.get('Test')
            if not package:
                continue  # Toolchain build output does not name a test package.
            if test:
                key = (package, test)
                if action == 'run':
                    started.add(key)
                if action in ('pass', 'fail', 'skip'):
                    if key in ended:
                        raise ValueError('duplicate terminal test event')
                    ended.add(key)
                if action == 'fail':
                    failures.add(package)
            elif action in ('pass', 'fail', 'skip'):
                if package in terminal:
                    raise ValueError('duplicate terminal package event')
                terminal[package] = action
        missing = sorted(set(expected) - set(terminal))
        unexpected = sorted(set(terminal) - set(expected))
        unexplained = sorted(p for p, status in terminal.items() if status == 'fail' and p not in failures)
        unfinished = sorted('::'.join(key) for key in started - ended)
        return dict(complete=not (missing or unexpected or unexplained or unfinished),
                    expected_packages=len(expected), terminal_packages=len(terminal),
                    package_outcomes=dict(Counter(terminal.values())),
                    missing_packages=missing, unexpected_packages=unexpected,
                    failed_packages_without_test_failure=unexplained, unfinished_tests=unfinished)
    except (ValueError, UnicodeError, AttributeError, TypeError) as error:
        return {'complete': False, 'reason': str(error)}


class GoPublicSuiteRunner(DockerTestRunner):
    """Keep raw events before container cleanup, including on failed attempts."""
    def run(self, source, command):
        self.captured = {}
        execution = super().run(source, command)
        directory = Path(execution.artifact_directory)
        for name, content in self.captured.items():
            if content is not None:
                (directory / name).write_bytes(content)
        self.package_audit = audit_packages(self.captured.get('go-packages.txt'),
                                            self.captured.get('go-events.jsonl'))
        (directory / 'package-audit.json').write_text(
            json.dumps(self.package_audit, indent=2) + '\n', encoding='utf-8')
        return execution

    def _docker(self, *args, **kwargs):
        result = super()._docker(*args, **kwargs)
        if args[0] == 'inspect':
            for name, path in [('go-packages.txt', '/tmp/go-packages.txt'),
                               ('go-events.jsonl', '/tmp/go-test.json')]:
                self.captured[name] = self._read_file(args[1], path, LIMIT + 1)
        return result
