"""Check, task by task, that each DeepSWE task's own test suite runs.

Before any workflow run, every task needs a sealed repository, its pinned
published image, a test plan (runner and targets) and a baseline run of that
plan on the unpatched checkout that yields at least one passing test: those
passing tests are the regression inventory. This tool does exactly that for
many tasks and records the outcome of each, so the tasks that need attention
are known before a model is ever called.

    python tools/survey_deepswe.py --tasks-root ../benchmarks/deep-swe/tasks \\
        --repositories ../benchmarks/deepswe-repos --language go --pull

Results are appended to ``--results`` as one JSON object per line. A task that
already has a result is skipped, so an interrupted survey resumes; ``--rerun``
runs the selected tasks again, and the latest line for a task wins. Images are
pulled only with ``--pull``, since all 113 amount to many gigabytes. Held-out
``tests/`` and ``solution/`` are never read.

Outcomes:
  ready              the suite ran and at least one test passed
  no_passing_tests   the suite ran and nothing passed; no inventory
  no_runner          the repository's test runner could not be determined
  no_image           the pinned image is not present (use --pull)
  image_mismatch     the local image is not the pinned digest
  repository_failed  the sealed repository could not be prepared or verified
  harness_error, timeout, out_of_memory   as the runner reports them
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import time
from collections import Counter
from pathlib import Path

from agentless_ml.adapters.benchmarks import (
    DeepSWEDataset,
    DeepSWEDatasetPin,
    deepswe_test_plan,
    load_test_overrides,
)
from agentless_ml.schemas import TestCaseStatus, TaskSpec, ValidationStatus
from agentless_ml.validation import DockerTestRunner
from agentless_ml.workspace import (
    LocalGitWorkspaceProvider,
    WorkspaceError,
    prepare_sealed_repository,
    verify_sealed_repository,
)

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = ROOT / "experiments" / "deepswe"


def _image_id(reference: str) -> str | None:
    result = subprocess.run(
        ["docker", "image", "inspect", "--format", "{{.Id}}", reference],
        capture_output=True, text=True, timeout=60, check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def _ensure_image(task: TaskSpec, pull: bool) -> tuple[str | None, str]:
    image_id = _image_id(task.container_image)
    if image_id is None and pull:
        pulled = subprocess.run(
            ["docker", "pull", "--quiet", task.container_image],
            capture_output=True, text=True, timeout=3600, check=False,
        )
        if pulled.returncode:
            return None, "no_image: pull failed: " + pulled.stderr.strip()[:300]
        image_id = _image_id(task.container_image)
    if image_id is None:
        return None, "no_image"
    if image_id != task.container_digest:
        return None, f"image_mismatch: {image_id} is not the pinned {task.container_digest}"
    return image_id, ""


def _survey(task, args, overrides) -> dict:
    record = {"task_id": task.instance_id, "language": task.language,
              "base_commit": task.base_commit}
    started = time.monotonic()

    def done(status, **fields):
        return {**record, "status": status, **fields,
                "seconds": round(time.monotonic() - started, 1)}

    repository = args.repositories / task.instance_id
    try:
        if repository.exists():
            verify_sealed_repository(repository, task.base_commit)
        else:
            prepare_sealed_repository(task.repository_url, task.base_commit, repository)
    except WorkspaceError as error:
        return done("repository_failed", message=str(error)[:500])

    image_id, problem = _ensure_image(task, args.pull)
    if image_id is None:
        status, _, message = problem.partition(": ")
        return done(status, message=message)

    artifacts = args.artifacts / task.instance_id
    provider = LocalGitWorkspaceProvider(repository, task.base_commit, artifacts / "workspaces")
    with provider.create() as workspace:
        try:
            plan = deepswe_test_plan(
                task.language, workspace.path, overrides.get(task.instance_id)
            )
        except (ValueError, OSError) as error:
            return done("no_runner", message=str(error)[:500])
        runner = DockerTestRunner(
            task.container_image,
            artifacts / "logs",
            memory_mb=task.memory_megabytes,
            cpus=2,
            tmpfs_mb=args.tmpfs_mb,
            pids_limit=2048,
            run_as_image_user=True,
        )
        execution = runner.run(workspace.path, plan.command(timeout_seconds=args.timeout_seconds))

    result = execution.result
    counts = Counter(case.status.value for case in result.test_cases)
    passed = counts.get(TestCaseStatus.PASSED.value, 0)
    if result.status in (ValidationStatus.PASS, ValidationStatus.FAIL):
        status = "ready" if passed else "no_passing_tests"
    else:
        status = result.status.value
    return done(
        status,
        runner=plan.runner,
        targets=list(plan.targets),
        override=plan.override_reason,
        exit_code=result.exit_code,
        tests=len(result.test_cases),
        passed=passed,
        failed=counts.get(TestCaseStatus.FAILED.value, 0) + counts.get(TestCaseStatus.ERROR.value, 0),
        skipped=counts.get(TestCaseStatus.SKIPPED.value, 0),
        image_id=image_id,
        message=execution.message[:500],
        artifacts=execution.artifact_directory,
    )


def _latest(path: Path) -> dict[str, dict]:
    latest: dict[str, dict] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                record = json.loads(line)
                latest[record["task_id"]] = record
    return latest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tasks-root", type=Path, required=True)
    parser.add_argument("--repositories", type=Path, required=True)
    parser.add_argument("--task-id", action="append", dest="task_ids")
    parser.add_argument("--language")
    parser.add_argument("--pull", action="store_true")
    parser.add_argument("--rerun", action="store_true")
    parser.add_argument("--results", type=Path, default=ROOT / "artifacts" / "deepswe" / "survey.jsonl")
    parser.add_argument("--artifacts", type=Path, default=ROOT / "artifacts" / "deepswe" / "survey")
    parser.add_argument("--timeout-seconds", type=float, default=1800)
    parser.add_argument("--tmpfs-mb", type=int, default=4096)
    # Pulling every image is about 100 GB; stop before the disk is full rather
    # than fail tasks for reasons that have nothing to do with them.
    parser.add_argument("--min-free-gb", type=float, default=30)
    args = parser.parse_args()

    pin = json.loads((EXPERIMENTS / "corpus_pin.json").read_text(encoding="utf-8"))
    overrides = load_test_overrides(EXPERIMENTS / "test_overrides.json")
    tasks = DeepSWEDataset(
        args.tasks_root,
        DeepSWEDatasetPin(pin["revision"], pin["agent_files_sha256"], pin["task_count"]),
    ).load_tasks(
        language=args.language,
        task_ids=tuple(args.task_ids) if args.task_ids else None,
        resolved_base_commits=pin["resolved_base_commits"],
        container_digests=pin["container_digests"],
    )
    args.results.parent.mkdir(parents=True, exist_ok=True)
    recorded = _latest(args.results)
    for task in tasks:
        if task.instance_id in recorded and not args.rerun:
            continue
        free_gb = shutil.disk_usage(args.repositories.anchor or ".").free / 1e9
        if free_gb < args.min_free_gb:
            print(f"stopping: {free_gb:.0f} GB free, below --min-free-gb {args.min_free_gb:g}")
            break
        record = _survey(task, args, overrides)
        with args.results.open("a", encoding="utf-8", newline="\n") as results:
            results.write(json.dumps(record) + "\n")
        detail = (
            f"{record.get('runner')} {record.get('passed')}/{record.get('tests')} passed"
            if "tests" in record else record.get("message", "")
        )
        print(f"{record['status']:17} {task.instance_id:48} {detail[:110]}", flush=True)

    latest = _latest(args.results)
    selected = {task.instance_id for task in tasks}
    summary = Counter(record["status"] for task_id, record in latest.items() if task_id in selected)
    print("summary:", dict(summary.most_common()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
