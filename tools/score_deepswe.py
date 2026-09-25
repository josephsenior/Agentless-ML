"""Score a patch for a DeepSWE task with DeepSWE's own verifier.

This is step 5, after selection: it reads the task's held-out tests, which the
workflow never sees, and reports whether the patch solves the task.

    python tools/score_deepswe.py --deepswe-repository ../benchmarks/deep-swe \\
        --tasks-root ../benchmarks/deep-swe/tasks \\
        --task-id actionlint-action-pinning-lint --prediction <run>/prediction.json

What to score is one of:

  --prediction FILE   the selected patch in a workflow run's prediction.json
  --patch FILE        a unified diff against the task's base commit
  --empty             no change; must score unresolved
  --reference         DeepSWE's reference solution; must score resolved

The last two check the scorer itself, not the workflow: a scorer that marks the
empty patch resolved, or the reference solution unresolved, cannot be trusted
to score anything else.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from agentless_ml.adapters.benchmarks import DeepSWEDataset, DeepSWEDatasetPin, pinned_load_options
from agentless_ml.scoring import DeepSWEVerifier

ROOT = Path(__file__).resolve().parents[1]
PIN = ROOT / "experiments" / "deepswe" / "corpus_pin.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--deepswe-repository", type=Path, required=True)
    parser.add_argument("--tasks-root", type=Path, required=True)
    parser.add_argument("--task-id", required=True)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--prediction", type=Path)
    source.add_argument("--patch", type=Path)
    source.add_argument("--empty", action="store_true")
    source.add_argument("--reference", action="store_true")
    parser.add_argument("--artifacts", type=Path, default=ROOT / "artifacts" / "scores")
    parser.add_argument("--timeout-seconds", type=float)
    args = parser.parse_args()

    pin = json.loads(PIN.read_text(encoding="utf-8"))
    (task,) = DeepSWEDataset(
        args.tasks_root,
        DeepSWEDatasetPin(pin["revision"], pin["agent_files_sha256"], pin["task_count"]),
    ).load_tasks(
        task_ids=(args.task_id,),
        **pinned_load_options(pin),
    )
    verifier = DeepSWEVerifier(args.deepswe_repository, pin["revision"])

    if args.prediction:
        prediction = json.loads(args.prediction.read_text(encoding="utf-8"))
        if prediction.get("instance_id") != task.instance_id:
            parser.error(f"{args.prediction} is for {prediction.get('instance_id')}")
        patch, label = prediction["model_patch"], f"prediction {args.prediction}"
    elif args.patch:
        patch, label = args.patch.read_bytes().decode("utf-8"), f"patch {args.patch}"
    elif args.empty:
        patch, label = "", "empty patch (expected: unresolved)"
    else:
        patch = verifier.reference_patch_for_harness_validation(task)
        label = "reference solution (expected: resolved)"

    score = verifier.score(
        task, patch, args.artifacts / task.instance_id, timeout_seconds=args.timeout_seconds
    )
    print(f"{task.instance_id}: {label}")
    print(json.dumps({**asdict(score), "status": score.status.value}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
