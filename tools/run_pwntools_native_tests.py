"""Run an explicitly substituted Pwntools native environment, not the survey.

Defaults to public assembly, SSH and example documentation pages. --full runs
the entire unchanged public suite; --public-docker-schedule applies only the
three documented public Docker page exclusions. No mode changes readiness.
Artifacts accumulate in unique runner directories; nothing is deleted.
"""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from agentless_ml.adapters.benchmarks import deepswe_test_command
from agentless_ml.validation import DockerTestRunner
from agentless_ml.workspace import LocalGitWorkspaceProvider

ROOT = Path(__file__).resolve().parents[1]
TASK = "pwntools-tube-multiplexing"
BASE = "76894a5404a65d2800b6d0adaf3485ecba275caa"
PUBLIC_DOCKER_EXCLUSIONS = ("gdb.rst", "adb.rst", "protocols.rst")


def apply_public_docker_schedule(workspace: Path) -> None:
    """Mirror only doctest3's three empty pages in our disposable checkout."""
    for name in PUBLIC_DOCKER_EXCLUSIONS:
        (workspace / "docs/source" / name).write_text("", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="agentless-ml/pwntools-native:2026-10-07")
    parser.add_argument("--repositories", type=Path, default=ROOT.parent / "benchmarks/deepswe/repos")
    parser.add_argument("--artifacts", type=Path, default=ROOT.parent / "output/deepswe-survey/pwntools-native-2026-10-07")
    schedule = parser.add_mutually_exclusive_group()
    schedule.add_argument("--full", action="store_true")
    schedule.add_argument("--public-docker-schedule", action="store_true")
    parser.add_argument("--timeout-seconds", type=float, default=300)
    arguments = parser.parse_args()
    targets = () if arguments.full or arguments.public_docker_schedule else (
        "source/asm.rst", "source/tubes/ssh.rst", "source/testexample.rst",
    )
    runner = DockerTestRunner(
        arguments.image, arguments.artifacts / "logs", memory_mb=8192,
        cpus=2, tmpfs_mb=4096, pids_limit=2048, run_as_image_user=True,
    )
    provider = LocalGitWorkspaceProvider(arguments.repositories / TASK, BASE, arguments.artifacts / "workspaces")
    with provider.create() as workspace:
        if arguments.public_docker_schedule:
            apply_public_docker_schedule(workspace.path)
        execution = runner.run(workspace.path, deepswe_test_command(
            "pwntools-native-doctest", targets, timeout_seconds=arguments.timeout_seconds,
        ))
    result = execution.result
    print(f"DIAGNOSTIC ONLY: image={runner.image_id} user={runner.user} targets={list(targets)}")
    print(f"documented Docker exclusions={list(PUBLIC_DOCKER_EXCLUSIONS) if arguments.public_docker_schedule else []}")
    print(f"status={result.status.value} exit={result.exit_code} duration={result.duration_seconds:.1f}s")
    print(f"groups={dict(Counter(case.status.value for case in result.test_cases))}")
    print(f"artifacts={execution.artifact_directory}")
    if execution.message:
        print(execution.message)
    return 0 if result.status.value == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
