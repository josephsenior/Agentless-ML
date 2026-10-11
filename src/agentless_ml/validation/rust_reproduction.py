"""Cargo-nextest reporting for a controller-selected Rust integration test."""

import re
from pathlib import PurePosixPath

from agentless_ml.schemas import ValidationKind

from .docker import PublicTestCommand
from .reports import ReportFormat, TestReport
from .reproduction import ReproductionSpec


_RUST_RUNNER = r"""
import base64
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from xml.etree import ElementTree as ET

manifest, target, test, report = sys.argv[1:]
raw = b''
cases = []
code = 2
try:
    with tempfile.TemporaryDirectory(prefix='reproduction-rust-') as directory:
        root = Path(directory)
        home = root / 'cargo-home'
        home.mkdir()
        original_home = Path(os.environ.get('CARGO_HOME', str(Path.home() / '.cargo')))
        for name in ('registry', 'git'):
            cached = original_home / name
            if cached.is_dir():
                (home / name).symlink_to(cached.resolve(), target_is_directory=True)
        store = root / 'nextest-store'
        config = root / 'nextest.toml'
        config.write_text('[store]\ndir = ' + json.dumps(str(store)) + '\n'
                          '[profile.default]\nretries = 0\nfail-fast = false\n'
                          '[profile.default.junit]\npath = "junit.xml"\n', encoding='utf-8')
        env = dict(os.environ, CARGO_HOME=str(home), CARGO_TARGET_DIR=str(root / 'target'),
                   CARGO_NET_OFFLINE='true', CARGO_INCREMENTAL='0',
                   CARGO_PROFILE_DEV_DEBUG='line-tables-only',
                   CARGO_PROFILE_TEST_DEBUG='line-tables-only')
        run = subprocess.run([
            'cargo', 'nextest', 'run', '--offline', '--manifest-path', manifest,
            '--test', target, '--config-file', str(config), '--profile', 'default',
            '--build-jobs', '1', '--test-threads', '1', '--retries', '0',
            '--no-fail-fast', '--no-tests', 'fail', '-E', 'test(=' + test + ')',
        ], env=env)
        junit = store / 'default' / 'junit.xml'
        if junit.is_file():
            with junit.open('rb') as stream:
                raw = stream.read(16 * 1024 * 1024 + 1)
        if run.returncode not in (0, 100):
            raise RuntimeError('cargo-nextest infrastructure/build exit: ' + str(run.returncode))
        if not raw or len(raw) > 16 * 1024 * 1024:
            raise RuntimeError('Missing or oversized Rust report')
        if b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():
            raise RuntimeError('Rust report declares XML entities')
        document = ET.fromstring(raw)
        if document.tag not in ('testsuites', 'testsuite'):
            raise RuntimeError('Unexpected Rust report root')
        entries = list(document.iter('testcase'))
        if len(entries) != 1 or entries[0].get('name') != test:
            raise RuntimeError('Rust report must contain exactly the selected test')
        entry = entries[0]
        children = list(entry)
        if any(child.tag.startswith(('rerun', 'flaky')) for child in children):
            raise RuntimeError('Rust reproduction unexpectedly retried')
        failures = entry.findall('failure')
        if entry.find('error') is not None:
            status = 'other'
        elif entry.find('skipped') is not None:
            status = 'skipped'
        elif failures:
            # Nextest also uses <failure> for aborts, timeouts and leaks. Those
            # are not ordinary libtest failures and must fail closed.
            status = 'failed' if all(f.get('type') == 'test failure with exit code 101' for f in failures) else 'other'
        else:
            status = 'passed'
        cases.append({'suite': entry.get('classname') or target, 'name': test, 'status': status})
        if status == 'passed' and run.returncode == 0:
            code = 0
        elif status == 'failed' and run.returncode == 100:
            code = 1
        else:
            raise RuntimeError('Rust test evidence is unclean or contradicts its exit')
except Exception as error:
    print(error, file=sys.stderr)
    cases.append({'suite': target, 'name': '__adapter_error__', 'status': 'other'})
Path(report).write_text(json.dumps({'results': {'tests': cases},
    'rust_junit_base64': base64.b64encode(raw).decode('ascii')}), encoding='utf-8')
sys.exit(code)
"""


def rust_reproduction_command(
    path: str, *, test_name: str, timeout_seconds: float = 600,
) -> PublicTestCommand:
    """Run one ordinary Cargo integration test with offline nextest/JUnit.

    The source must be a new direct child of a crate's tests/ directory. That
    crate must already discover integration tests automatically. Custom test
    harnesses and feature/build provisioning remain the caller's responsibility.
    Requires Python 3, Cargo, Rust and cargo-nextest already installed in Docker.
    """
    source = PurePosixPath(path)
    if (source.suffix != '.rs' or source.parent.name != 'tests'
            or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', source.stem)
            or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*(?:::[A-Za-z_][A-Za-z0-9_]*)*', test_name)):
        raise ValueError('Rust reproduction requires tests/<target>.rs and a literal test name')
    manifest = str(source.parent.parent / 'Cargo.toml')
    command = PublicTestCommand(
        ('python3', '-c', _RUST_RUNNER, manifest, source.stem, test_name, '/tmp/reproduction.json'),
        kind=ValidationKind.REPRODUCTION, timeout_seconds=timeout_seconds,
        failure_exit_codes=(1, 2),
        report=TestReport(ReportFormat.CTRF_JSON, '/tmp/reproduction.json'),
    )
    ReproductionSpec(path, command)
    return command
