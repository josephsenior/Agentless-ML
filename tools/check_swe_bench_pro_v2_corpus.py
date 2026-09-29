"""Check that the complete V2 agent-visible corpus loads against pinned V1 metadata."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from agentless_ml.adapters.benchmarks import (
    SWEbenchProDataset,
    SWEbenchProDatasetPin,
    SWEbenchProV2Dataset,
    SWEbenchProV2DatasetPin,
)

ROOT = Path(__file__).resolve().parents[1]
PIN = ROOT / "experiments" / "swe_bench_pro" / "v2_corpus_pin.json"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--v1-parquet", type=Path, required=True)
    parser.add_argument("--v2-tasks", type=Path, required=True)
    args = parser.parse_args()
    pin = json.loads(PIN.read_text(encoding="utf-8"))
    v1_dataset = SWEbenchProDataset(
        args.v1_parquet,
        SWEbenchProDatasetPin(
            revision=pin["v1_dataset_revision"],
            parquet_sha256=pin["v1_parquet_sha256"],
            row_count=pin["v1_row_count"],
        ),
    )
    v2_dataset = SWEbenchProV2Dataset(
        args.v2_tasks,
        SWEbenchProV2DatasetPin(
            revision=pin["v2_dataset_revision"],
            visible_files_sha256=pin["v2_visible_files_sha256"],
            task_count=pin["v2_task_count"],
        ),
        v1_dataset,
    )
    tasks = v2_dataset.load_tasks()
    print(
        json.dumps(
            {
                "tasks": len(tasks),
                "languages": dict(
                    sorted(Counter(task.language for task in tasks).items())
                ),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
