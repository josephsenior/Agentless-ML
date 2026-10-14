"""Recover completed NodeBB reports after interruption of the host recorder.

This preserves evidence and records the missing command exit code. It cannot
turn an interrupted attempt into a ready baseline or resume a test process.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from agentless_ml.validation import DockerTestRunner
from agentless_ml.validation.reports import parse_report, ReportFormat
from v2_nodebb_public import audit_completion, LIMIT

IMAGE = 'sha256:cc8c9217344bf50df0a4276abad046538bb20e5c2f2815a1b2e201871c5cf364'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--container', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not args.container.startswith('agentless-ml-'):
        parser.error('expected a named Agentless test container')
    runner = DockerTestRunner(IMAGE, args.output)
    metadata = json.loads(runner._docker('inspect', args.container).stdout)[0]
    if metadata['Image'] != IMAGE:
        raise ValueError('container image differs from the reviewed NodeBB image')
    args.output.mkdir(parents=True, exist_ok=False)
    files = {}
    for name, path in [('mocha-completion.json', '/tmp/nodebb-completion.json'),
                       ('mocha-individual.json', '/tmp/nodebb-report.json'),
                       ('mocha-raw.json', '/tmp/nodebb-raw.json'),
                       ('stdout.log', '/tmp/agentless-stdout'),
                       ('stderr.log', '/tmp/agentless-stderr')]:
        content = runner._read_file(args.container, path, LIMIT + 1)
        if content is None or len(content) > LIMIT:
            raise ValueError(f'missing or oversized recovery file: {path}')
        (args.output / name).write_bytes(content)
        files[name] = content
    audit = audit_completion(files['mocha-completion.json'], files['mocha-individual.json'])
    individual = parse_report(files['mocha-individual.json'], ReportFormat.MOCHA_JSON)
    report = json.loads(files['mocha-individual.json'])
    evidence = dict(condition='Recovery after host recorder interruption',
                    image_id=IMAGE, container=args.container,
                    command_exit_code=None, host_recorder_interrupted=True,
                    readiness='not_ready', completion_audit=audit,
                    individual_counts=dict(Counter(case.status.value for case in individual)),
                    raw_mocha_stats=json.loads(files['mocha-raw.json'])['stats'],
                    failures=report['failures'],
                    artifact_sha256={name: hashlib.sha256(content).hexdigest()
                                     for name, content in files.items()},
                    host_config=metadata['HostConfig'])
    (args.output / 'recovery.json').write_text(json.dumps(evidence, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: value for key, value in evidence.items()
                      if key not in ('host_config', 'completion_audit', 'failures')}, indent=2))
    print(json.dumps({key: value for key, value in audit.items()
                      if key not in ('missing_tests', 'unexpected_tests')}, indent=2))


if __name__ == '__main__':
    main()
