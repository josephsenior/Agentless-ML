"""Run the pinned, recorded SWE-bench Pro Python vertical slice."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from agentless_ml.adapters.benchmarks import (
    SWEbenchProDataset,
    SWEbenchProDatasetPin,
    load_swe_bench_pro_v2_task,
)
from agentless_ml.schemas import ValidationKind
from agentless_ml.validation import DockerTestRunner, PublicTestCommand
from agentless_ml.workflow import FixedWorkflowController, RecordedStageResponses

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT_ROOT = ROOT / "experiments" / "swe_bench_pro"


def _revision() -> str:
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    dirty = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return revision + ("+dirty" if dirty else "")


def _responses(experiment: Path) -> RecordedStageResponses:
    repairs = tuple(
        path.read_text(encoding="utf-8")
        for path in sorted(experiment.glob("repair_*.txt"))
    )
    return RecordedStageResponses(
        file_localization=(experiment / "file_localization.txt").read_text(
            encoding="utf-8"
        ),
        symbol_localization=(experiment / "symbol_localization.txt").read_text(
            encoding="utf-8"
        ),
        repairs=repairs,
        source="manually recorded from agent-visible issue and base checkout",
    )


def _verify_v2_base_checkout(task) -> None:
    """V2's manifest omits the base commit; check the pinned image itself."""
    result = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--entrypoint",
            "git",
            task.container_digest,
            "-C",
            "/app",
            "rev-parse",
            "HEAD",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    if result.stdout.strip() != task.base_commit:
        raise ValueError("V2 image base commit differs from pinned V1 metadata")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-parquet", type=Path, required=True)
    parser.add_argument("--experiment", required=True)
    parser.add_argument("--source-repository", type=Path, required=True)
    parser.add_argument("--workspace-root", type=Path, required=True)
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument(
        "--v2-task-dir",
        type=Path,
        help="Agent-visible V2 task directory for the pinned V2 smoke slice",
    )
    args = parser.parse_args()

    smoke_set = json.loads(
        (EXPERIMENT_ROOT / "python_smoke_set.json").read_text(encoding="utf-8")
    )
    if args.experiment not in smoke_set["experiments"]:
        parser.error(f"unknown smoke experiment: {args.experiment}")
    experiment = EXPERIMENT_ROOT / args.experiment
    entry = smoke_set["experiments"][args.experiment]
    pin = SWEbenchProDatasetPin(
        revision=smoke_set["dataset_revision"],
        parquet_sha256=smoke_set["parquet_sha256"],
        row_count=smoke_set["row_count"],
    )
    dataset = SWEbenchProDataset(args.dataset_parquet, pin)
    task = dataset.load_tasks(
        language="python",
        instance_ids=(entry["instance_id"],),
        container_digests={entry["instance_id"]: entry["container_digest"]},
    )[0]
    if args.v2_task_dir is not None:
        v2_set = json.loads(
            (EXPERIMENT_ROOT / "v2_smoke_set.json").read_text(encoding="utf-8")
        )
        v2_entry = v2_set["experiments"].get(args.experiment)
        if v2_entry is None or v2_entry["instance_id"] != task.instance_id:
            parser.error("experiment is not in the pinned V2 smoke set")
        task = load_swe_bench_pro_v2_task(
            args.v2_task_dir,
            task,
            dataset_revision=v2_set["dataset_revision"],
            visible_sha256=v2_entry["visible_sha256"],
            container_digest=v2_entry["container_digest"],
        )
        _verify_v2_base_checkout(task)
    validation = json.loads(
        (experiment / "validation.json").read_text(encoding="utf-8")
    )
    commands = tuple(
        PublicTestCommand(
            tuple(spec["argv"]),
            kind=ValidationKind(spec["kind"]),
            timeout_seconds=spec["timeout_seconds"],
        )
        for spec in validation
    )
    runner = DockerTestRunner(
        task.container_image,
        args.artifact_root / "unused-default-executions",
        memory_mb=task.memory_megabytes,
        cpus=2,
        pids_limit=512,
        tmpfs_mb=1_024,
    )
    result = FixedWorkflowController(
        task=task,
        source_repository=args.source_repository,
        workspace_root=args.workspace_root,
        artifact_root=args.artifact_root,
        runner=runner,
        public_commands=commands,
        implementation_revision=_revision(),
        harness_revision=(
            v2_set["dataset_revision"]
            if args.v2_task_dir
            else smoke_set["harness_revision"]
        ),
        model_name=(
            "recorded/manual-v1-reused-for-v2-smoke"
            if args.v2_task_dir
            else "recorded/manual-v1"
        ),
    ).run(_responses(experiment))
    print(
        json.dumps(
            {
                "experiment": args.experiment,
                "instance_id": task.instance_id,
                "selected_candidate_id": result.prediction.selected_candidate_id,
                "selection_reason": result.selection_reason,
                "attempt_statuses": [attempt.status for attempt in result.attempts],
                "model_calls": result.run.model_calls,
                "artifact_directory": result.artifact_directory,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
