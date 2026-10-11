"""Run fd's unchanged public suite against its already-exported partial repair.

No model call, generated reproduction overlay, target filtering or patch rewrite.
The saved reproduction evidence pins the prediction; use a fresh output directory.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import subprocess

from agentless_ml.adapters.benchmarks import (
    DeepSWEDataset, DeepSWEDatasetPin, deepswe_test_plan,
    load_test_overrides, pinned_load_options,
)
from agentless_ml.repair import build_patch_candidate
from agentless_ml.validation import DockerTestRunner
from agentless_ml.workspace import (
    LocalGitWorkspaceProvider, PatchApplicationStatus, verify_sealed_repository,
)

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'experiments/reproduction/fd_issue_2026-10-11.json'
SPEC = ROOT / 'experiments/deepswe/fd_path_sort_reproduction/experiment.json'
SOURCE_PATHS = {'src/cli.rs', 'src/config.rs', 'src/main.rs', 'src/walk.rs'}


def load_export(prediction: Path, evidence: dict):
    """Refuse a different task, selected candidate or patch, before Docker starts."""
    record = json.loads(prediction.read_bytes())
    if (record['instance_id'] != evidence['task_id']
            or record['selected_candidate_id'] != evidence['selected_candidate_id']):
        raise ValueError('prediction does not match the recorded fd selection')
    patch = record['model_patch']
    if hashlib.sha256(patch.encode('utf-8')).hexdigest() != evidence['final_patch_sha256']:
        raise ValueError('exported patch differs from the recorded repair')
    candidate = build_patch_candidate(
        candidate_id=record['selected_candidate_id'], raw_response='existing exported prediction',
        diff=patch, localization_rank=0, sample_index=1, language='rust')
    if candidate.diff != patch:
        raise ValueError('exported patch would be rewritten')
    return candidate


def run_suite(output: Path, prediction: Path, tasks_root: Path, repositories: Path,
              *, baseline: bool = False) -> dict:
    evidence = json.loads(EVIDENCE.read_bytes())
    spec = json.loads(SPEC.read_bytes())
    candidate = load_export(prediction, evidence)
    pin = json.loads((ROOT / 'experiments/deepswe/corpus_pin.json').read_bytes())
    dataset = DeepSWEDataset(tasks_root, DeepSWEDatasetPin(
        revision=pin['revision'], agent_files_sha256=pin['agent_files_sha256'],
        task_count=pin['task_count']))
    (task,) = dataset.load_tasks(task_ids=(evidence['task_id'],), **pinned_load_options(pin))
    if (task.base_commit != evidence['base_commit']
            or task.container_digest != evidence['container_digest']):
        raise ValueError('task pins differ from the reproduction run')
    source = repositories / task.instance_id
    verify_sealed_repository(source, task.base_commit)
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    limits = {key: spec[key] for key in ('memory_mb', 'cpus', 'tmpfs_mb', 'pids_limit')}
    runner = DockerTestRunner(task.container_image, output / 'executions',
                              run_as_image_user=True, **limits)
    if runner.image_id != task.container_digest:
        raise ValueError('Docker image differs from its pinned digest')
    overrides = load_test_overrides(ROOT / 'experiments/deepswe/test_overrides.json')
    provider = LocalGitWorkspaceProvider(source, task.base_commit, output / 'workspaces')
    revision = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, check=True,
                              capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(['git', 'status', '--porcelain'], cwd=ROOT, check=True,
                           capture_output=True, text=True).stdout.strip()
    with provider.create() as workspace:
        # Freeze the existing whole-suite plan on the pristine base, not candidate code.
        plan = deepswe_test_plan(task.language, workspace.path, overrides.get(task.instance_id))
        command = plan.command(timeout_seconds=spec['timeout_seconds'])
        application = None if baseline else workspace.apply_candidate(candidate)
        if application is not None and (
                application.status is not PatchApplicationStatus.APPLIED
                or set(application.changed_paths) != SOURCE_PATHS):
            raise ValueError(f'expected only the four exported source changes: {application}')
        if (workspace.path / spec['reproduction_path']).exists():
            raise ValueError('generated reproduction must not enter the public suite')
        provenance = asdict(workspace.provenance)
        print(f'{task.instance_id} [{"unpatched control" if baseline else "exported repair"}]: '
              f'{plan.runner}, targets={plan.targets}, '
              f'timeout={command.timeout_seconds}s, limits={limits}', flush=True)
        execution = runner.run(workspace.path, command)
    verify_sealed_repository(source, task.base_commit)
    cleaned = not any((output / 'workspaces').iterdir())
    result = execution.result
    artifacts = Path(execution.artifact_directory)
    summary = {
        'scope': 'existing full public nextest schedule; not a task score',
        'condition': 'unpatched control' if baseline else 'exported partial repair',
        'task_id': task.instance_id, 'base_commit': task.base_commit,
        'container_digest': runner.image_id, 'implementation_revision': revision + ('+dirty' if dirty else ''),
        'prediction_path': str(prediction.resolve()),
        'prediction_sha256': hashlib.sha256(prediction.read_bytes()).hexdigest(),
        'related_export_patch_sha256': candidate.diff_sha256,
        'patch_sha256': None if baseline else candidate.diff_sha256,
        'selected_candidate_id': None if baseline else candidate.candidate_id,
        'plan': asdict(plan), 'command': asdict(command), 'limits': limits,
        'workspace': provenance, 'application': None if baseline else asdict(application),
        'execution_artifacts': str(artifacts), 'result': asdict(result),
        'counts': dict(Counter(case.status.value for case in result.test_cases)),
        'message': execution.message,
        'artifact_sha256': {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                            for path in sorted(artifacts.iterdir()) if path.is_file()},
        'model_calls': 0, 'generated_reproduction_included': False,
        'held_out_verifier_run': False, 'source_unchanged': True,
        'candidate_workspaces_cleaned': cleaned, 'deepswe_readiness_unchanged': '109/113',
    }
    (output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    print(f'{result.status.value}: {summary["counts"]}, {result.duration_seconds:.1f}s', flush=True)
    print(f'Artifacts: {output}', flush=True)
    if not cleaned:
        raise RuntimeError('candidate workspace cleanup incomplete; evidence saved')
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prediction', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--tasks-root', type=Path, required=True)
    parser.add_argument('--repositories', type=Path, required=True)
    parser.add_argument('--baseline', action='store_true',
                        help='run an unpatched control with the identical plan and limits')
    args = parser.parse_args()
    summary = run_suite(args.output, args.prediction, args.tasks_root, args.repositories,
                        baseline=args.baseline)
    return 0 if summary['result']['status'] == 'pass' else 1


if __name__ == '__main__':
    raise SystemExit(main())
