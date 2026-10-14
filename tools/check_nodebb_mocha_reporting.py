"""Exercise the reporter with the pinned image's real Mocha before public tests."""
import argparse
from collections import Counter
import json
from pathlib import Path

from agentless_ml.validation import PublicTestCommand
from agentless_ml.validation.reports import TestReport
from v2_nodebb_public import NodeBBPublicSuiteRunner, REPORTER

ROOT = Path(__file__).resolve().parents[1]
IMAGE = 'sha256:cc8c9217344bf50df0a4276abad046538bb20e5c2f2815a1b2e201871c5cf364'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    runner = NodeBBPublicSuiteRunner(IMAGE, args.output, memory_mb=512, cpus=1,
                                    tmpfs_mb=128, pids_limit=128, run_as_image_user=True)
    results = []
    for mode in ('complete', 'bail', 'hook', 'duplicate', 'dynamic'):
        script = (
            "cat > /tmp/nodebb-reporter.cjs <<'NODEBB_REPORTER'\n"
            + REPORTER.read_text(encoding='utf-8') + '\nNODEBB_REPORTER\n'
            f'export REPORTER_FIXTURE_MODE={mode}; '
            'node /app/node_modules/mocha/bin/mocha.js --no-config --no-package '
            '--bail --reporter /tmp/nodebb-reporter.cjs '
            '--reporter-option output=/tmp/nodebb-report.json suite.cjs'
        )
        execution = runner.run(ROOT / 'tests/fixtures/nodebb_mocha_completion',
                               PublicTestCommand(('sh', '-c', script), timeout_seconds=60,
                                                 report=TestReport('mocha-json', '/tmp/nodebb-report.json')))
        audit = runner.completion_audit
        counts = dict(Counter(case.status.value for case in execution.result.test_cases))
        expected_counts = {'complete': {'passed': 3, 'skipped': 1},
                           'bail': {'passed': 1, 'skipped': 1, 'failed': 1},
                           'hook': {'failed': 1},
                           'duplicate': {'passed': 5, 'skipped': 1},
                           'dynamic': {'passed': 4, 'skipped': 1}}[mode]
        success = (audit['complete'] is (mode in ('complete', 'duplicate', 'dynamic'))
                   and counts == expected_counts)
        results.append(dict(mode=mode, verified=success, counts=counts, audit=audit,
                            artifacts=execution.artifact_directory))
    (args.output / 'verification.json').write_text(json.dumps(results, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(results, indent=2))
    if not all(row['verified'] for row in results):
        raise SystemExit('Mocha reporting verification failed')


if __name__ == '__main__':
    main()
