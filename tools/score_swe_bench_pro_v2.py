"""Replay a final patch with SWE-bench Pro V2's pinned verifier.

Only use this after candidate selection. Empty and reference modes check the
scorer itself; their patches must never enter localization or repair.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from agentless_ml.adapters.benchmarks import (
    SWEbenchProDataset,
    SWEbenchProDatasetPin,
    SWEbenchProV2Dataset,
    SWEbenchProV2DatasetPin,
)
from agentless_ml.scoring import SWEbenchProV2Verifier

ROOT = Path(__file__).resolve().parents[1]
PIN = ROOT / "experiments" / "swe_bench_pro" / "v2_corpus_pin.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--v1-parquet", type=Path, required=True)
    parser.add_argument("--v2-repository", type=Path, required=True)
    parser.add_argument("--v2-tasks", type=Path, required=True)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--image-id", required=True)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--prediction", type=Path)
    source.add_argument("--patch", type=Path)
    source.add_argument("--empty", action="store_true")
    source.add_argument("--reference", action="store_true")
    parser.add_argument(
        "--artifacts", type=Path, default=ROOT / "artifacts" / "v2_scores"
    )
    parser.add_argument("--timeout-seconds", type=float)
    args = parser.parse_args()

    pin = json.loads(PIN.read_text(encoding="utf-8"))
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
        instance_ids=(args.task_id,),
        container_digests={args.task_id: args.image_id},
    )
    verifier = SWEbenchProV2Verifier(args.v2_repository, pin["v2_dataset_revision"])
    if args.prediction:
        prediction = json.loads(args.prediction.read_text(encoding="utf-8"))
        if prediction.get("instance_id") != task.instance_id:
            parser.error("prediction is for a different task")
        patch, label = prediction["model_patch"], "selected prediction"
    elif args.patch:
        patch, label = args.patch.read_text(encoding="utf-8"), "supplied patch"
    elif args.empty:
        patch, label = "", "empty patch (expect unresolved)"
    else:
        patch = verifier.reference_patch_for_harness_validation(task)
        label = "reference patch (expect resolved)"

    score = verifier.score(
        task,
        patch,
        args.artifacts / task.instance_id,
        timeout_seconds=args.timeout_seconds,
    )
    print(f"{task.instance_id}: {label}")
    print(json.dumps({**asdict(score), "status": score.status.value}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
