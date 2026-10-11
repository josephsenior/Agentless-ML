"""Recorded issue-derived Rust reproduction with a disclosed partial fd repair."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path
import subprocess
from xml.etree import ElementTree

from agentless_ml.adapters.benchmarks import DeepSWEDataset, DeepSWEDatasetPin, pinned_load_options
from agentless_ml.validation import DockerTestRunner, ReproductionSpec, rust_reproduction_command
from agentless_ml.validation.reproduction import parse_reproduction_source
from agentless_ml.workflow import FixedWorkflowController, RecordedStageResponses
from agentless_ml.workspace import verify_sealed_repository

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / 'experiments/deepswe/fd_path_sort_reproduction'


def responses() -> RecordedStageResponses:
    return RecordedStageResponses(
        file_localization=(EXPERIMENT / 'file_localization.txt').read_text(encoding='utf-8'),
        symbol_localization=(EXPERIMENT / 'symbol_localization.txt').read_text(encoding='utf-8'),
        repairs=tuple(p.read_text(encoding='utf-8') for p in sorted(EXPERIMENT.glob('repair_*.txt'))),
        reproduction_test=(EXPERIMENT / 'reproduction_test.txt').read_text(encoding='utf-8'),
        source='manually recorded from public instruction and sealed base source; partial path-sorting repair',
    )


def run_slice(output: Path, tasks_root: Path, repositories: Path) -> dict:
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
    revision = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, check=True,
                              capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(['git', 'status', '--porcelain'], cwd=ROOT, check=True,
                           capture_output=True, text=True).stdout.strip()
    revision += '+dirty' if dirty else ''
    result = FixedWorkflowController(
        task=task, source_repository=source, workspace_root=output / 'workspaces',
        artifact_root=output / 'runs', runner=runner, public_commands=(),
        reproduction_spec=ReproductionSpec(spec['reproduction_path'], rust_reproduction_command(
            spec['reproduction_path'], test_name=spec['test_name'], timeout_seconds=spec['timeout_seconds'])),
        implementation_revision=revision, harness_revision=pin['revision'],
        model_name='recorded/manual-fd-path-sort-partial',
    ).run(responses())
    assert result.prediction.selected_candidate_id == 'repair-1' and result.run.model_calls == 0
    return audit_existing(output, repositories)


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
    baseline = json.loads((directory / 'reproduction-baseline.json').read_bytes())
    assert baseline['checked_result']['status'] == 'fail'
    assert [a['status'] for a in attempts] == ['repair_error', 'validated']
    candidate = attempts[1]['candidate']
    assert candidate is not None
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
    assert len(reports) == 2
    for report in reports:
        data = json.loads(report.read_bytes())
        expected = 'failed' if report == baseline_report else 'passed'
        cases = data['results']['tests']
        assert len(cases) == 1 and cases[0]['name'] == spec['test_name']
        assert cases[0]['status'] == expected
        document = ElementTree.fromstring(base64.b64decode(data['rust_junit_base64'], validate=True))
        (entry,) = list(document.iter('testcase'))
        assert entry.attrib['name'] == spec['test_name']
        assert entry.find('error') is None and entry.find('skipped') is None
        assert (entry.find('failure') is not None) == (expected == 'failed')
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
    (output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--tasks-root', type=Path, required=True)
    parser.add_argument('--repositories', type=Path, required=True)
    parser.add_argument('--audit-existing', action='store_true', help='audit saved export without any Docker run')
    args = parser.parse_args()
    summary = (audit_existing(args.output, args.repositories) if args.audit_existing
               else run_slice(args.output, args.tasks_root, args.repositories))
    print(json.dumps(summary, indent=2))
