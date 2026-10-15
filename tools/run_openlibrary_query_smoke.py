"""Verify pinned public Infogami, then run only nine Open Library query cases."""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

from agentless_ml.validation import DockerTestRunner, PublicTestCommand
from agentless_ml.validation.reports import TestReport
from verify_openlibrary_infogami import COMMIT

IMAGE = 'sha256:03205f63224d992c930df7a2b898353d9d3dface4ab4d921eebc73dc909c1ba6'
BASE = '02f647f7d525286b6e3a661133c3772649e585cd'
TEST = 'openlibrary/tests/solr/test_query_utils.py'
EXPECTED = {'openlibrary.tests.solr.test_query_utils::' + name for name in (
    'test_luqum_remove_child[Complete match]', 'test_luqum_remove_child[Binary Op Left]',
    'test_luqum_remove_child[Binary Op Right]', 'test_luqum_remove_child[Group]',
    'test_luqum_remove_child[Unary]', 'test_luqum_replace_child[Complex replace]',
    'test_luqum_replace_child[Deeply nested]', 'test_luqum_parser', 'test_luqum_replace_fields',
)}


def public_manifest(reference):
    def git(*args):
        return subprocess.check_output(['git', '-C', str(reference), *args], timeout=30)
    if git('rev-parse', COMMIT + '^{commit}').decode().strip() != COMMIT:
        raise ValueError('public reference commit mismatch')
    files = []
    for record in git('ls-tree', '-rz', '--full-tree', COMMIT).split(b'\0'):
        if not record:
            continue
        metadata, path = record.split(b'\t', 1)
        mode, kind, blob = metadata.decode().split()
        if kind != 'blob' or mode not in ('100644', '100755'):
            raise ValueError('unsupported public Infogami tree entry')
        files.append(dict(path=path.decode(), mode=mode, blob=blob))
    return dict(commit=COMMIT, tree=git('rev-parse', COMMIT + '^{tree}').decode().strip(), files=files)


def smoke_command():
    script = (
        'set -e; mkdir /tmp/agentless-setup; '
        'mv /tmp/work/_infogami-pin.json /tmp/work/_verify-infogami.py /tmp/agentless-setup/; '
        'test "$(git -C /app rev-parse HEAD)" = ' + BASE + '; '
        'test "$(git -C /app rev-parse HEAD:vendor/infogami)" = ' + COMMIT + '; '
        'git -C /app archive --format=tar --output=/tmp/base.tar HEAD; '
        'tar --no-same-owner -xf /tmp/base.tar -C /tmp/work; cd /tmp/work; '
        'export HOME=/tmp PYTHONPATH=/tmp/work:/tmp/work/vendor/infogami PYTHONDONTWRITEBYTECODE=1; '
        'python /tmp/agentless-setup/_verify-infogami.py /tmp/agentless-setup/_infogami-pin.json '
        '/app/vendor/infogami /tmp/work/vendor/infogami; '
        'python --version; sha256sum Makefile pyproject.toml openlibrary/conftest.py '
        'openlibrary/solr/query_utils.py ' + TEST + '; '
        'python -m pytest ' + TEST + ' --ignore=infogami --ignore=vendor --ignore=node_modules '
        '-o cache_dir=/tmp/openlibrary-pytest-cache --junitxml=/tmp/openlibrary-query.xml'
    )
    return PublicTestCommand(('sh', '-c', script), timeout_seconds=180,
                             report=TestReport('junit-xml', '/tmp/openlibrary-query.xml'))


def verify_cases(cases):
    return (len(cases) == 9 and {case.test_id for case in cases} == EXPECTED
            and all(case.status.value == 'passed' for case in cases))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--infogami-reference', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    manifest = public_manifest(args.infogami_reference)
    raw = (json.dumps(manifest, indent=2) + '\n').encode()
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / 'infogami-public-manifest.json').write_bytes(raw)
    runner = DockerTestRunner(IMAGE, args.output / 'executions', memory_mb=4096,
                              cpus=1, tmpfs_mb=4096, pids_limit=2048, run_as_image_user=True,
                              execution_phase='trusted-baseline', network_mode='none')
    with tempfile.TemporaryDirectory(prefix='agentless-openlibrary-smoke-') as temporary:
        source = Path(temporary)
        (source / '_infogami-pin.json').write_bytes(raw)
        (source / '_verify-infogami.py').write_bytes(Path(__file__).with_name('verify_openlibrary_infogami.py').read_bytes())
        execution = runner.run(source, smoke_command())
    verified = verify_cases(execution.result.test_cases)
    evidence = dict(condition='Open Library selected public query utility smoke', image_id=IMAGE,
                    base_commit=BASE, selected_file=TEST, expected_tests=sorted(EXPECTED),
                    infogami_commit=COMMIT, public_manifest_sha256=hashlib.sha256(raw).hexdigest(),
                    public_manifest_files=len(manifest['files']), execution=asdict(execution),
                    individual_report_verified=verified,
                    smoke_checked=execution.result.status.value == 'pass' and verified,
                    full_suite_ready=False, tests_modified=False, dependencies_installed=False,
                    model_calls=0, verifier_run=False)
    (args.output / 'result.json').write_text(json.dumps(evidence, indent=2, default=str) + '\n', encoding='utf-8')
    print(json.dumps(dict(status=execution.result.status.value, smoke_checked=evidence['smoke_checked'],
                         report_verified=verified, artifacts=execution.artifact_directory), indent=2))
    if not evidence['smoke_checked']:
        raise SystemExit('selected Open Library smoke did not pass with all nine individual cases')


if __name__ == '__main__':
    main()
