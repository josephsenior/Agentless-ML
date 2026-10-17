"""One full native Numba two-worker attempt, with an explicit time allowance.

No automatic retry and no official override or survey mutation. Retains the
complete native report if the schedule finishes; partial progress is never
promoted to a baseline. Uses the resource diagnostic's unchanged Docker limits.
"""

import argparse
import json
import tempfile
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from agentless_ml.adapters.benchmarks.deepswe_execution import NUMBA_RUNTESTS
from agentless_ml.workspace import LocalGitWorkspaceProvider, verify_sealed_repository
from run_numba_resource_diagnostic import BASE, ROOT, TASK, SampledRunner


def full_command(timeout_seconds=1800):
    if type(timeout_seconds) is not int or not 1 <= timeout_seconds <= 10800:
        raise ValueError("full-attempt timeout must be an integer from 1 to 10800 seconds")
    # Native schedule and build stay identical; only the worker count changes.
    template = replace(NUMBA_RUNTESTS, script=NUMBA_RUNTESTS.script + " -m 2")
    command = template.command((), timeout_seconds=timeout_seconds)
    native = (command.argv[0], command.argv[1],
              "export AGENTLESS_NUMBA_DIAGNOSTIC=1; " + command.argv[2],
              *command.argv[3:])
    # Keep the deadline even if the host supervisor disappears. This covers
    # build, import checks and tests, not just the test phase.
    return replace(command, argv=("timeout", "--signal=TERM", "--kill-after=10s",
                                 f"{timeout_seconds}s", *native))


class FullBaselineRunner(SampledRunner):
    def capture_timings(self, name):
        # Full runs do not install the short diagnostic's timing hooks.
        # Resource samples and the native report are their evidence.
        pass

    def record_sample(self, name, sample):
        super().record_sample(name, {**sample, "observed_at": datetime.now(UTC).isoformat()})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout-seconds", type=int, default=1800,
                        help="Explicit allowance for this attempt only, at most 10800 seconds")
    parser.add_argument("--artifact-root", type=Path,
                        default=ROOT.parent / "output/deepswe-survey/numba-two-worker-full")
    args = parser.parse_args()
    command = full_command(args.timeout_seconds)
    repository = ROOT.parent / "benchmarks/deepswe/repos" / TASK
    verify_sealed_repository(repository, BASE)
    runner = FullBaselineRunner()
    runner.artifact_root = args.artifact_root / "logs"
    args.artifact_root.mkdir(parents=True, exist_ok=True)
    started = {
        "started_at": datetime.now(UTC).isoformat(), "task_id": TASK,
        "base_commit": BASE, "image_id": runner.image_id,
        "workers": 2, "timeout_seconds": args.timeout_seconds,
        "container_timeout_seconds": args.timeout_seconds,
        "memory_mb": runner.memory_mb, "cpus": runner.cpus,
        "scratch_mode": runner.scratch_mode, "swap_policy": runner.swap_policy,
        "environment": {"OPENBLAS_NUM_THREADS": "1", "XDG_CACHE_HOME": "/tmp/numba-user-cache"},
        "automatic_retry": False, "official_survey_updated": False,
        "official_override_changed": False, "verifier_run": False,
        "command": command.argv,
    }
    with (args.artifact_root / "attempt-started.json").open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(started, indent=2) + "\n")
    print(json.dumps({key: value for key, value in started.items() if key != "command"}), flush=True)
    provider = LocalGitWorkspaceProvider(
        repository, BASE, Path(tempfile.gettempdir()) / "agentless-ml-survey-workspaces",
    )
    try:
        with provider.create() as workspace:
            execution = runner.run(workspace.path, command)
    finally:
        runner.stop_sampling.set()
        if runner.sampler:
            runner.sampler.join(timeout=20)
    evidence = {
        "label": "full_public_schedule_two_worker_attempt", "task_id": TASK,
        "base_commit": BASE, "image_id": runner.image_id, "workers": 2,
        "timeout_seconds": args.timeout_seconds, "container_timeout_seconds": args.timeout_seconds,
        "started_at": started["started_at"], "finished_at": datetime.now(UTC).isoformat(),
        "scratch_mode": runner.scratch_mode, "swap_policy": runner.swap_policy,
        "environment": {"OPENBLAS_NUM_THREADS": "1", "XDG_CACHE_HOME": "/tmp/numba-user-cache"},
        "automatic_retry": False,
        "official_override_changed": False, "official_survey_updated": False,
        "status": execution.result.status.value, "exit_code": execution.result.exit_code,
        "report_cases": len(execution.result.test_cases),
        "artifacts": execution.artifact_directory, "samples": runner.samples,
    }
    target = Path(execution.artifact_directory) / "full-attempt.json"
    target.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in evidence.items() if key != "samples"}, indent=2))
    print(target)


if __name__ == "__main__":
    main()
