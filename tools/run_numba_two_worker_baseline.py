"""One full native Numba two-worker attempt, capped at 1800 seconds.

No automatic retry and no official override or survey mutation. Retains the
complete native report if the schedule finishes; partial progress is never
promoted to a baseline. Uses the resource diagnostic's unchanged Docker limits.
"""

import json
import tempfile
from dataclasses import replace
from pathlib import Path

from agentless_ml.adapters.benchmarks.deepswe_execution import NUMBA_RUNTESTS
from agentless_ml.workspace import LocalGitWorkspaceProvider, verify_sealed_repository
from run_numba_resource_diagnostic import BASE, ROOT, TASK, SampledRunner


def full_command():
    # Native schedule and build stay identical; only the worker count changes.
    template = replace(NUMBA_RUNTESTS, script=NUMBA_RUNTESTS.script + " -m 2")
    command = template.command((), timeout_seconds=1800)
    return replace(command, argv=(command.argv[0], command.argv[1],
                                 "export AGENTLESS_NUMBA_DIAGNOSTIC=1; " + command.argv[2],
                                 *command.argv[3:]))


def main():
    repository = ROOT.parent / "benchmarks/deepswe/repos" / TASK
    verify_sealed_repository(repository, BASE)
    runner = SampledRunner()
    runner.artifact_root = ROOT.parent / "output/deepswe-survey/numba-two-worker-full/logs"
    provider = LocalGitWorkspaceProvider(
        repository, BASE, Path(tempfile.gettempdir()) / "agentless-ml-survey-workspaces",
    )
    try:
        with provider.create() as workspace:
            execution = runner.run(workspace.path, full_command())
    finally:
        runner.stop_sampling.set()
        if runner.sampler:
            runner.sampler.join(timeout=20)
    evidence = {
        "label": "full_public_schedule_two_worker_attempt", "task_id": TASK,
        "base_commit": BASE, "image_id": runner.image_id, "workers": 2,
        "timeout_seconds": 1800, "automatic_retry": False,
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
