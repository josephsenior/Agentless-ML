"""Run the recorded V2 Vuls Go slice with public checks only.

The responses are hand-written engineering fixtures, not model output. The
benchmark verifier is deliberately not imported or run by this command.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

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
)
from agentless_ml.workflow import FixedWorkflowController, RecordedStageResponses

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "experiments" / "swe_bench_pro" / "v2_go_vuls_header"
PIN = ROOT / "experiments" / "swe_bench_pro" / "v2_corpus_pin.json"


def _revision() -> str:
    def git(*args: str) -> str:
        return subprocess.run(
            ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
        ).stdout.strip()

    return git("rev-parse", "HEAD") + (
        "+dirty" if git("status", "--porcelain", "--untracked-files=all") else ""
    )


def _responses() -> RecordedStageResponses:
    return RecordedStageResponses(
        file_localization=(EXPERIMENT / "file_localization.txt").read_text(
            encoding="utf-8"
        ),
        symbol_localization=(EXPERIMENT / "symbol_localization.txt").read_text(
            encoding="utf-8"
        ),
        repairs=tuple(
            path.read_text(encoding="utf-8")
            for path in sorted(EXPERIMENT.glob("repair_*.txt"))
        ),
        regression_exclusions=(EXPERIMENT / "regression_exclusions.txt").read_text(
            encoding="utf-8"
        ),
        reproduction_test=(EXPERIMENT / "reproduction_test.txt").read_text(
            encoding="utf-8"
        ),
        source="manually recorded from the V2 instruction and public base checkout",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--v1-parquet", type=Path, required=True)
    parser.add_argument("--v2-tasks", type=Path, required=True)
    parser.add_argument("--source-repository", type=Path, required=True)
    parser.add_argument("--workspace-root", type=Path, required=True)
    parser.add_argument("--artifact-root", type=Path, required=True)
    args = parser.parse_args()

    pin = json.loads(PIN.read_text(encoding="utf-8"))
    spec = json.loads((EXPERIMENT / "experiment.json").read_text(encoding="utf-8"))
    v1_dataset = SWEbenchProDataset(
        args.v1_parquet,
        SWEbenchProDatasetPin(
            pin["v1_dataset_revision"], pin["v1_parquet_sha256"], pin["v1_row_count"]
        ),
    )
    v2_dataset = SWEbenchProV2Dataset(
        args.v2_tasks,
        SWEbenchProV2DatasetPin(
            pin["v2_dataset_revision"],
            pin["v2_visible_files_sha256"],
            pin["v2_task_count"],
        ),
        v1_dataset,
    )
    (task,) = v2_dataset.load_tasks(
        instance_ids=(spec["instance_id"],),
        container_digests={spec["instance_id"]: spec["image_id"]},
    )
    if task.language != "go":
        raise ValueError("the recorded Vuls slice requires a Go task")
    image_base = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--entrypoint",
            "git",
            task.container_image,
            "-C",
            "/app",
            "rev-parse",
            "HEAD",
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    ).stdout.strip()
    if image_base != task.base_commit or image_base != spec["base_commit"]:
        raise ValueError("official image checkout differs from the pinned base")
    runner = DockerTestRunner(
        task.container_image,
        args.artifact_root / "unused-default-executions",
        memory_mb=task.memory_megabytes,
        cpus=1,
        tmpfs_mb=4_096,
        pids_limit=2_048,
        run_as_image_user=True,
    )
    regression = RegressionTest(
        spec["regression"]["test_id"],
        PublicTestCommand(
            tuple(spec["regression"]["argv"]),
            timeout_seconds=spec["regression"]["timeout_seconds"],
        ),
    )
    reproduction = ReproductionSpec(
        spec["reproduction"]["path"],
        PublicTestCommand(
            tuple(spec["reproduction"]["argv"]),
            kind=ValidationKind.REPRODUCTION,
            timeout_seconds=spec["reproduction"]["timeout_seconds"],
        ),
    )
    result = FixedWorkflowController(
        task=task,
        source_repository=args.source_repository,
        workspace_root=args.workspace_root,
        artifact_root=args.artifact_root,
        runner=runner,
        public_commands=(),
        regression_tests=(regression,),
        reproduction_spec=reproduction,
        implementation_revision=_revision(),
        harness_revision=pin["v2_dataset_revision"],
        model_name="recorded/manual-go-v2-smoke",
    ).run(_responses())
    print(
        json.dumps(
            {
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
