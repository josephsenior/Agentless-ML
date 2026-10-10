"""One full Pebble public-schedule diagnostic with -p 1, not a survey refresh."""

import json
import tempfile
from collections import Counter
from dataclasses import replace
from pathlib import Path

from agentless_ml.adapters.benchmarks import deepswe_test_plan
from agentless_ml.workspace import LocalGitWorkspaceProvider, verify_sealed_repository
from run_pebble_compile_diagnostic import (
    BASE, IMAGE, ROOT, TASK, PebbleCompileRunner,
)

ARTIFACTS = ROOT.parent / "output/deepswe-survey/pebble-full-single-worker-diagnostic"


def diagnostic_command(plan):
    command = plan.command(timeout_seconds=1800)
    script = command.argv[2]
    original = 'go test -json -count=1 "$@"'
    if plan.runner != "go" or script.count(original) != 1:
        raise ValueError("expected the unchanged ordinary Go public command")
    return replace(command, argv=(
        *command.argv[:2],
        script.replace(original, 'go test -json -count=1 -p 1 "$@"', 1),
        *command.argv[3:],
    ))


class FullScheduleRunner(PebbleCompileRunner):
    def __init__(self):
        super().__init__(artifact_root=ARTIFACTS / "logs")
        self.go_event_tail = b""

    def _docker(self, *args, **kwargs):
        result = super()._docker(*args, **kwargs)
        if args[0] == "inspect":
            self.go_event_tail = self._tail_file(args[1], "/tmp/go-test.json")
        return result


def main():
    repository = ROOT.parent / "benchmarks/deepswe/repos" / TASK
    verify_sealed_repository(repository, BASE)
    runner = FullScheduleRunner()
    try:
        with LocalGitWorkspaceProvider(
            repository, BASE, Path(tempfile.gettempdir()) / "agentless-ml-survey-workspaces",
        ).create() as workspace:
            plan = deepswe_test_plan("go", workspace.path)
            execution = runner.run(workspace.path, diagnostic_command(plan))
    finally:
        runner.stop_sampling.set()
        if runner.sampler:
            runner.sampler.join(timeout=20)
    evidence = {
        "condition": "full public schedule with one package worker; diagnostic only",
        "task_id": TASK, "base_commit": BASE, "image_id": runner.image_id,
        "runner": plan.runner, "targets": list(plan.targets),
        "package_workers": 1, "timeout_seconds": 1800,
        "cache_seeded": False, "official_survey_updated": False,
        "automatic_retry": False,
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
    target = directory / "full-schedule-diagnostic.json"
    target.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in evidence.items() if key != "samples"}, indent=2))
    print(target)


if __name__ == "__main__":
    main()
