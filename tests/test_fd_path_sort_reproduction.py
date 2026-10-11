"""Recorded fd fixture contract and opt-in sealed-source/controller verification."""

import json
import base64
import hashlib
import os
from pathlib import Path
import runpy

import pytest

from agentless_ml.adapters.languages import get_language_adapter
from agentless_ml.localization import construct_selected_context, extract_code_blocks, parse_locations_for_files
from agentless_ml.repair import apply_search_replace_edits, build_unified_diff, parse_search_replace_edits
from agentless_ml.validation import ReproductionSpec, rust_reproduction_command
from agentless_ml.validation.reproduction import parse_reproduction_source
from agentless_ml.workspace import LocalGitWorkspaceProvider, verify_sealed_repository

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / 'experiments/deepswe/fd_path_sort_reproduction'
SOURCE_PATHS = {'src/cli.rs', 'src/config.rs', 'src/main.rs', 'src/walk.rs'}


def test_fd_issue_reproduction_fixture_contract():
    spec = json.loads((EXPERIMENT / 'experiment.json').read_bytes())
    source = parse_reproduction_source((EXPERIMENT / 'reproduction_test.txt').read_text(), 'rust')
    command = rust_reproduction_command(spec['reproduction_path'], test_name=spec['test_name'],
                                       timeout_seconds=spec['timeout_seconds'])
    ReproductionSpec(spec['reproduction_path'], command)
    assert command.report is not None
    assert command.timeout_seconds == 600
    assert 'CARGO_BIN_EXE_fd' in source and '0..1205' in source
    assert 'Some(3)' in source and '"--max-buffer-time", "0"' in source
    assert 'partial' in spec['purpose'] and 'no separate public regression' in spec['regression_scope']
    assert spec['base_commit'] == '227883606023d62275fb48701aeac90f2b604143'


def test_fd_partial_repair_is_source_only_and_scoped():
    repair = (EXPERIMENT / 'repair_01_path_sort.txt').read_text()
    edits = parse_search_replace_edits(repair)
    assert len(edits) == 7 and {e.path for e in edits} == SOURCE_PATHS
    assert not any(e.creates_file for e in edits)
    assert 'value_parser = ["path"]' in repair
    assert 'self.buffer.truncate(max_results)' in repair
    assert '!self.config.sort_path' in repair
    with pytest.raises(ValueError):
        parse_search_replace_edits((EXPERIMENT / 'repair_00_malformed.txt').read_text())


@pytest.mark.parametrize('mutation', [None, 'wrong-baseline-reason', 'candidate-report-failed', 'changed-source'])
def test_saved_fd_audit_checks_nextest_output_and_contract(tmp_path, monkeypatch, mutation):
    # Synthetic saved records test the audit, not real fd behavior or Docker.
    tool = runpy.run_path(str(ROOT / 'tools/run_fd_path_sort_reproduction.py'))
    monkeypatch.setitem(tool['audit_existing'].__globals__, 'verify_sealed_repository', lambda *args: None)
    output = tmp_path / 'output'
    directory = output / 'runs/run-authored-audit'
    directory.mkdir(parents=True)
    (output / 'workspaces').mkdir()
    repositories = tmp_path / 'repositories'
    repositories.mkdir()
    spec = json.loads((EXPERIMENT / 'experiment.json').read_bytes())
    pin = json.loads((ROOT / 'experiments/deepswe/corpus_pin.json').read_bytes())
    digest = pin['container_digests'][spec['task_id']]
    old = {p: 'old\n' for p in SOURCE_PATHS}
    patch = build_unified_diff(old, {p: 'new\n' for p in SOURCE_PATHS})
    patch_hash = hashlib.sha256(patch.encode()).hexdigest()
    source = parse_reproduction_source(tool['responses']().reproduction_test, 'rust')
    if mutation == 'changed-source':
        source += '# changed\n'

    def write(path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding='utf-8')

    write(directory / 'task.json', {'benchmark': 'deepswe', 'instance_id': spec['task_id'],
          'base_commit': spec['base_commit'], 'container_digest': digest})
    write(directory / 'run.json', {'model_calls': 0, 'container_digest': digest,
          'implementation_revision': 'authored-audit', 'wall_time_seconds': 0, 'final_patch_sha256': patch_hash})
    write(directory / 'attempts.json', [{'status': 'repair_error'}, {'status': 'validated',
          'candidate': {'validation': [{'status': 'pass'}], 'diff': patch}}])
    baseline_dir = directory / 'reproduction-baseline/execution'
    write(directory / 'reproduction-baseline.json', {'checked_result': {'status': 'fail'},
          'artifact_directory': str(baseline_dir)})
    write(directory / 'prediction.json', {'instance_id': spec['task_id'], 'selected_candidate_id': 'repair-1',
          'model_patch': patch})
    write(directory / 'reproduction-source.json', {'source': source,
          'source_sha256': hashlib.sha256(source.encode()).hexdigest()})
    for path, failed in [(baseline_dir / 'report.json', True),
                         (directory / 'executions/repair-1/execution/report.json', False)]:
        reason = 'unexpected argument --sort' if mutation != 'wrong-baseline-reason' else 'unrelated panic'
        # Like actual nextest, put the panic output beside an empty failure tag.
        child = '<failure type="test failure with exit code 101"/><system-err>' + reason + '</system-err>' if failed else ''
        xml = '<testsuites><testcase name="issue_path_sort">' + child + '</testcase></testsuites>'
        status = 'failed' if failed or mutation == 'candidate-report-failed' else 'passed'
        write(path, {'results': {'tests': [{'name': 'issue_path_sort', 'status': status}]},
                     'rust_junit_base64': base64.b64encode(xml.encode()).decode()})
    if mutation:
        with pytest.raises(AssertionError):
            tool['audit_existing'](output, repositories)
    else:
        result = tool['audit_existing'](output, repositories)
        assert result['baseline_status'] == 'fail' and result['candidate_status'] == 'pass'


@pytest.mark.skipif(not os.environ.get('AGENTLESS_DEEPSWE_REPOSITORIES'),
                    reason='opt-in sealed fd source fixture check')
def test_fd_recorded_patch_matches_pinned_source(tmp_path):
    spec = json.loads((EXPERIMENT / 'experiment.json').read_bytes())
    repository = Path(os.environ['AGENTLESS_DEEPSWE_REPOSITORIES']) / spec['task_id']
    verify_sealed_repository(repository, spec['base_commit'])
    provider = LocalGitWorkspaceProvider(repository, spec['base_commit'], tmp_path / 'workspaces')
    with provider.create() as workspace:
        sources = {p: (workspace.path / p).read_text(encoding='utf-8') for p in SOURCE_PATHS}
        adapter = get_language_adapter('rust')
        nodes = {p: adapter.parse_file(p, s) for p, s in sources.items()}
        locations = parse_locations_for_files(
            extract_code_blocks((EXPERIMENT / 'symbol_localization.txt').read_text()),
            tuple(sorted(SOURCE_PATHS)), extension=adapter.extensions)
        _, intervals = construct_selected_context(locations, nodes, sources)
        edits = parse_search_replace_edits((EXPERIMENT / 'repair_01_path_sort.txt').read_text())
        applied = apply_search_replace_edits(sources, edits, allowed_intervals=intervals)
        assert set(applied.changed_paths) == SOURCE_PATHS
    assert not list((tmp_path / 'workspaces').iterdir())


@pytest.mark.skipif(
    os.environ.get('AGENTLESS_FD_ISSUE_REPRODUCTION_DOCKER_TESTS') != '1'
    or not os.environ.get('AGENTLESS_DEEPSWE_REPOSITORIES')
    or not os.environ.get('AGENTLESS_DEEPSWE_TASKS_ROOT'),
    reason='opt-in real fd issue-derived Docker controller slice',
)
def test_fd_issue_controller_slice(tmp_path):
    tool = runpy.run_path(str(ROOT / 'tools/run_fd_path_sort_reproduction.py'))
    result = tool['run_slice'](tmp_path / 'fd-issue', Path(os.environ['AGENTLESS_DEEPSWE_TASKS_ROOT']),
                               Path(os.environ['AGENTLESS_DEEPSWE_REPOSITORIES']))
    assert result['baseline_status'] == 'fail' and result['candidate_status'] == 'pass'
    assert result['selected_candidate_id'] == 'repair-1' and result['model_calls'] == 0
