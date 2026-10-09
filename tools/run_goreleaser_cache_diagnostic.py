"""Opt-in offline GoReleaser cache diagnostic; never updates the official survey.

Build the separate image with the documented pinned parent first. --check-only
verifies read-only module access in a candidate checkout without running tests.
The full mode retains the public Go plan, reporter and existing Docker limits.
"""

from __future__ import annotations

import argparse
import json
import tempfile
from collections import Counter
from dataclasses import replace
from pathlib import Path

from agentless_ml.adapters.benchmarks import deepswe_test_plan, load_test_overrides
from agentless_ml.validation import DockerTestRunner
from agentless_ml.validation.docker import PublicTestCommand
from agentless_ml.workspace import LocalGitWorkspaceProvider, verify_sealed_repository

ROOT = Path(__file__).resolve().parents[1]
TASK = "goreleaser-retry-publish-auditing"
BASE = "399ef141161f212f4e81b5d7497b84633fc712d9"
PARENT = "sha256:778c43a00bb317e8e0b266b212b187be7765a12dbdadde3ba2f4bceba9c40080"
IMAGE = "agentless-ml/goreleaser-cache:2026-10-08"

CHECK = (
    "set -eu; cd /tmp/work; "
    "test \"$(go version)\" = 'go version go1.26.1 linux/amd64'; "
    "test \"$(go env GOMODCACHE)\" = /opt/agentless-go/modules; "
    "test \"$(go env GOTOOLCHAIN)\" = local; "
    "test \"$(go env GOPROXY)\" = off; "
    "GOCACHE=/tmp/go-build go list -m all; "
    "go version; echo OFFLINE_MODULE_CHECK_OK"
)


def diagnostic_command(plan):
    return cache_command(plan.command(timeout_seconds=1800))


def cache_command(native):
    """Reuse the verified seed/deadline setup without replacing caller targets."""
    # Go's content-addressed cache is a seed, not a substitute for candidate
    # source. Retain writable cache outputs and rebuild when source keys differ.
    prefix = (
        "set -e; mkdir -p /tmp/go-build; "
        "cp -a /opt/agentless-go/build-seed/. /tmp/go-build/; set +e; "
    )
    argv = (native.argv[0], native.argv[1], prefix + native.argv[2], *native.argv[3:])
    return replace(native, argv=("timeout", "--signal=TERM", "--kill-after=10s",
                                 f"{native.timeout_seconds:g}s", *argv))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--image-id", required=True, help="Verified derivative image ID")
    args = parser.parse_args()
    repository = ROOT.parent / "benchmarks/deepswe/repos" / TASK
    verify_sealed_repository(repository, BASE)
    runner = DockerTestRunner(
        args.image_id, ROOT.parent / "output/deepswe-survey/goreleaser-cache/logs",
        memory_mb=8192, cpus=2, tmpfs_mb=4096, pids_limit=2048,
        run_as_image_user=True,
    )
    provider = LocalGitWorkspaceProvider(
        repository, BASE, Path(tempfile.gettempdir()) / "agentless-ml-survey-workspaces",
    )
    with provider.create() as workspace:
        overrides = load_test_overrides(ROOT / "experiments/deepswe/test_overrides.json")
        plan = deepswe_test_plan("go", workspace.path, overrides.get(TASK))
        command = (PublicTestCommand(("sh", "-c", CHECK), timeout_seconds=120)
                   if args.check_only else diagnostic_command(plan))
        execution = runner.run(workspace.path, command)
    evidence = {
        "label": "substituted_environment_cache_relocation_diagnostic",
        "check_only": args.check_only, "task_id": TASK, "base_commit": BASE,
        "parent_image_id": PARENT, "image_id": runner.image_id,
        "official_survey_updated": False, "automatic_retry": False,
        "runner": plan.runner, "targets": list(plan.targets),
        "memory_mb": 8192, "cpus": 2, "tmpfs_mb": 4096, "pids_limit": 2048,
        "status": execution.result.status.value, "exit_code": execution.result.exit_code,
        "duration_seconds": execution.result.duration_seconds,
        "report_cases": len(execution.result.test_cases),
        "counts": dict(Counter(case.status.value for case in execution.result.test_cases)),
        "message": execution.message, "artifacts": execution.artifact_directory,
    }
    (Path(execution.artifact_directory) / "cache-diagnostic.json").write_text(
        json.dumps(evidence, indent=2) + "\n", encoding="utf-8",
    )
    print(json.dumps(evidence, indent=2), flush=True)
    return 0 if execution.result.exit_code == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
