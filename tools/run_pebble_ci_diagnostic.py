"""Verify Pebble's upstream CI skips, then run one full CI-mode diagnostic."""

import json
import tempfile
from collections import Counter
from dataclasses import replace
from pathlib import Path

from agentless_ml.adapters.benchmarks import deepswe_test_plan
from agentless_ml.schemas import TestCaseStatus, ValidationStatus
from agentless_ml.workspace import LocalGitWorkspaceProvider, verify_sealed_repository
from run_pebble_schedule_diagnostic import (
    BASE, ROOT, TASK, FullScheduleRunner, diagnostic_command,
)

ARTIFACTS = ROOT.parent / "output/deepswe-survey/pebble-ci-mode-diagnostic"
SKIP_NAMES = (
    "TestSingularKVBlockRestartsOverflow",
    "TestExceedingMaximumRestartOffset",
    "TestMultipleKVBlockRestartsOverflow",
)
PACKAGE = "github.com/cockroachdb/pebble/sstable/rowblk"


def ci_command(plan, *, verify_only=False):
    command = diagnostic_command(plan)
    if verify_only:
        command = replace(command, argv=(
            *command.argv[:4], "-run", "^(" + "|".join(SKIP_NAMES) + ")$",
            "./sstable/rowblk",
        ))
    return replace(command, argv=("env", "CI=1", *command.argv))


def verified_skips(execution, event_tail):
    result = execution.result
    expected = {PACKAGE + "::" + name for name in SKIP_NAMES}
    if (result.status is not ValidationStatus.PASS or result.exit_code != 0
            or len(result.test_cases) != 3
            or {case.test_id for case in result.test_cases} != expected
            or any(case.status is not TestCaseStatus.SKIPPED for case in result.test_cases)):
        return False
    messages = {name: "" for name in SKIP_NAMES}
    for line in event_tail.splitlines():
        event = json.loads(line)
        if event.get("Package") == PACKAGE and event.get("Test") in messages:
            messages[event["Test"]] += event.get("Output", "")
    return all("Skipping test: requires too much memory for CI" in text
               for text in messages.values())


def run_phase(repository, phase):
    runner = FullScheduleRunner(artifact_root=ARTIFACTS / phase / "logs")
    try:
        with LocalGitWorkspaceProvider(
            repository, BASE, Path(tempfile.gettempdir()) / "agentless-ml-survey-workspaces",
        ).create() as workspace:
            plan = deepswe_test_plan("go", workspace.path)
            execution = runner.run(workspace.path, ci_command(plan, verify_only=phase == "verify-skips"))
    finally:
        runner.stop_sampling.set()
        if runner.sampler:
            runner.sampler.join(timeout=20)
    verified = verified_skips(execution, runner.go_event_tail) if phase == "verify-skips" else None
    record = {
        "condition": "upstream CI=1 public validation; diagnostic only",
        "phase": phase, "task_id": TASK, "base_commit": BASE,
        "image_id": runner.image_id, "ci": "1", "package_workers": 1,
        "targets": ["./sstable/rowblk"] if phase == "verify-skips" else list(plan.targets),
        "test_filter": list(SKIP_NAMES) if phase == "verify-skips" else None,
        "timeout_seconds": 1800, "cache_seeded": False,
        "automatic_retry": False, "official_survey_updated": False,
        "three_upstream_skips_verified": verified,
        "status": execution.result.status.value, "exit_code": execution.result.exit_code,
        "duration_seconds": execution.result.duration_seconds,
        "tests": len(execution.result.test_cases),
        "counts": dict(Counter(case.status.value for case in execution.result.test_cases)),
        "message": execution.message, "artifacts": execution.artifact_directory,
        "observed_host_config": runner.observed_host_config,
        "final_state": runner.final_state, "final_probe": runner.final_probe,
        "samples": runner.samples,
    }
    directory = Path(execution.artifact_directory)
    (directory / "go-events-tail.jsonl").write_bytes(runner.go_event_tail)
    (directory / "ci-diagnostic.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in record.items() if key != "samples"}, indent=2), flush=True)
    return verified


def main():
    repository = ROOT.parent / "benchmarks/deepswe/repos" / TASK
    verify_sealed_repository(repository, BASE)
    if not run_phase(repository, "verify-skips"):
        print("Skip verification failed; full schedule NOT started.", flush=True)
        return 1
    print("All three upstream CI skips verified; starting one full CI-mode schedule.", flush=True)
    run_phase(repository, "full-schedule")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
