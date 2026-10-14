"""Cheap corpus inventory plus a bounded repository-balanced local-image pilot.

No pulls, model calls, reference solutions, verifier reads or full test suites.
"""
import argparse
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import tempfile

from agentless_ml.adapters.benchmarks import (
    SWEbenchProDataset, SWEbenchProDatasetPin, SWEbenchProV2Dataset, SWEbenchProV2DatasetPin,
)
from agentless_ml.validation import DockerTestRunner, PublicTestCommand
from survey_swe_bench_pro_v2 import ROOT, load_plans, MANIFEST, survey_task

PARKED_REPO = 'https://github.com/NodeBB/NodeBB'
PARKED_EVIDENCE = 'v2_js_nodebb_upload_path/no-bail-diagnostic-2026-10-14.json'


def is_parked(task):
    return task.repository_url.rstrip('/').removesuffix('.git').casefold() == PARKED_REPO.casefold()


def choose_pilot(tasks, local_images, plans, size):
    if not 1 <= size <= 11:
        raise ValueError('pilot size must be between 1 and 11 repositories')
    groups = defaultdict(list)
    for task in tasks:
        if not is_parked(task):
            groups[task.repository_url].append(task)
    candidates = []
    for group in groups.values():
        candidates.append(sorted(group, key=lambda task: (
            -(task.container_image in local_images and task.instance_id in plans),
            -(task.container_image in local_images), task.instance_id))[0])
    selected, languages = [], set()
    while candidates and len(selected) < size:
        candidate = sorted(candidates, key=lambda task: (
            -(task.language not in languages), -(task.container_image in local_images),
            -(task.instance_id in plans), task.repository_url, task.instance_id))[0]
        candidates.remove(candidate)
        selected.append(candidate)
        languages.add(candidate.language)
    return selected


def local_images():
    result = subprocess.run(['docker', 'image', 'ls', '--no-trunc', '--format', '{{json .}}'],
                            capture_output=True, text=True, timeout=30, check=True)
    images = {}
    for line in result.stdout.splitlines():
        row = json.loads(line)
        if row['Repository'] != '<none>' and row['Tag'] != '<none>':
            images[row['Repository'] + ':' + row['Tag']] = row['ID']
    return images


def workspace_probe_command(task):
    # Trusted git archive only: no package scripts, tests or candidate code.
    script = (
        'set -e; repository=; '
        'for directory in /app /testbed; do '
        'if git -C "$directory" rev-parse --verify HEAD >/dev/null 2>&1; then '
        'repository="$directory"; break; fi; done; test -n "$repository"; '
        'observed=$(git -C "$repository" rev-parse HEAD); '
        'test "$observed" = ' + shlex.quote(task.base_commit) + '; '
        'git -C "$repository" archive --format=tar --output=/tmp/base.tar HEAD; '
        'mkdir /tmp/provisioned; tar --no-same-owner -xf /tmp/base.tar -C /tmp/provisioned; '
        'mktemp /tmp/provisioned/.agentless-write-XXXXXX; '
        'test ! -e /tmp/provisioned/.git; '
        'du -sk /tmp/provisioned; '
        'find /tmp/provisioned -type f | wc -l'
    )
    return PublicTestCommand(('sh', '-c', script), timeout_seconds=120)


def pilot_task(task, images, plans, repositories, output):
    record = dict(task_id=task.instance_id, repository=task.repository_url, language=task.language,
                  base_commit=task.base_commit, full_suite_ready=False,
                  public_check_executed=False, model_calls=0, verifier_run=False)
    image = images.get(task.container_image)
    if image is None:
        return dict(record, status='needs_local_image', required_image=task.container_image)
    record['image_id'] = image
    plan = plans.get(task.instance_id)
    if plan and image != plan['image_id']:
        return dict(record, status='image_pin_mismatch')
    try:
        runner = DockerTestRunner(image, output / 'workspace-probes' / task.instance_id,
                                  memory_mb=task.memory_megabytes, cpus=1, tmpfs_mb=4096,
                                  pids_limit=2048, run_as_image_user=True,
                                  execution_phase='setup', network_mode='none')
        with tempfile.TemporaryDirectory(prefix='agentless-batch-probe-') as temporary:
            execution = runner.run(Path(temporary), workspace_probe_command(task))
        record['workspace_probe'] = asdict(execution)
        if execution.result.status.value != 'pass':
            return dict(record, status='workspace_probe_blocked')
        if plan is None:
            return dict(record, status='workspace_probe_passed_needs_public_plan')
        if plan['scope'] == 'full_public_suite':
            return dict(record, status='workspace_probe_passed_full_suite_not_in_pilot')
        smoke = survey_task(task, plan, selected=True, engine_error=None,
                            repositories=repositories,
                            workspace_root=Path(tempfile.gettempdir()) / 'agentless-v2-survey-workspaces',
                            artifacts=output / 'smokes')
        return dict(record, status=smoke['status'], public_check_executed=smoke['public_check_executed'],
                    smoke=smoke)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        return dict(record, status='provisioning_error', message=str(error)[:2000])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--v1-parquet', type=Path, required=True)
    parser.add_argument('--v2-tasks', type=Path, required=True)
    parser.add_argument('--repositories', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--pilot-size', type=int, default=5)
    parser.add_argument('--execute-pilot', action='store_true')
    args = parser.parse_args()
    if not 1 <= args.pilot_size <= 11:
        parser.error('--pilot-size must be between 1 and 11')
    pin_path = ROOT / 'experiments/swe_bench_pro/v2_corpus_pin.json'
    pin = json.loads(pin_path.read_bytes())
    tasks = SWEbenchProV2Dataset(args.v2_tasks, SWEbenchProV2DatasetPin(
        pin['v2_dataset_revision'], pin['v2_visible_files_sha256'], pin['v2_task_count']),
        SWEbenchProDataset(args.v1_parquet, SWEbenchProDatasetPin(
            pin['v1_dataset_revision'], pin['v1_parquet_sha256'], pin['v1_row_count']))).load_tasks()
    plans = load_plans(MANIFEST)
    engine_error = None
    try:
        images = local_images()
    except (OSError, subprocess.SubprocessError) as error:
        images, engine_error = {}, str(error)[:1000]
    inventory = [dict(task_id=t.instance_id, repository=t.repository_url, language=t.language,
                      base_commit=t.base_commit, required_image=t.container_image,
                      local_image_id=images.get(t.container_image),
                      host_repository_present=(args.repositories / t.instance_id).is_dir(),
                      reviewed_smoke_scope=plans[t.instance_id]['scope'] if t.instance_id in plans else None,
                      parked=is_parked(t), runtime_checked=False) for t in tasks]
    selected = choose_pilot(tasks, images, plans, args.pilot_size)
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / 'inventory.json').write_text(json.dumps(inventory, indent=2) + '\n', encoding='utf-8')
    results = []
    with (args.output / 'pilot.jsonl').open('x', encoding='utf-8') as journal:
        for task in selected:
            print('Pilot: ' + task.repository_url + ' / ' + task.instance_id, flush=True)
            record = (dict(task_id=task.instance_id, repository=task.repository_url,
                           status='not_executed', message=engine_error, full_suite_ready=False)
                      if not args.execute_pilot or engine_error else
                      pilot_task(task, images, plans, args.repositories, args.output))
            results.append(record)
            journal.write(json.dumps(record, default=str) + '\n')
            journal.flush()
            print('Result: ' + record['status'], flush=True)
    summary = dict(generated_at=datetime.now(UTC).isoformat(), tasks=len(tasks),
                   repositories=len({t.repository_url for t in tasks}),
                   repository_counts=dict(Counter(t.repository_url for t in tasks)),
                   local_image_tasks=sum(t.container_image in images for t in tasks),
                   corpus_pin_sha256=hashlib.sha256(pin_path.read_bytes()).hexdigest(),
                   pilot_size=len(selected), pilot_executed=args.execute_pilot,
                   statuses=dict(Counter(r['status'] for r in results)),
                   pilot=results, engine_error=engine_error,
                   parked_repository=PARKED_REPO, parked_evidence=PARKED_EVIDENCE,
                   selection='One task per repository; prefer language coverage, local images and reviewed smokes, then lexical order. Availability-biased engineering pilot, not a research sample.',
                   images_pulled=0, full_suites_run=0, official_readiness_changed=False,
                   model_calls=0, verifier_run=False)
    (args.output / 'summary.json').write_text(json.dumps(summary, indent=2, default=str) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in summary.items() if k != 'pilot'}, indent=2))


if __name__ == '__main__':
    main()
