"""Inventory every pinned V2 task; execute only explicitly selected public plans.

No image pulls, repository fetches, model calls or held-out verifier reads.
Smoke checks are never promoted to full public-suite readiness.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import re
import subprocess
import uuid

from agentless_ml.adapters.benchmarks import (
    SWEbenchProDataset, SWEbenchProDatasetPin,
    SWEbenchProV2Dataset, SWEbenchProV2DatasetPin,
)
from agentless_ml.validation import DockerTestRunner, PublicTestCommand
from agentless_ml.validation.reports import TestReport
from agentless_ml.workspace import LocalGitWorkspaceProvider, verify_sealed_repository
from v2_go_public import GoPublicSuiteRunner, public_command
from v2_nodebb_public import NodeBBPublicSuiteRunner, public_command as nodebb_public_command

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = ROOT / 'experiments/swe_bench_pro'
MANIFEST = EXPERIMENTS / 'v2_public_plans.json'


def load_plans(path: Path) -> dict:
    manifest = json.loads(path.read_bytes())
    if manifest['schema_version'] != 1:
        raise ValueError('unsupported public-plan schema')
    plans = {}
    for entry in manifest['plans']:
        task_id = entry['instance_id']
        if task_id in plans or not re.fullmatch(r'[A-Za-z0-9_.-]+', task_id):
            raise ValueError('duplicate or unsafe task ID')
        source = (EXPERIMENTS / entry['source']).resolve(strict=True)
        if not source.is_relative_to(EXPERIMENTS.resolve()):
            raise ValueError('plan source must be in the reviewed experiment directory')
        spec = json.loads(source.read_bytes())
        if spec['instance_id'] != task_id:
            raise ValueError('public-plan source task differs')
        image = spec.get('image_id', spec.get('container_digest'))
        if not re.fullmatch(r'sha256:[0-9a-f]{64}', image or ''):
            raise ValueError('public plan requires an immutable image ID')
        scope = entry['scope']
        if scope not in ('syntax_only', 'selected_public_test', 'full_public_suite'):
            raise ValueError('unknown public-validation scope')
        regression = spec.get('regression') or {
            'argv': spec['regression_argv'],
            'timeout_seconds': spec['regression_timeout_seconds'],
        }
        runner_kind = spec.get('runner', 'declared-command')
        if runner_kind not in ('declared-command', 'go-public-suite-v1', 'nodebb-redis-public-v1'):
            raise ValueError('unknown public-plan runner')
        report = TestReport(**regression['report']) if regression.get('report') else None
        if scope == 'full_public_suite' and report is None:
            raise ValueError('full public-suite readiness requires individual test results')
        command = PublicTestCommand(tuple(regression['argv']),
                                    timeout_seconds=regression['timeout_seconds'], report=report)
        if runner_kind == 'go-public-suite-v1':
            if regression['argv'] != ['go', 'test', '-cover', '-v', './...']:
                raise ValueError('Go public runner requires the reviewed complete target')
            command = public_command(regression['timeout_seconds'])
        elif runner_kind == 'nodebb-redis-public-v1':
            if regression['argv'] != ['npm', 'test']:
                raise ValueError('NodeBB public runner requires the reviewed complete target')
            command = nodebb_public_command(regression['timeout_seconds'])
        plans[task_id] = dict(entry, image_id=image, base_commit=spec['base_commit'],
                             source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                             command=command, runner_kind=runner_kind)
    return plans


def readiness_status(scope, result):
    status = result.status.value
    if status not in ('pass', 'fail'):
        return status
    if scope != 'full_public_suite':
        return 'smoke_checked' if status == 'pass' else 'public_check_failed'
    return 'public_suite_ready' if any(case.status.value == 'passed' for case in result.test_cases) else 'no_passing_tests'


def check_image_base(image_id, base_commit, memory_mb):
    name = 'agentless-v2-probe-' + uuid.uuid4().hex
    try:
        result = subprocess.run([
            'docker', 'run', '--pull=never', '--rm', '--name', name,
            '--network', 'none', '--read-only', '--cap-drop', 'ALL',
            '--security-opt', 'no-new-privileges', '--memory', f'{memory_mb}m',
            '--memory-swap', f'{memory_mb}m', '--cpus', '1', '--pids-limit', '2048',
            '--entrypoint', 'git', image_id, '-C', '/app', 'rev-parse', 'HEAD',
        ], check=True, capture_output=True, text=True, timeout=60)
        if result.stdout.strip() != base_commit:
            raise ValueError('image /app revision differs from task base')
    finally:
        subprocess.run(['docker', 'rm', '--force', name], capture_output=True, timeout=30)


def survey_task(task, plan, *, selected, engine_error, repositories, workspace_root, artifacts):
    record = dict(task_id=task.instance_id, language=task.language, base_commit=task.base_commit,
                  model_calls=0, verifier_run=False, image_checked=False,
                  workspace_checked=False, public_check_executed=False)
    if plan is None:
        return dict(record, status='needs_public_plan')
    record.update(scope=plan['scope'], image_id=plan['image_id'],
                  plan_source=plan['source'], plan_source_sha256=plan['source_sha256'])
    if task.base_commit != plan['base_commit']:
        return dict(record, status='plan_mismatch')
    if not selected:
        return dict(record, status='configured_not_checked')
    if engine_error:
        return dict(record, status='docker_unavailable', message=engine_error)
    stage = 'image'
    try:
        runner_type = {
            'go-public-suite-v1': GoPublicSuiteRunner,
            'nodebb-redis-public-v1': NodeBBPublicSuiteRunner,
        }.get(plan.get('runner_kind'), DockerTestRunner)
        runner = runner_type(plan['image_id'], artifacts / task.instance_id,
                                  memory_mb=task.memory_megabytes, cpus=1,
                                  tmpfs_mb=4096, pids_limit=2048, run_as_image_user=True)
        if runner.image_id != plan['image_id']:
            raise ValueError('resolved image differs from pin')
        check_image_base(runner.image_id, task.base_commit, task.memory_megabytes)
        record['image_checked'] = True
        stage = 'repository'
        source = repositories / task.instance_id
        verify_sealed_repository(source, task.base_commit)
        stage = 'workspace'
        provider = LocalGitWorkspaceProvider(source, task.base_commit, workspace_root)
        with provider.create() as workspace:
            record['workspace_checked'] = True
            record['workspace_provenance'] = asdict(workspace.provenance)
            stage = 'public_check'
            execution = runner.run(workspace.path, plan['command'])
            record.update(public_check_executed=True, artifacts=execution.artifact_directory,
                          result=asdict(execution.result), message=execution.message)
            if isinstance(runner, GoPublicSuiteRunner):
                record['package_audit'] = runner.package_audit
                if not runner.package_audit['complete'] and execution.result.status.value in ('pass', 'fail'):
                    return dict(record, status='public_suite_incomplete')
            elif isinstance(runner, NodeBBPublicSuiteRunner):
                record['completion_audit'] = runner.completion_audit
                if not runner.completion_audit['complete'] and execution.result.status.value in ('pass', 'fail'):
                    return dict(record, status='public_suite_incomplete')
        return dict(record, status=readiness_status(plan['scope'], execution.result))
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
        return dict(record, status=f'{stage}_blocked', message=str(error)[:2000])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--v1-parquet', type=Path, required=True)
    parser.add_argument('--v2-tasks', type=Path, required=True)
    parser.add_argument('--plans', type=Path, default=MANIFEST)
    parser.add_argument('--output', type=Path, required=True, help='new directory for this survey')
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--task-id', action='append', default=[])
    parser.add_argument('--repositories', type=Path)
    parser.add_argument('--workspace-root', type=Path)
    args = parser.parse_args()
    if args.execute and (not args.task_id or args.repositories is None or args.workspace_root is None):
        parser.error('--execute requires explicit task IDs, repositories and workspace root')
    pin_path = EXPERIMENTS / 'v2_corpus_pin.json'
    pin = json.loads(pin_path.read_bytes())
    plans = load_plans(args.plans)
    dataset = SWEbenchProV2Dataset(args.v2_tasks, SWEbenchProV2DatasetPin(
        pin['v2_dataset_revision'], pin['v2_visible_files_sha256'], pin['v2_task_count']),
        SWEbenchProDataset(args.v1_parquet, SWEbenchProDatasetPin(
            pin['v1_dataset_revision'], pin['v1_parquet_sha256'], pin['v1_row_count'])))
    tasks = dataset.load_tasks(container_digests={key: plan['image_id'] for key, plan in plans.items()})
    unknown = (set(plans) | set(args.task_id)) - {task.instance_id for task in tasks}
    if unknown:
        parser.error(f'unknown task IDs: {sorted(unknown)}')
    if args.execute and set(args.task_id) - set(plans):
        parser.error('execution needs a reviewed public plan for every selected task')
    args.output.mkdir(parents=True, exist_ok=False)
    engine_error = None
    if args.execute:
        try:
            engine = subprocess.run(['docker', 'info', '--format', '{{.OSType}}'],
                                    capture_output=True, text=True, timeout=30, check=True)
            if engine.stdout.strip() != 'linux':
                engine_error = 'Docker Linux engine required'
        except (OSError, subprocess.SubprocessError) as error:
            engine_error = str(error)
    records = []
    with (args.output / 'survey.jsonl').open('x', encoding='utf-8') as journal:
        for task in tasks:
            record = survey_task(task, plans.get(task.instance_id),
                                 selected=args.execute and task.instance_id in args.task_id,
                                 engine_error=engine_error, repositories=args.repositories,
                                 workspace_root=args.workspace_root, artifacts=args.output / 'executions')
            records.append(record)
            journal.write(json.dumps(record, default=str) + '\n')
            journal.flush()
    summary = dict(generated_at=datetime.now(UTC).isoformat(), benchmark_revision=pin['v2_dataset_revision'],
                   corpus_pin_sha256=hashlib.sha256(pin_path.read_bytes()).hexdigest(),
                   plans_sha256=hashlib.sha256(args.plans.read_bytes()).hexdigest(),
                   tasks=len(records), statuses=dict(Counter(r['status'] for r in records)),
                   model_calls=0, verifier_run=False, official_score=False)
    (args.output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
