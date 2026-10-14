"""NodeBB's public Redis test target with individual and completion evidence."""
import json
from pathlib import Path

from agentless_ml.validation import DockerTestRunner, PublicTestCommand
from agentless_ml.validation.reports import TestReport
from check_v2_nodebb_setup import setup_script

LIMIT = 32 * 1024 * 1024
REPORTER = Path(__file__).with_name('nodebb_mocha_reporter.cjs')


def public_command(timeout_seconds, *, offline=True):
    reporter = REPORTER.read_text(encoding='utf-8')
    script = (
        setup_script(offline=offline) + '; '
        'cat > /tmp/nodebb-reporter.cjs <<\'NODEBB_COMPLETION_REPORTER\'\n'
        + reporter + '\nNODEBB_COMPLETION_REPORTER\n'
        'export PATH=/tmp/work/node_modules/.bin:$PATH; '
        'set +e; npm test -- --reporter /tmp/nodebb-reporter.cjs '
        '--reporter-option output=/tmp/nodebb-report.json; rc=$?; exit "$rc"'
    )
    # Mocha returns the failure count (capped at 255), while npm preserves it.
    # PublicTestCommand accepts 1..124; higher exits remain harness errors.
    return PublicTestCommand(('sh', '-c', script), timeout_seconds=timeout_seconds,
                             failure_exit_codes=tuple(range(1, 125)),
                             report=TestReport('mocha-json', '/tmp/nodebb-report.json'))


def audit_completion(raw_audit, raw_report):
    if raw_audit is None or raw_report is None:
        return {'complete': False, 'reason': 'missing completion audit or individual report'}
    if len(raw_audit) > LIMIT or len(raw_report) > LIMIT:
        return {'complete': False, 'reason': 'evidence exceeds capture limit'}
    try:
        audit, report = json.loads(raw_audit), json.loads(raw_report)
        if audit['schema_version'] != 1:
            raise ValueError('unsupported completion schema')
        planned, ended = audit['planned'], audit['ended']
        if not isinstance(planned, list) or not isinstance(ended, list):
            raise ValueError('invalid test inventory')
        if not planned or not all(isinstance(key, str) for key in planned + ended):
            raise ValueError('empty or invalid test inventory')
        if len(set(planned)) != len(planned) or len(set(ended)) != len(ended):
            raise ValueError('duplicate test IDs; matching would be ambiguous')
        reported = []
        for field in ('passes', 'failures', 'pending'):
            entries = report[field]
            if not isinstance(entries, list):
                raise ValueError('invalid individual report')
            reported.extend(json.dumps([entry.get('file') or '', entry['fullTitle']],
                                       separators=(',', ':'), ensure_ascii=False) for entry in entries)
        missing = sorted(set(planned) - set(ended))
        unexpected = sorted(set(ended) - set(planned))
        report_matches = len(set(reported)) == len(reported) and set(reported) == set(ended)
        counts_match = (audit['runner_total'] == len(planned) and
                        audit['stats_tests'] == len(ended) and report['stats']['tests'] == len(ended))
        lifecycle = audit['run_started'] is True and audit['run_ended'] is True and audit['aborted'] is False
        return dict(complete=bool(lifecycle and counts_match and report_matches and
                                  not (missing or unexpected or audit['hook_failures'])),
                    planned_tests=len(planned), ended_tests=len(ended),
                    initial_planned_tests=audit.get('initial_planned_tests', len(planned)),
                    dynamically_added=audit.get('dynamically_added', 0),
                    missing_tests=missing, unexpected_tests=unexpected,
                    report_matches=report_matches, counts_match=counts_match,
                    run_ended=audit['run_ended'], aborted=audit['aborted'],
                    hook_failures=audit['hook_failures'])
    except (KeyError, ValueError, TypeError, AttributeError) as error:
        return {'complete': False, 'reason': str(error)}


class NodeBBPublicSuiteRunner(DockerTestRunner):
    def run(self, source, command):
        self.captured = {}
        execution = super().run(source, command)
        directory = Path(execution.artifact_directory)
        for name, content in self.captured.items():
            if content is not None:
                (directory / name).write_bytes(content)
        self.completion_audit = audit_completion(self.captured.get('mocha-completion.json'),
                                                self.captured.get('mocha-individual.json'))
        (directory / 'completion-audit.json').write_text(
            json.dumps(self.completion_audit, indent=2) + '\n', encoding='utf-8')
        return execution

    def _docker(self, *args, **kwargs):
        result = super()._docker(*args, **kwargs)
        if args[0] == 'inspect':
            for name, path in [('mocha-completion.json', '/tmp/nodebb-completion.json'),
                               ('mocha-individual.json', '/tmp/nodebb-report.json'),
                               ('mocha-raw.json', '/tmp/nodebb-raw.json')]:
                self.captured[name] = self._read_file(args[1], path, LIMIT + 1)
        return result
