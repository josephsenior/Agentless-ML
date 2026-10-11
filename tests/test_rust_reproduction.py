"""Synthetic reporter checks and opt-in authored Rust fixtures; no generated host execution."""

import base64
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import tomllib

import pytest

from agentless_ml.schemas import ValidationKind, ValidationResult, ValidationStatus
from agentless_ml.validation import DockerTestRunner, rust_reproduction_command
from agentless_ml.validation.reproduction_evidence import check_reproduction_result
from agentless_ml.validation.reports import parse_report, ReportFormat
from agentless_ml.validation.rust_reproduction import _RUST_RUNNER


def junit(child='', name='issue'):
    return f'<testsuites><testsuite><testcase classname="fixture::reproduce" name="{name}">{child}</testcase></testsuite></testsuites>'.encode()


@pytest.mark.parametrize('raw,exit_code,expected,code', [
    (junit(), 0, 'pass', 0),
    (junit('<failure type="test failure with exit code 101">assertion failed</failure>'), 100, 'fail', 1),
    (junit('<failure type="test failure"/>'), 100, 'harness_error', 2),
    (junit('<failure type="test failure with exit code 1"/>'), 100, 'harness_error', 2),
    (junit('<failure type="test abort"/>'), 100, 'harness_error', 2),
    (junit('<failure type="test timeout"/>'), 100, 'harness_error', 2),
    (junit('<failure type="test failure with leaked handles"/>'), 100, 'harness_error', 2),
    (junit('<failure/>'), 100, 'harness_error', 2),
    (junit('<error/>'), 100, 'harness_error', 2),
    (junit('<skipped/>'), 0, 'harness_error', 2),
    (junit('<failure type="test failure with exit code 101"/>'), 101, 'harness_error', 2),
    (junit(), 100, 'harness_error', 2),
    (junit('<failure type="test failure with exit code 101"/>'), 0, 'harness_error', 2),
    (junit('<flakyFailure/>'), 0, 'harness_error', 2),
    (junit('<rerunFailure/>'), 100, 'harness_error', 2),
    (junit(name='other'), 0, 'harness_error', 2),
    (b'<testsuites/>', 0, 'harness_error', 2),
    (b'<testsuites><testcase name="issue"/><testcase name="other"/></testsuites>', 0, 'harness_error', 2),
    (b'<invalid', 0, 'harness_error', 2),
    (b'<!DOCTYPE testsuites><testsuites/>', 0, 'harness_error', 2),
    (b'', 0, 'harness_error', 2),
    (b'', 4, 'harness_error', 2),
])
def test_rust_report_contract(tmp_path, monkeypatch, raw, exit_code, expected, code):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(tempfile, 'tempdir', str(tmp_path))
    monkeypatch.setenv('CARGO_HOME', str(tmp_path / 'existing-cargo-home'))
    report = tmp_path / 'report.json'
    captured = []

    def fake_nextest(argv, *, env):
        captured.append(argv)
        config = tomllib.loads(Path(argv[argv.index('--config-file') + 1]).read_text())
        destination = Path(config['store']['dir']) / 'default/junit.xml'
        destination.parent.mkdir(parents=True)
        if raw:
            destination.write_bytes(raw)
        assert env['CARGO_NET_OFFLINE'] == 'true'
        assert env['CARGO_INCREMENTAL'] == '0'
        assert Path(env['CARGO_HOME']).is_dir()
        return subprocess.CompletedProcess(argv, exit_code)

    monkeypatch.setattr(subprocess, 'run', fake_nextest)
    monkeypatch.setattr(sys, 'argv', ['runner', 'Cargo.toml', 'reproduce', 'issue', str(report)])
    with pytest.raises(SystemExit) as stopped:
        exec(compile(_RUST_RUNNER, '<trusted-rust-reporter>', 'exec'), {})
    assert stopped.value.code == code
    document = json.loads(report.read_bytes())
    assert base64.b64decode(document['rust_junit_base64']) == raw
    cases = parse_report(report.read_bytes(), ReportFormat.CTRF_JSON)
    result = ValidationResult(
        ValidationStatus.PASS if code == 0 else ValidationStatus.FAIL,
        ('trusted-rust-reporter',), 0, kind=ValidationKind.REPRODUCTION, test_cases=cases,
    )
    assert check_reproduction_result(result, report_declared=True).status.value == expected
    argv = captured[0]
    assert argv[argv.index('-E') + 1] == 'test(=issue)'
    assert argv[argv.index('--retries') + 1] == '0'
    assert argv[argv.index('--no-tests') + 1] == 'fail'
    assert '--offline' in argv


@pytest.mark.parametrize('path,name', [
    ('src/reproduce.rs', 'issue'), ('tests/nested/reproduce.rs', 'issue'),
    ('../tests/reproduce.rs', 'issue'), ('tests/../tests/reproduce.rs', 'issue'),
    ('tests/reproduce.rs', 'issue.*'), ('tests/reproduce.rs', 'issue) | all('),
    ('tests/reproduce.rs', ''), ('tests/-reproduce.rs', 'issue'),
])
def test_rust_configuration_boundary(path, name):
    with pytest.raises(ValueError):
        rust_reproduction_command(path, test_name=name)


def test_nested_crate_and_module_test_name():
    command = rust_reproduction_command('crates/example/tests/reproduce.rs', test_name='checks::issue')
    assert command.argv[3:6] == ('crates/example/Cargo.toml', 'reproduce', 'checks::issue')
    assert command.report.format is ReportFormat.CTRF_JSON
    assert command.kind is ValidationKind.REPRODUCTION


RUST_FIXTURES = [
    ('#[test] fn issue() { assert_eq!(reproduction_fixture::add(2, 3), 5); }', '-', ValidationStatus.FAIL),
    ('#[test] fn issue() { assert_eq!(reproduction_fixture::add(2, 3), 5); }', '+', ValidationStatus.PASS),
    ('#[test] fn issue() { nonexistent(); }', '+', ValidationStatus.HARNESS_ERROR),
    ('#[test] fn other() {}', '+', ValidationStatus.HARNESS_ERROR),
    ('#[test] #[ignore] fn issue() {}', '+', ValidationStatus.HARNESS_ERROR),
    ('#[test] fn issue() { std::process::abort(); }', '+', ValidationStatus.HARNESS_ERROR),
    ('#[test] fn issue() { std::process::exit(1); }', '+', ValidationStatus.HARNESS_ERROR),
    # Nextest cannot prove that assertions ran before an explicit successful exit.
    ('#[test] fn issue() { std::process::exit(0); }', '+', ValidationStatus.PASS),
    ('#[test] fn issue() { panic!("non-assertion panic"); }', '+', ValidationStatus.FAIL),
]


@pytest.mark.skipif(os.environ.get('AGENTLESS_RUST_REPRODUCTION_DOCKER_TESTS') != '1',
                    reason='opt-in pinned Rust image authored-fixture diagnostic')
@pytest.mark.parametrize('source,operator,expected', RUST_FIXTURES)
def test_rust_pinned_image(tmp_path, source, operator, expected):
    root = Path(__file__).resolve().parents[1]
    pin = json.loads((root / 'experiments/deepswe/corpus_pin.json').read_text())
    image = pin['container_digests']['wasmi-trap-coredumps']
    workspace = tmp_path / 'source'
    (workspace / 'src').mkdir(parents=True)
    (workspace / 'tests').mkdir()
    (workspace / 'Cargo.toml').write_text('[package]\nname = "reproduction-fixture"\nversion = "0.1.0"\nedition = "2021"\n')
    (workspace / 'src/lib.rs').write_text(f'pub fn add(a: i32, b: i32) -> i32 {{ a {operator} b }}')
    (workspace / 'tests/reproduce.rs').write_text(source)
    command = rust_reproduction_command('tests/reproduce.rs', test_name='issue', timeout_seconds=120)
    runner = DockerTestRunner(image, tmp_path / 'artifacts', memory_mb=4096, tmpfs_mb=4096,
                              cpus=1, pids_limit=2048, run_as_image_user=True)
    execution = runner.run(workspace, command)
    assert execution.result.status is expected, execution
    report = json.loads((Path(execution.artifact_directory) / 'report.json').read_bytes())
    if expected is not ValidationStatus.HARNESS_ERROR:
        assert b'<testcase' in base64.b64decode(report['rust_junit_base64'])
