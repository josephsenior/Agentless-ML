"""Run the fixed workflow on a DeepSWE task with recorded responses.

The regression inventory is one report-bearing command for the task's suite.
The controller runs it once on the unpatched checkout, keeps every test that
passed by name, applies the recorded exclusions, and counts each candidate's
failures among the tests that remain. No model is called.

    python tools/run_deepswe_workflow.py --tasks-root ../benchmarks/deep-swe/tasks \\
        --repositories ../benchmarks/deepswe-repos \\
        --experiment actionlint_action_pinning \\
        --workspace-root ../runs/workspaces --artifact-root ../runs/artifacts

By default the task runs in its published image, which must already be pulled,
and the controller refuses it unless its ID matches the digest pinned in
``corpus_pin.json``. ``--image`` substitutes another image, such as a local
build; the task is then rewritten to that reference and its ID, and the
substitution is printed and kept in the run's ``task.json``.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import replace
from pathlib import Path

from agentless_ml.adapters.benchmarks import (
    pinned_load_options,
    DeepSWEDataset,
    DeepSWEDatasetPin,
    deepswe_test_command,
    deepswe_test_plan,
    load_test_overrides,
)
from agentless_ml.validation import DockerTestRunner, RegressionTest
from agentless_ml.workflow import FixedWorkflowController, RecordedStageResponses
from agentless_ml.workspace import LocalGitWorkspaceProvider

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = ROOT / "experiments" / "deepswe"
PIN = EXPERIMENTS / "corpus_pin.json"


def _revision() -> str:
    def git(*args: str) -> str:
        return subprocess.run(
            ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
        ).stdout.strip()

    dirty = git("status", "--porcelain", "--untracked-files=all")
    return git("rev-parse", "HEAD") + ("+dirty" if dirty else "")


def _responses(experiment: Path) -> RecordedStageResponses:
    return RecordedStageResponses(
        file_localization=(experiment / "file_localization.txt").read_text(encoding="utf-8"),
        symbol_localization=(experiment / "symbol_localization.txt").read_text(encoding="utf-8"),
        repairs=tuple(
            path.read_text(encoding="utf-8")
            for path in sorted(experiment.glob("repair_*.txt"))
        ),
        regression_exclusions=(experiment / "regression_exclusions.txt").read_text(
            encoding="utf-8"
        ),
        source="manually recorded from the agent-visible instruction and base checkout",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tasks-root", type=Path, required=True)
    parser.add_argument("--repositories", type=Path, required=True)
    parser.add_argument("--experiment", required=True)
    parser.add_argument("--image")
    parser.add_argument("--workspace-root", type=Path, required=True)
    parser.add_argument("--artifact-root", type=Path, required=True)
    args = parser.parse_args()

    experiment = EXPERIMENTS / args.experiment
    spec = json.loads((experiment / "experiment.json").read_text(encoding="utf-8"))
    pin = json.loads(PIN.read_text(encoding="utf-8"))
    dataset = DeepSWEDataset(
        args.tasks_root,
        DeepSWEDatasetPin(
            revision=pin["revision"],
            agent_files_sha256=pin["agent_files_sha256"],
            task_count=pin["task_count"],
        ),
    )
    (published,) = dataset.load_tasks(
        task_ids=(spec["task_id"],),
        **pinned_load_options(pin),
    )

    runner = DockerTestRunner(
        args.image or published.container_image,
        args.artifact_root / "unused-default-executions",
        memory_mb=published.memory_megabytes,
        cpus=2,
        tmpfs_mb=4096,
        pids_limit=2048,
        run_as_image_user=True,
    )
    task = (
        replace(
            published,
            container_image=runner.image_reference,
            container_digest=runner.image_id,
        )
        if args.image
        else published
    )
    suite = spec.get("suite", {})
    source_repository = args.repositories / task.instance_id
    overrides = load_test_overrides(EXPERIMENTS / "test_overrides.json")
    # Read the declared runner from a clean checkout of the pinned commit.
    with LocalGitWorkspaceProvider(
        source_repository, task.base_commit, args.workspace_root
    ).create() as checkout:
        plan = deepswe_test_plan(task.language, checkout.path, overrides.get(task.instance_id))
    test_runner = plan.runner
    # An experiment may narrow the suite; by default it is the task's whole plan.
    targets = tuple(suite["targets"]) if "targets" in suite else plan.targets
    regression_tests = (
        RegressionTest(
            suite.get("test_id", "suite"),
            deepswe_test_command(
                test_runner,
                targets,
                timeout_seconds=suite.get("timeout_seconds", 1800),
            ),
        ),
    )

    result = FixedWorkflowController(
        task=task,
        source_repository=source_repository,
        workspace_root=args.workspace_root,
        artifact_root=args.artifact_root,
        runner=runner,
        public_commands=(),
        regression_tests=regression_tests,
        implementation_revision=_revision(),
        harness_revision=pin["revision"],
        model_name="recorded/manual-v1",
    ).run(_responses(experiment))

    directory = Path(result.artifact_directory)
    selection = json.loads((directory / "regression-selection.json").read_text(encoding="utf-8"))
    print(
        json.dumps(
            {
                "experiment": args.experiment,
                "instance_id": task.instance_id,
                "image": {
                    "used": task.container_image,
                    "image_id": runner.image_id,
                    "published": published.container_image,
                    "pinned_digest": published.container_digest,
                    "substituted": bool(args.image),
                },
                "test_runner": test_runner,
                "baseline_passing": len(selection["passing_ids"]),
                "excluded": selection["excluded_ids"],
                "counted": len(selection["selected_ids"]),
                "attempts": [
                    {"candidate": a.candidate_id, "status": a.status, "message": a.message[:120]}
                    for a in result.attempts
                ],
                "selected_candidate_id": result.prediction.selected_candidate_id,
                "selection_reason": result.selection_reason,
                "model_calls": result.run.model_calls,
                "artifact_directory": result.artifact_directory,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
