"""Run a DeepSWE task's tests in its image, against a candidate checkout.

Prepare the task's repository first with `tools/prepare_deepswe_repositories.py`,
then, from the repository root:

    python tools/run_deepswe_tests.py --tasks-root ../benchmarks/deepswe/corpus/tasks \\
        --repositories ../benchmarks/deepswe/repos \\
        --task-id actionlint-action-pinning-lint

The task's whole suite runs, as its repository declares it, with any override
from `experiments/deepswe/test_overrides.json`; arguments after `--` replace
that plan's targets. This runs the unpatched checkout: it is the baseline a
regression schedule is built from. No model is called.

By default the published image is used unless environments.json registers a
verified, explicitly labelled alternative. Both paths enforce immutable image
pins. `--image` is a separate diagnostic substitution and bypasses registration.
"""

from __future__ import annotations

import argparse
import json
import shutil
from collections import Counter
from pathlib import Path

from agentless_ml.adapters.benchmarks import (
    pinned_load_options,
    DeepSWEDataset,
    DeepSWEDatasetPin,
    deepswe_test_command,
    deepswe_test_plan,
    load_test_overrides,
)
from agentless_ml.workspace import LocalGitWorkspaceProvider
from deepswe_environments import (
    environment_for, load_environments, runtime_task, runtime_command, runtime_runner,
)

ROOT = Path(__file__).resolve().parents[1]
PIN = ROOT / "experiments" / "deepswe" / "corpus_pin.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tasks-root", type=Path, required=True)
    parser.add_argument("--repositories", type=Path, required=True)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--image")
    parser.add_argument("--artifacts", type=Path, default=ROOT / "artifacts" / "deepswe")
    parser.add_argument("--timeout-seconds", type=float, default=1800)
    parser.add_argument("targets", nargs="*")
    arguments = parser.parse_args()

    pin = json.loads(PIN.read_text(encoding="utf-8"))
    dataset = DeepSWEDataset(
        arguments.tasks_root,
        DeepSWEDatasetPin(
            revision=pin["revision"],
            agent_files_sha256=pin["agent_files_sha256"],
            task_count=pin["task_count"],
        ),
    )
    (task,) = dataset.load_tasks(
        task_ids=(arguments.task_id,),
        **pinned_load_options(pin),
    )
    overrides = load_test_overrides(PIN.parent / "test_overrides.json")
    override = overrides.get(task.instance_id)
    environment = None if arguments.image else environment_for(task, load_environments())
    selected_task = runtime_task(task, environment)

    artifacts = arguments.artifacts / task.instance_id
    shutil.rmtree(artifacts, ignore_errors=True)
    provider = LocalGitWorkspaceProvider(
        arguments.repositories / task.instance_id,
        task.base_commit,
        artifacts / "workspaces",
    )
    # The image's own user owns the toolchain caches under /root that these
    # suites need; every other container restriction stays in place.
    runner = runtime_runner(
        arguments.image or selected_task.container_image,
        artifacts / "logs",
        environment,
        task=None if arguments.image else task,
        memory_mb=task.memory_megabytes,
        cpus=2,
        tmpfs_mb=override.get("tmpfs_mb", 4096) if override else 4096,
        pids_limit=2048,
        run_as_image_user=True,
    )
    if not arguments.image and runner.image_id != selected_task.container_digest:
        raise SystemExit(
            f"{task.container_image} is {runner.image_id}, "
            f"not the pinned {selected_task.container_digest}"
        )
    source = environment['condition'] if environment else ("substituted" if arguments.image else "published, matches pin")
    with provider.create() as workspace:
        plan = deepswe_test_plan(task.language, workspace.path, override)
        # Targets on the command line replace the task's derived plan.
        targets = tuple(arguments.targets) if arguments.targets else plan.targets
        command = deepswe_test_command(
            plan.runner, targets, timeout_seconds=arguments.timeout_seconds
        )
        command = runtime_command(command, environment)
        print(f"{task.instance_id} [{task.language}, {plan.runner}] at {task.base_commit[:12]}")
        print(f"targets {list(targets)}")
        print(f"image {runner.image_reference} ({runner.image_id[:19]}, {source}) as {runner.user}")
        execution = runner.run(workspace.path, command)
    if environment is not None:
        (Path(execution.artifact_directory) / 'environment.json').write_text(
            json.dumps(environment, indent=2) + '\n', encoding='utf-8')
    result = execution.result
    counts = Counter(case.status.value for case in result.test_cases)
    print(
        f"status={result.status.value} exit={result.exit_code} "
        f"duration={result.duration_seconds:.1f}s"
    )
    print(f"tests={len(result.test_cases)} {dict(counts)} failures={result.failure_count()}")
    if execution.message:
        print(f"message: {execution.message[:300]}")
    for case in result.test_cases:
        if case.status.value in {"failed", "error"}:
            print(f"  FAIL {case.test_id}")
    print(f"artifacts: {execution.artifact_directory}")
    return 0 if result.test_cases else 1


if __name__ == "__main__":
    raise SystemExit(main())
