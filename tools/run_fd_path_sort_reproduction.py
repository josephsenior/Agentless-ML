"""Recorded fd reproduction and partial repair, optionally with public regressions."""

from __future__ import annotations

import argparse
import base64
from collections import Counter
from dataclasses import asdict
from datetime import datetime
import hashlib
import json
from pathlib import Path
import subprocess
from xml.etree import ElementTree

from agentless_ml.adapters.benchmarks import (
    DeepSWEDataset, DeepSWEDatasetPin, deepswe_test_plan, load_test_overrides, pinned_load_options,
)
from agentless_ml.validation import (
    DockerTestRunner, RegressionTest, ReportFormat, ReproductionSpec, parse_report,
    rust_reproduction_command,
)
from agentless_ml.validation.reproduction import parse_reproduction_source
from agentless_ml.workflow import FixedWorkflowController, RecordedStageResponses
from agentless_ml.workspace import LocalGitWorkspaceProvider, verify_sealed_repository

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / 'experiments/deepswe/fd_path_sort_reproduction'
SAMPLE_EXPERIMENT = ROOT / 'experiments/deepswe/fd_reproduction_samples/experiment.json'


def sample_responses() -> tuple[str, ...]:
    manifest = json.loads(SAMPLE_EXPERIMENT.read_bytes())
    return tuple((ROOT / entry['response_file']).read_text(encoding='utf-8')
                 for entry in manifest['inputs'])


def responses(*, with_public_regressions: bool = False,
              multiple_reproduction_samples: bool = False) -> RecordedStageResponses:
    return RecordedStageResponses(
        file_localization=(EXPERIMENT / 'file_localization.txt').read_text(encoding='utf-8'),
        symbol_localization=(EXPERIMENT / 'symbol_localization.txt').read_text(encoding='utf-8'),
        repairs=tuple(p.read_text(encoding='utf-8') for p in sorted(EXPERIMENT.glob('repair_*.txt'))),
        reproduction_test=None if multiple_reproduction_samples else (
            EXPERIMENT / 'reproduction_test.txt').read_text(encoding='utf-8'),
        reproduction_samples=sample_responses() if multiple_reproduction_samples else (),
        regression_exclusions='' if with_public_regressions else None,
        source='manually recorded from public instruction and sealed base source; partial path-sorting repair',
    )


def run_slice(output: Path, tasks_root: Path, repositories: Path,
              *, with_public_regressions: bool = False,
              multiple_reproduction_samples: bool = False) -> dict:
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    spec = json.loads((EXPERIMENT / 'experiment.json').read_bytes())
    pin = json.loads((ROOT / 'experiments/deepswe/corpus_pin.json').read_bytes())
    dataset = DeepSWEDataset(tasks_root, DeepSWEDatasetPin(
        revision=pin['revision'], agent_files_sha256=pin['agent_files_sha256'], task_count=pin['task_count']))
    (task,) = dataset.load_tasks(task_ids=(spec['task_id'],), **pinned_load_options(pin))
    assert task.base_commit == spec['base_commit']
    source = repositories / task.instance_id
    verify_sealed_repository(source, task.base_commit)
    runner = DockerTestRunner(task.container_image, output / 'executions', memory_mb=spec['memory_mb'],
                              cpus=spec['cpus'], tmpfs_mb=spec['tmpfs_mb'], pids_limit=spec['pids_limit'],
                              run_as_image_user=True)
    assert runner.image_id == task.container_digest
    regression_tests = ()
    if with_public_regressions:
        overrides = load_test_overrides(ROOT / 'experiments/deepswe/test_overrides.json')
        with LocalGitWorkspaceProvider(source, task.base_commit, output / 'workspaces').create() as checkout:
            plan = deepswe_test_plan(task.language, checkout.path, overrides.get(task.instance_id))
        command = plan.command(timeout_seconds=spec['timeout_seconds'])
        regression_tests = (RegressionTest('fd-public-suite', command),)
        (output / 'public-regression-plan.json').write_text(json.dumps({
            'plan': asdict(plan), 'command': asdict(command), 'recorded_exclusions': '',
        }, indent=2) + '\n', encoding='utf-8')
        print('Combined run: ' + ('four sample baselines, ' if multiple_reproduction_samples
                                 else 'reproduction baseline, ') + 'full public baseline, '
              'candidate full public suite, candidate reproduction. No manual exclusions.', flush=True)
    revision = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, check=True,
                              capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(['git', 'status', '--porcelain'], cwd=ROOT, check=True,
                           capture_output=True, text=True).stdout.strip()
    revision += '+dirty' if dirty else ''
    result = FixedWorkflowController(
        task=task, source_repository=source, workspace_root=output / 'workspaces',
        artifact_root=output / 'runs', runner=runner, public_commands=(),
        regression_tests=regression_tests,
        reproduction_spec=ReproductionSpec(spec['reproduction_path'], rust_reproduction_command(
            spec['reproduction_path'], test_name=spec['test_name'], timeout_seconds=spec['timeout_seconds'])),
        implementation_revision=revision, harness_revision=pin['revision'],
        model_name='recorded/manual-fd-path-sort-partial',
    ).run(responses(with_public_regressions=with_public_regressions,
                    multiple_reproduction_samples=multiple_reproduction_samples))
    assert result.prediction.selected_candidate_id == 'repair-1' and result.run.model_calls == 0
    return audit_existing(output, repositories)


def audit_regressions(directory: Path, regression: dict) -> dict:
    """Check the frozen counted IDs against both complete, unfiltered reports."""
    (baseline,) = json.loads((directory / 'regression-baseline.json').read_bytes())
    selection = json.loads((directory / 'regression-selection.json').read_bytes())
    base_result = baseline['result']
    assert base_result['kind'] == regression['kind'] == 'regression'
    assert base_result['status'] in {'pass', 'fail'} and regression['status'] in {'pass', 'fail'}
    assert base_result['command'] == regression['command']
    base_report = Path(baseline['artifact_directory']) / 'report.xml'
    records = [json.loads(p.read_bytes()) for p in (directory / 'executions').rglob('execution.json')]
    (candidate_execution,) = [r for r in records if r['result']['kind'] == 'regression']
    assert candidate_execution['result'] == regression
    candidate_report = Path(candidate_execution['artifact_directory']) / 'report.xml'
    for report, result in ((base_report, base_result), (candidate_report, regression)):
        parsed = [asdict(case) for case in parse_report(report.read_bytes(), ReportFormat.JUNIT_XML)]
        assert parsed == result['test_cases'], 'raw JUnit differs from saved test outcomes'
        assert len(parsed) == 241, 'the complete pinned public inventory must run'
        assert not any('issue_path_sort' in case['test_id'] for case in parsed)
    passing = [case['test_id'] for case in base_result['test_cases'] if case['status'] == 'passed']
    assert selection['response'] == '' and selection['excluded_ids'] == []
    assert selection['passing_ids'] == selection['selected_ids'] == passing
    assert regression['counted_test_ids'] == passing
    before = {case['test_id']: case['status'] for case in base_result['test_cases']}
    after = {case['test_id']: case['status'] for case in regression['test_cases']}
    assert before.keys() == after.keys(), 'candidate changed the public test inventory'
    new_failures = [test_id for test_id in passing if after.get(test_id) != 'passed']
    return {
        'baseline_raw_status': base_result['status'], 'candidate_raw_status': regression['status'],
        'baseline_counts': dict(Counter(before.values())),
        'candidate_counts': dict(Counter(after.values())),
        'counted_baseline_passing': len(passing), 'manual_exclusions': [],
        'new_regressions': new_failures,
        'baseline_nonpassing_ids': [test_id for test_id, status in before.items() if status != 'passed'],
        'same_test_ids_and_outcomes': before == after,
        'baseline_duration_seconds': base_result['duration_seconds'],
        'candidate_duration_seconds': regression['duration_seconds'],
    }


def audit_sample_pool(directory: Path, *, require_candidate_validation: bool = True
                      ) -> tuple[dict, dict, dict[Path, str]]:
    """Verify eligibility, exact-source majority and selection before repair checks."""
    manifest = json.loads(SAMPLE_EXPERIMENT.read_bytes())
    samples = sample_responses()
    attempts = json.loads((directory / 'reproduction-attempts.json').read_bytes())
    selection_path = directory / 'reproduction-selection.json'
    selection = json.loads(selection_path.read_bytes())
    assert [entry['sample_index'] for entry in attempts] == list(range(len(samples)))
    assert [entry['status'] for entry in attempts] == [e['expected_status'] for e in manifest['inputs']]
    assert selection['eligible_sample_indices'] == manifest['expected_eligible_indices']
    assert selection['selected_sample_index'] == manifest['expected_selected_index']
    assert selection['vote_count'] == manifest['expected_vote_count']
    assert selection['voting_key'] == manifest['voting_key']
    eligible = {}
    baselines = {}
    report_outcomes = {}
    for index, attempt in enumerate(attempts):
        sample_directory = directory / 'reproduction-samples' / str(index)
        if attempt['status'] == 'parse_error':
            assert not (sample_directory / 'source.json').exists()
            assert not (sample_directory / 'reproduction-baseline').exists()
            continue
        source = parse_reproduction_source(samples[index], 'rust')
        frozen = json.loads((sample_directory / 'source.json').read_bytes())
        assert frozen['source'] == source
        assert frozen['source_sha256'] == hashlib.sha256(source.encode()).hexdigest()
        baseline = json.loads((sample_directory / 'baseline.json').read_bytes())
        assert baseline['checked_result']['status'] == attempt['status']
        assert baseline['checked_result']['kind'] == 'reproduction'
        baselines[index] = baseline
        report_outcomes[Path(baseline['artifact_directory']) / 'report.json'] = (
            'failed' if attempt['status'] == 'fail' else 'passed')
        if attempt['status'] == 'fail':
            eligible[index] = source
    counts = Counter(eligible.values())
    winner = max(eligible, key=lambda index: (counts[eligible[index]], -index))
    assert winner == selection['selected_sample_index']
    assert counts[eligible[winner]] == selection['vote_count']
    frozen = json.loads((directory / 'reproduction-source.json').read_bytes())
    assert frozen['source'] == eligible[winner]
    assert frozen['source_sha256'] == selection['source_sha256']
    selected_at = selection_path.stat().st_mtime
    # A provenance sanity check in addition to the controller's fixed code order.
    candidate_records = list((directory / 'executions').rglob('candidate.json'))
    if require_candidate_validation:
        assert candidate_records
    for path in candidate_records:
        candidate = json.loads(path.read_bytes())
        assert selected_at <= datetime.fromisoformat(candidate['workspace']['created_at']).timestamp()
    return ({**selection, 'attempt_statuses': [a['status'] for a in attempts],
             'selection_before_candidate_validation': True if candidate_records else None,
             'candidate_validation_observed': bool(candidate_records),
             'intentional_duplicate_control': True}, baselines[winner], report_outcomes)


def audit_reproduction_report(report: Path, spec: dict, expected: str):
    data = json.loads(report.read_bytes())
    cases = data['results']['tests']
    assert len(cases) == 1 and cases[0]['name'] == spec['test_name']
    assert cases[0]['status'] == expected
    document = ElementTree.fromstring(base64.b64decode(data['rust_junit_base64'], validate=True))
    (entry,) = list(document.iter('testcase'))
    assert entry.attrib['name'] == spec['test_name']
    assert entry.find('error') is None and entry.find('skipped') is None
    assert (entry.find('failure') is not None) == (expected == 'failed')
    return entry


def audit_selection_checkpoint(output: Path, repositories: Path) -> dict:
    """Audit completed sample selection only; never imply an interrupted run exported."""
    output = output.resolve()
    (directory,) = (output / 'runs').iterdir()
    assert not (directory / 'prediction.json').exists(), 'use the complete-run audit for a saved prediction'
    sample_summary, _, report_outcomes = audit_sample_pool(directory, require_candidate_validation=False)
    assert sample_summary['candidate_validation_observed'] is False
    spec = json.loads((EXPERIMENT / 'experiment.json').read_bytes())
    pin = json.loads((ROOT / 'experiments/deepswe/corpus_pin.json').read_bytes())
    image = pin['container_digests'][spec['task_id']]
    records = []
    for report, expected in report_outcomes.items():
        entry = audit_reproduction_report(report, spec, expected)
        if expected == 'failed':
            detail = ''.join(entry.itertext())
            assert '--sort' in detail and 'unexpected argument' in detail
        execution = json.loads((report.parent / 'execution.json').read_bytes())
        assert execution['image_id'] == image
        assert execution['result']['status'] == ('fail' if expected == 'failed' else 'pass')
        for key in ('memory_mb', 'cpus', 'tmpfs_mb', 'pids_limit', 'timeout_seconds'):
            assert execution['limits'][key] == spec[key]
        records.append({'report': report.relative_to(directory).as_posix(),
                        'status': execution['result']['status'],
                        'duration_seconds': execution['result']['duration_seconds']})
    assert len(records) == 4
    verify_sealed_repository(repositories / spec['task_id'], spec['base_commit'])
    summary = {
        'scope': 'verified real Rust sample-selection checkpoint; full controller run incomplete',
        'artifact_directory': str(directory), 'task_id': spec['task_id'],
        'base_commit': spec['base_commit'], 'container_digest': image,
        'sample_selection': sample_summary, 'completed_sample_executions': records,
        'report_sha256': {p.relative_to(directory).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in report_outcomes},
        'model_calls': 0, 'source_unchanged': True,
        'prediction_exported': False, 'candidate_validation_completed': False,
        'public_regression_completed': False,
        'retained_workspace_directories': [p.name for p in (output / 'workspaces').iterdir()],
        'held_out_verifier_run': False, 'deepswe_readiness_unchanged': '109/113',
    }
    (output / 'selection-checkpoint-summary.json').write_text(
        json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    return summary


def audit_existing(output: Path, repositories: Path) -> dict:
    """Audit saved evidence without rerunning Docker or changing candidates."""
    output = output.resolve()
    spec = json.loads((EXPERIMENT / 'experiment.json').read_bytes())
    pin = json.loads((ROOT / 'experiments/deepswe/corpus_pin.json').read_bytes())
    (directory,) = (output / 'runs').iterdir()
    task = json.loads((directory / 'task.json').read_bytes())
    run = json.loads((directory / 'run.json').read_bytes())
    attempts = json.loads((directory / 'attempts.json').read_bytes())
    assert task['benchmark'] == 'deepswe' and task['instance_id'] == spec['task_id']
    assert task['base_commit'] == spec['base_commit']
    assert task['container_digest'] == pin['container_digests'][spec['task_id']]
    assert run['container_digest'] == task['container_digest'] and run['model_calls'] == 0
    source = repositories / task['instance_id']
    multiple_samples = (directory / 'reproduction-selection.json').exists()
    sample_summary = None
    report_outcomes = {}
    if multiple_samples:
        sample_summary, baseline, report_outcomes = audit_sample_pool(directory)
    else:
        baseline = json.loads((directory / 'reproduction-baseline.json').read_bytes())
    assert baseline['checked_result']['status'] == 'fail'
    assert [a['status'] for a in attempts] == ['repair_error', 'validated']
    candidate = attempts[1]['candidate']
    assert candidate is not None
    combined = (directory / 'regression-selection.json').exists()
    regression_summary = None
    if combined:
        regression, reproduction = candidate['validation']
        assert reproduction['kind'] == 'reproduction' and reproduction['status'] == 'pass'
        regression_summary = audit_regressions(directory, regression)
        original = json.loads((ROOT / 'experiments/reproduction/fd_issue_2026-10-11.json').read_bytes())
        assert run['final_patch_sha256'] == original['final_patch_sha256']
    else:
        assert [v['status'] for v in candidate['validation']] == ['pass']
    baseline_report = Path(baseline['artifact_directory']) / 'report.json'
    raw_baseline = json.loads(baseline_report.read_bytes())
    junit = ElementTree.fromstring(base64.b64decode(raw_baseline['rust_junit_base64'], validate=True))
    # Establish why it failed: the requested CLI option is absent on the base.
    (case,) = list(junit.iter('testcase'))
    assert case.attrib['name'] == spec['test_name'] and case.find('failure') is not None
    # Nextest puts the panic detail in testcase/system-err, not failure text.
    failure_text = ''.join(case.itertext())
    assert '--sort' in failure_text and 'unexpected argument' in failure_text
    reports = list(directory.rglob('report.json'))
    assert len(reports) == (len(report_outcomes) + 1 if multiple_samples else 2)
    for report in reports:
        expected = (report_outcomes.get(report, 'passed') if multiple_samples else
                    'failed' if report == baseline_report else 'passed')
        entry = audit_reproduction_report(report, spec, expected)
        if multiple_samples and expected == 'failed':
            assert '--sort' in ''.join(entry.itertext()) and 'unexpected argument' in ''.join(entry.itertext())
    prediction = json.loads((directory / 'prediction.json').read_bytes())
    assert prediction['instance_id'] == task['instance_id']
    assert prediction['selected_candidate_id'] == 'repair-1'
    assert prediction['model_patch'] == candidate['diff']
    patch = prediction['model_patch']
    assert 'tests/' not in patch and 'Cargo.toml' not in patch
    assert set(line.split(' b/')[1] for line in patch.splitlines() if line.startswith('diff --git ')) == {
        'src/cli.rs', 'src/config.rs', 'src/main.rs', 'src/walk.rs'}
    assert hashlib.sha256(patch.encode()).hexdigest() == run['final_patch_sha256']
    frozen = json.loads((directory / 'reproduction-source.json').read_bytes())
    assert frozen['source'] == parse_reproduction_source(responses().reproduction_test, 'rust')
    assert frozen['source_sha256'] == hashlib.sha256(frozen['source'].encode()).hexdigest()
    verify_sealed_repository(source, task['base_commit'])
    assert not (source / spec['reproduction_path']).exists()
    assert not list((output / 'workspaces').iterdir())
    summary = {
        'scope': spec['purpose'], 'coverage': spec['coverage'], 'not_implemented': spec['not_implemented'],
        'regression_scope': spec['regression_scope'], 'artifact_directory': str(directory),
        'task_id': task['instance_id'], 'base_commit': task['base_commit'],
        'container_digest': task['container_digest'], 'implementation_revision': run['implementation_revision'],
        'baseline_status': 'fail', 'baseline_reason': 'requested --sort option absent on pinned base',
        'candidate_status': 'pass', 'selected_candidate_id': 'repair-1',
        'model_calls': 0, 'wall_time_seconds': run['wall_time_seconds'],
        'reproduction_source_sha256': frozen['source_sha256'],
        'final_patch_sha256': run['final_patch_sha256'],
        'report_sha256': {p.relative_to(directory).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in reports},
        'source_unchanged': True, 'candidate_workspaces_cleaned': True,
    }
    if combined:
        summary['baseline_reproduction_status'] = summary.pop('baseline_status')
        summary['baseline_reproduction_reason'] = summary.pop('baseline_reason')
        summary['candidate_reproduction_status'] = summary.pop('candidate_status')
        public_reports = list(directory.rglob('report.xml'))
        assert len(public_reports) == 2
        selection = json.loads((directory / 'selection.json').read_bytes())
        assert selection['reason'] == 'best_regression_then_reproduction_passed_then_normalized_majority'
        summary.update({
            'regression_scope': 'combined recorded controller run with the unchanged full public suite',
            'public_regression': regression_summary, 'selection_reason': selection['reason'],
            'docker_executions': len(reports) + len(public_reports), 'held_out_verifier_run': False,
            'deepswe_readiness_unchanged': '109/113',
        })
        summary['report_sha256'].update({
            p.relative_to(directory).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in public_reports})
    if multiple_samples:
        summary['sample_selection'] = sample_summary
    (output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--tasks-root', type=Path, required=True)
    parser.add_argument('--repositories', type=Path, required=True)
    parser.add_argument('--audit-existing', action='store_true', help='audit saved export without any Docker run')
    parser.add_argument('--with-public-regressions', action='store_true',
                        help='also run and count the existing public suite via the regression inventory')
    parser.add_argument('--multiple-reproduction-samples', action='store_true',
                        help='use the recorded sample pool with eligibility and exact-source voting controls')
    parser.add_argument('--audit-selection-only', action='store_true',
                        help='audit a completed selection checkpoint without claiming validation/export or running Docker')
    args = parser.parse_args()
    if args.audit_existing and args.audit_selection_only:
        parser.error('choose either complete-run audit or selection-only audit')
    summary = (audit_selection_checkpoint(args.output, args.repositories) if args.audit_selection_only else
               audit_existing(args.output, args.repositories) if args.audit_existing
               else run_slice(args.output, args.tasks_root, args.repositories,
                              with_public_regressions=args.with_public_regressions,
                              multiple_reproduction_samples=args.multiple_reproduction_samples))
    print(json.dumps(summary, indent=2))
