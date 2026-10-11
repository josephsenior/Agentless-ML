"""Replay the recorded Python reproduction on the pinned qutebrowser V2 task."""

from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import subprocess

from agentless_ml.adapters.benchmarks import (
    SWEbenchProDataset,
    SWEbenchProDatasetPin,
    SWEbenchProV2Dataset,
    SWEbenchProV2DatasetPin,
)
from agentless_ml.schemas import ValidationKind
from agentless_ml.validation import (
    DockerTestRunner,
    PublicTestCommand,
    RegressionTest,
    ReproductionSpec,
    python_reproduction_command,
)
from agentless_ml.workflow import FixedWorkflowController, RecordedStageResponses
from agentless_ml.workspace import verify_sealed_repository

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "experiments/swe_bench_pro/qutebrowser_network_error"
SPEC = json.loads((EXPERIMENT / "python_reproduction_experiment.json").read_bytes())


def _revision() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
        capture_output=True, text=True,
    ).stdout.strip()


def _load_task(v1_parquet: Path, v2_tasks: Path):
    smoke = json.loads((ROOT / "experiments/swe_bench_pro/python_smoke_set.json").read_bytes())
    v2 = json.loads((ROOT / "experiments/swe_bench_pro/v2_smoke_set.json").read_bytes())
    pin = json.loads((ROOT / "experiments/swe_bench_pro/v2_corpus_pin.json").read_bytes())
    dataset = SWEbenchProDataset(
        v1_parquet,
        SWEbenchProDatasetPin(
            smoke["dataset_revision"], smoke["parquet_sha256"], smoke["row_count"]
        ),
    )
    tasks = SWEbenchProV2Dataset(
        v2_tasks,
        SWEbenchProV2DatasetPin(
            pin["v2_dataset_revision"], pin["v2_visible_files_sha256"], pin["v2_task_count"]
        ),
        dataset,
    )
    entry = v2["experiments"][SPEC["experiment"]]
    (task,) = tasks.load_tasks(
        language="python",
        instance_ids=(SPEC["instance_id"],),
        container_digests={SPEC["instance_id"]: entry["container_digest"]},
    )
    if task.base_commit != SPEC["base_commit"] or task.container_digest != SPEC["container_digest"]:
        raise ValueError("task base or image differs from the reviewed experiment pin")
    if task.memory_megabytes != SPEC["memory_mb"]:
        raise ValueError("container memory limit differs from the pinned V2 task metadata")
    visible = v2["experiments"][SPEC["experiment"]]["visible_sha256"]
    if visible != SPEC["visible_sha256"]:
        raise ValueError("visible V2 task files differ from the reviewed experiment pin")
    return task, pin


def _verify_image_base(task) -> None:
    result = subprocess.run(
        ["docker", "run", "--rm", "--network", "none", "--entrypoint", "git",
         task.container_digest, "-C", "/app", "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True, timeout=60,
    )
    if result.stdout.strip() != task.base_commit:
        raise ValueError("pinned image checkout differs from the pinned task base")


def _responses() -> RecordedStageResponses:
    base = python_reproduction_command(
        SPEC["reproduction_path"], timeout_seconds=SPEC["reproduction_timeout_seconds"]
    )
    command = replace(
        base,
        argv=("env", *SPEC["environment"], *base.argv),
    )
    spec = ReproductionSpec(SPEC["reproduction_path"], command)
    repairs = tuple(
        path.read_text(encoding="utf-8")
        for path in sorted(EXPERIMENT.glob("repair_*.txt"))
    )
    return RecordedStageResponses(
        file_localization=(EXPERIMENT / "file_localization.txt").read_text(encoding="utf-8"),
        symbol_localization=(EXPERIMENT / "symbol_localization.txt").read_text(encoding="utf-8"),
        repairs=repairs,
        regression_exclusions="",
        reproduction_test=(EXPERIMENT / "python_reproduction_test.txt").read_text(encoding="utf-8"),
        source="recorded from the public issue and pinned base behavior; no model call",
    ), spec


def run(*, v1_parquet: Path, v2_tasks: Path, source_repository: Path,
        workspace_root: Path, artifact_root: Path) -> dict:
    task, pin = _load_task(v1_parquet, v2_tasks)
    source_repository = source_repository.resolve(strict=True)
    verify_sealed_repository(source_repository, task.base_commit)
    _verify_image_base(task)

    output = artifact_root.resolve()
    output.mkdir(parents=True, exist_ok=False)
    command = PublicTestCommand(
        tuple(SPEC["regression_argv"]),
        kind=ValidationKind.REGRESSION,
        timeout_seconds=SPEC["regression_timeout_seconds"],
    )
    runner = DockerTestRunner(
        task.container_image,
        output / "unused-default-executions",
        memory_mb=SPEC["memory_mb"],
        cpus=SPEC["cpus"],
        tmpfs_mb=SPEC["tmpfs_mb"],
        pids_limit=SPEC["pids_limit"],
        run_as_image_user=True,
    )
    responses, reproduction = _responses()
    result = FixedWorkflowController(
        task=task,
        source_repository=source_repository,
        workspace_root=workspace_root,
        artifact_root=output,
        runner=runner,
        public_commands=(),
        regression_tests=(RegressionTest("networkreply-source-compiles", command),),
        reproduction_spec=reproduction,
        implementation_revision=_revision(),
        harness_revision=pin["v2_dataset_revision"],
        model_name="recorded/manual-python-v2-reproduction",
    ).run(responses)

    (run_directory,) = (output / "runs").iterdir()
    baseline = json.loads((run_directory / "reproduction-baseline.json").read_bytes())
    public_baseline = json.loads((run_directory / "regression-baseline.json").read_bytes())
    prediction_path = run_directory / "prediction.json"
    report_paths = sorted(run_directory.rglob("report.json")) + sorted(run_directory.rglob("report.xml"))
    summary = {
        "scope": SPEC["purpose"],
        "run_id": result.run.run_id,
        "started_at": result.run.started_at.astimezone(UTC).isoformat(),
        "artifact_directory": str(run_directory),
        "task_id": task.instance_id,
        "base_commit": task.base_commit,
        "container_digest": task.container_digest,
        "implementation_revision": result.run.implementation_revision,
        "reproduction_source_sha256": json.loads(
            (run_directory / "reproduction-source.json").read_bytes()
        )["source_sha256"],
        "baseline_reproduction_status": baseline["checked_result"]["status"],
        "public_regression_status": public_baseline[0]["result"]["status"],
        "attempts": [
            {"candidate_id": attempt.candidate_id, "status": attempt.status}
            for attempt in result.attempts
        ],
        "selected_candidate_id": result.prediction.selected_candidate_id,
        "candidate_outcomes": {
            attempt.candidate_id: [evidence.status.value for evidence in attempt.candidate.validation]
            for attempt in result.attempts if attempt.candidate is not None
        },
        "prediction_sha256": hashlib.sha256(prediction_path.read_bytes()).hexdigest(),
        "report_sha256": {
            path.relative_to(run_directory).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in report_paths
        },
        "model_calls": result.run.model_calls,
        "wall_time_seconds": result.run.wall_time_seconds,
        "held_out_verifier_run": False,
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--v1-parquet", type=Path, required=True)
    parser.add_argument("--v2-tasks", type=Path, required=True)
    parser.add_argument("--source-repository", type=Path, required=True)
    parser.add_argument("--workspace-root", type=Path, required=True)
    parser.add_argument("--artifact-root", type=Path, required=True)
    args = parser.parse_args()
    run(**vars(args))
