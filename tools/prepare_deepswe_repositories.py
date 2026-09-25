"""Clone DeepSWE task repositories, sealed at each task's base commit.

Usage (from the repository root):

    python tools/prepare_deepswe_repositories.py --tasks-root ../benchmarks/deep-swe/tasks \\
        --destination ../benchmarks/deepswe-repos --task-id abs-module-cache-flags

Each repository lands in ``<destination>/<task-id>`` with no history after the
task's base commit, beside a ``<task-id>.sealed.json`` provenance record. This
is the only step that uses the network; pass ``--verify-only`` to re-check
repositories that were prepared earlier.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from agentless_ml.adapters.benchmarks import DeepSWEDataset, DeepSWEDatasetPin, pinned_load_options
from agentless_ml.workspace import (
    WorkspaceError,
    prepare_sealed_repository,
    verify_sealed_repository,
)

ROOT = Path(__file__).resolve().parents[1]
PIN = ROOT / "experiments" / "deepswe" / "corpus_pin.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tasks-root", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--task-id", action="append", dest="task_ids")
    parser.add_argument("--language")
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--timeout-seconds", type=float, default=1800)
    arguments = parser.parse_args()

    pin_data = json.loads(PIN.read_text(encoding="utf-8"))
    dataset = DeepSWEDataset(
        arguments.tasks_root,
        DeepSWEDatasetPin(
            revision=pin_data["revision"],
            agent_files_sha256=pin_data["agent_files_sha256"],
            task_count=pin_data["task_count"],
        ),
    )
    tasks = dataset.load_tasks(
        language=arguments.language,
        task_ids=tuple(arguments.task_ids) if arguments.task_ids else None,
        **pinned_load_options(pin_data),
    )

    failures = 0
    for task in tasks:
        destination = arguments.destination / task.instance_id
        try:
            if arguments.verify_only:
                verify_sealed_repository(destination, task.base_commit)
                print(f"verified {task.instance_id}")
            elif destination.exists():
                verify_sealed_repository(destination, task.base_commit)
                print(f"already prepared {task.instance_id}")
            else:
                sealed = prepare_sealed_repository(
                    task.repository_url,
                    task.base_commit,
                    destination,
                    timeout_seconds=arguments.timeout_seconds,
                )
                print(f"prepared {task.instance_id} at {sealed.base_commit}")
        except WorkspaceError as error:
            failures += 1
            print(f"FAILED {task.instance_id}: {error}")
    print(f"{len(tasks) - failures}/{len(tasks)} repositories ready")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
