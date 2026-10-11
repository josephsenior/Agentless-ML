"""Only authored fixtures are executed here, never generated source."""

import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from agentless_ml.schemas import ValidationStatus
from agentless_ml.validation import (
    DockerTestRunner, go_reproduction_command, javascript_reproduction_command,
    typescript_reproduction_command,
)
from agentless_ml.validation.reports import parse_report, ReportFormat


NODE_CASES = [
    ("require('assert').strictEqual(1, 1)", "passed", 0),
    ("require('assert').strictEqual(1, 2)", "failed", 1),
    ("Promise.resolve().then(() => require('assert').fail('issue'))", "failed", 1),
    ("setTimeout(() => require('assert').fail('issue'), 1)", "failed", 1),
    ("require('agentless_missing_dependency')", "error", 2),
    ("throw new Error('setup failed')", "error", 2),
    ("Promise.reject(new Error('setup failed'))", "error", 2),
    ("const broken = ;", "error", 2),
    ("process.exit(0)", "error", 0),
    ("process.exit(1)", "error", 1),
    ("process.exitCode = 1", "error", 2),
]


@pytest.mark.skipif(not shutil.which('node'), reason='Node is not installed')
@pytest.mark.parametrize('factory', [javascript_reproduction_command, typescript_reproduction_command])
@pytest.mark.parametrize('source,status,code', NODE_CASES)
def test_node_authored_fixtures(tmp_path, factory, source, status, code):
    (tmp_path / 'reproduce.cjs').write_text(source, encoding='utf-8')
    report = tmp_path / 'report.json'
    command = factory('reproduce.cjs')
    argv = [str(report) if arg == '/tmp/reproduction.json' else arg for arg in command.argv]
    execution = subprocess.run(argv, cwd=tmp_path, capture_output=True, timeout=15)
    assert execution.returncode == code, execution.stderr
    assert [case.status.value for case in parse_report(report.read_bytes(), ReportFormat.CTRF_JSON)] == [status]


@pytest.mark.skipif(not shutil.which('node'), reason='Node is not installed')
def test_node_candidate_relative_import(tmp_path):
    (tmp_path / 'helper.cjs').write_text('module.exports = 42')
    (tmp_path / 'reproduce.cjs').write_text("require('assert').strictEqual(require('./helper.cjs'), 42)")
    report = tmp_path / 'report.json'
    command = javascript_reproduction_command('reproduce.cjs')
    argv = [str(report) if arg == '/tmp/reproduction.json' else arg for arg in command.argv]
    run = subprocess.run(argv, cwd=tmp_path, capture_output=True, timeout=15)
    assert run.returncode == 0, run.stderr
    assert parse_report(report.read_bytes(), ReportFormat.CTRF_JSON)[0].status.value == 'passed'


GO_CASES = [
    ('func TestIssue(t *testing.T) {}', 'passed', 0),
    ('func TestIssue(t *testing.T) { t.Fatal("issue") }', 'failed', 1),
    ('func TestIssue(t *testing.T) { panic("setup") }', 'error', 2),
    ('func TestIssue(t *testing.T) { t.Skip("unsupported") }', 'skipped', 0),
    ('func TestOther(t *testing.T) {}', 'error', 2),
    ('func TestIssue(t *testing.T) { doesNotCompile() }', 'error', 2),
    ('func TestIssue(t *testing.T) { t.Run("child", func(t *testing.T) { t.Fatal("issue") }) }', 'failed', 1),
    ('func TestIssue(t *testing.T) {}\nfunc TestMain(m *testing.M) {}', 'error', 2),
    ('func TestIssue(t *testing.T) { t.Run("child", func(t *testing.T) { panic("setup") }) }', 'error', 2),
]


@pytest.mark.skipif(not shutil.which('go'), reason='Go is not installed')
@pytest.mark.parametrize('source,status,code', GO_CASES)
def test_go_authored_fixtures(tmp_path, source, status, code):
    (tmp_path / 'go.mod').write_text('module reproduction.fixture\n\ngo 1.20\n')
    (tmp_path / 'reproduce_test.go').write_text('package fixture\nimport "testing"\n' + source)
    report = tmp_path / 'report.json'
    command = go_reproduction_command('reproduce_test.go', test_name='TestIssue')
    # Only adapt the host executable/cache/report locations, not classification.
    runner = command.argv[2].replace("'/tmp/go-build'", repr(str(tmp_path.parent / 'go-cache')))
    run = subprocess.run([sys.executable, '-c', runner, *command.argv[3:-1], str(report)],
                         cwd=tmp_path, capture_output=True, timeout=120)
    assert run.returncode == code, run.stderr
    cases = parse_report(report.read_bytes(), ReportFormat.CTRF_JSON)
    assert status in [case.status.value for case in cases]
    raw = json.loads(report.read_bytes())
    assert 'go_events_jsonl' in raw
    if code != 2:
        assert 'TestIssue' in raw['go_events_jsonl']
    if 't.Run' in source and code != 2:
        assert {case.test_id for case in cases} == {'./.::TestIssue', './.::TestIssue/child'}


@pytest.mark.parametrize('factory,path,options', [
    (go_reproduction_command, '../x_test.go', {'test_name': 'TestIssue'}),
    (go_reproduction_command, 'x_test.go', {'test_name': 'Test.*'}),
    (javascript_reproduction_command, '../x.cjs', {}),
    (javascript_reproduction_command, 'x.mjs', {}),
    (typescript_reproduction_command, 'x.ts', {'node_path': 'bad\npath'}),
])
def test_adapter_configuration_boundaries(factory, path, options):
    with pytest.raises(ValueError):
        factory(path, **options)


def test_recorded_smoke_configs_use_reporting_factories():
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location('recorded_slice', root / 'tools/run_swe_bench_pro_v2_recorded_slice.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for name, language in [('v2_go_vuls_header', 'go'), ('v2_js_nodebb_upload_path', 'javascript'),
                           ('v2_ts_tutanota_credentials', 'typescript')]:
        directory = root / 'experiments/swe_bench_pro' / name
        config = json.loads((directory / 'experiment.json').read_text())
        reproduction = module.reproduction_spec(config, language)
        assert reproduction.command.report.format is ReportFormat.CTRF_JSON
        assert reproduction.command.timeout_seconds == config['reproduction']['timeout_seconds']
        assert 'argv' not in config['reproduction']
        source = (directory / 'reproduction_test.txt').read_text()
        assert 'process.exitCode' not in source
        if language == 'typescript':
            assert 'NODE_PATH=/app/node_modules' in reproduction.command.argv
            assert 'throw new SyntaxError' in source


@pytest.mark.skipif(os.environ.get('AGENTLESS_REPRODUCTION_DOCKER_TESTS') != '1',
                    reason='opt-in pinned-image authored-fixture diagnostic')
@pytest.mark.parametrize('language,source,expected', [
    ('javascript', "require('assert').strictEqual(1, 2)", ValidationStatus.FAIL),
    ('javascript', "require('assert').strictEqual(1, 1)", ValidationStatus.PASS),
    ('javascript', "require('missing_agentless_dependency')", ValidationStatus.HARNESS_ERROR),
    ('typescript', "const value: number = 1; require('assert').strictEqual(value, 2)", ValidationStatus.FAIL),
    ('typescript', "const value: number = 1; require('assert').strictEqual(value, 1)", ValidationStatus.PASS),
    ('typescript', "const value: = ;", ValidationStatus.HARNESS_ERROR),
    ('typescript', "require('missing_agentless_dependency')", ValidationStatus.HARNESS_ERROR),
    ('go', 'func TestIssue(t *testing.T) { t.Fatal("issue") }', ValidationStatus.FAIL),
    ('go', 'func TestIssue(t *testing.T) {}', ValidationStatus.PASS),
    ('go', 'func TestIssue(t *testing.T) { panic("setup") }', ValidationStatus.HARNESS_ERROR),
    ('go', 'func TestIssue(t *testing.T) { broken() }', ValidationStatus.HARNESS_ERROR),
])
def test_pinned_image_authored_fixture(tmp_path, language, source, expected):
    root = Path(__file__).resolve().parents[1]
    name = {'javascript': 'v2_js_nodebb_upload_path', 'typescript': 'v2_ts_tutanota_credentials',
            'go': 'v2_go_vuls_header'}[language]
    image = json.loads((root / 'experiments/swe_bench_pro' / name / 'experiment.json').read_text())['image_id']
    workspace = tmp_path / 'source'
    workspace.mkdir()
    if language == 'go':
        (workspace / 'go.mod').write_text('module reproduction.fixture\n\ngo 1.20\n')
        (workspace / 'reproduce_test.go').write_text('package fixture\nimport "testing"\n' + source)
        command = go_reproduction_command('reproduce_test.go', test_name='TestIssue')
    else:
        path = 'reproduce.ts' if language == 'typescript' else 'reproduce.cjs'
        (workspace / path).write_text(source)
        factory = typescript_reproduction_command if language == 'typescript' else javascript_reproduction_command
        command = factory(path, node_path='/app/node_modules' if language == 'typescript' else None)
    runner = DockerTestRunner(image, tmp_path / 'artifacts', memory_mb=8192, tmpfs_mb=4096,
                              cpus=1, pids_limit=2048, run_as_image_user=True)
    execution = runner.run(workspace, command)
    assert execution.result.status is expected, execution
    if language == 'go':
        reports = list(Path(execution.artifact_directory).glob('report*'))
        assert len(reports) == 1
        raw = json.loads(reports[0].read_bytes())
        assert 'go_events_jsonl' in raw
