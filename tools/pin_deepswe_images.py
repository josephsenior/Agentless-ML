"""Record the registry digest of every DeepSWE task's published image.

A task names its image by tag, e.g.
``public.ecr.aws/d3j8x8q7/swe-bench-202605:kh79...-v1.1``. A tag can be moved to
different contents at any time; a digest cannot. This looks up each tag's
top-level digest from the registry, without downloading the image, and writes
the mapping into ``experiments/deepswe/corpus_pin.json`` as
``container_digests``. Loading tasks with that mapping makes the controller
refuse to run a task in any image other than the pinned one.

    python tools/pin_deepswe_images.py --tasks-root ../benchmarks/deep-swe/tasks

On Docker's containerd image store, which is the default here, the local image
ID after a pull equals this registry digest, and that ID is what the runner
compares against the pin.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from agentless_ml.adapters.benchmarks import DeepSWEDataset, DeepSWEDatasetPin, pinned_load_options

ROOT = Path(__file__).resolve().parents[1]
PIN = ROOT / "experiments" / "deepswe" / "corpus_pin.json"
_DIGEST = re.compile(r"^Digest:\s+(sha256:[0-9a-f]{64})\s*$", re.MULTILINE)
_MEDIA = re.compile(r"^MediaType:\s+(\S+)\s*$", re.MULTILINE)


def _resolve(reference: str) -> tuple[str, str]:
    result = subprocess.run(
        ["docker", "buildx", "imagetools", "inspect", reference],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    digest, media = _DIGEST.search(result.stdout), _MEDIA.search(result.stdout)
    if result.returncode or not digest or not media:
        raise RuntimeError(f"{reference}: {(result.stderr or result.stdout).strip()[:300]}")
    return digest.group(1), media.group(1)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tasks-root", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args()

    pin = json.loads(PIN.read_text(encoding="utf-8"))
    tasks = DeepSWEDataset(
        args.tasks_root,
        DeepSWEDatasetPin(
            revision=pin["revision"],
            agent_files_sha256=pin["agent_files_sha256"],
            task_count=pin["task_count"],
        ),
    ).load_tasks(**pinned_load_options(pin))

    def resolve(task):
        try:
            return task.instance_id, task.container_image, *_resolve(task.container_image), None
        except (RuntimeError, subprocess.TimeoutExpired) as error:
            return task.instance_id, task.container_image, None, None, str(error)

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(resolve, tasks))

    failures = [r for r in results if r[4]]
    media = sorted({r[3] for r in results if r[3]})
    for task_id, _, _, _, error in failures:
        print(f"FAILED {task_id}: {error}")
    print(f"resolved {len(results) - len(failures)}/{len(results)}; media types: {media}")
    if failures:
        return 1

    digests = {task_id: digest for task_id, _, digest, _, _ in results}
    # Tasks on the same repository and base commit may legitimately share one.
    print(f"distinct digests: {len(set(digests.values()))}")
    pin["container_digests"] = dict(sorted(digests.items()))
    # newline="\n": on Windows write_text would otherwise emit CRLF.
    PIN.write_text(json.dumps(pin, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {len(digests)} digests to {PIN.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
