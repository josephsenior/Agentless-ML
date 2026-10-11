"""One Wazero short-mode diagnostic; never a full baseline or survey refresh."""

import json
import subprocess
import tempfile
import threading
import time
from collections import Counter
from dataclasses import replace
from pathlib import Path

from agentless_ml.adapters.benchmarks import deepswe_test_plan
from agentless_ml.validation import DockerTestRunner
from agentless_ml.workspace import LocalGitWorkspaceProvider, verify_sealed_repository
from run_pebble_compile_diagnostic import FINAL_PROBE, PebbleCompileRunner

ROOT = Path(__file__).resolve().parents[1]
TASK = "wazero-multi-module-snapshots"
BASE = "3ec1e028c8cbda984a71bf72321008723ebdcb51"
IMAGE = "sha256:919deb52eb7b2bf568155881aac94349d93c711c5edddeced559138bfbd3c66f"
ARTIFACTS = ROOT.parent / "output/deepswe-diagnostics/wazero-short-8g"


def diagnostic_command(plan):
    command = plan.command(timeout_seconds=1800)
    if plan.runner != "go" or plan.targets != ("./...",):
        raise ValueError("expected ordinary Go root-module ./... plan")
    return replace(command, argv=(
        *command.argv[:4], "-short", "-p", "1", "-parallel", "1", *plan.targets,
    ))


class WazeroShortRunner(PebbleCompileRunner):
    def __init__(self):
        # Reuse sampling lifecycle/final probes only; never initialize Pebble.
        DockerTestRunner.__init__(
            self, IMAGE, ARTIFACTS / "logs", memory_mb=8192, cpus=2,
            tmpfs_mb=4096, pids_limit=2048, run_as_image_user=True,
        )
        if self.image_id != IMAGE:
            raise ValueError("Wazero diagnostic requires its original pinned image")
        self.samples = []
        self.stop_sampling = threading.Event()
        self.sampler = None
        self.final_state = self.observed_host_config = self.final_probe = None
        self.go_event_tail = b""

    def sample(self, name):
        started = time.monotonic()
        probe = FINAL_PROBE + (
            '; if [ -f /tmp/go-test.json ]; then echo GO_PROGRESS; '
            'tail -n 2 /tmp/go-test.json; fi'
        )
        while not self.stop_sampling.is_set():
            try:
                result = subprocess.run(
                    ["docker", "exec", name, "/bin/sh", "-c", probe],
                    capture_output=True, text=True, timeout=15, check=False,
                )
                sample = {
                    "seconds": round(time.monotonic() - started, 2),
                    "exit_code": result.returncode,
                    "stdout": result.stdout, "stderr": result.stderr,
                }
            except subprocess.TimeoutExpired:
                sample = {"seconds": round(time.monotonic() - started, 2),
                          "error": "resource probe timeout"}
            self.record_sample(name, sample)
            print(f"Wazero SHORT-MODE diagnostic resource sample {sample['seconds']}s",
                  flush=True)
            self.stop_sampling.wait(10)

    def _docker(self, *args, **kwargs):
        result = super()._docker(*args, **kwargs)
        if args[0] == "inspect":
            self.go_event_tail = self._tail_file(args[1], "/tmp/go-test.json")
        return result


def main():
    repository = ROOT.parent / "benchmarks/deepswe/repos" / TASK
    verify_sealed_repository(repository, BASE)
    runner = WazeroShortRunner()
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
        "condition": "Wazero short-mode diagnostic, NOT a full baseline",
        "task_id": TASK, "base_commit": BASE, "image_id": runner.image_id,
        "short_mode": True, "targets": list(plan.targets),
        "package_workers": 1, "parallel_tests": 1, "timeout_seconds": 1800,
        "memory_mb": 8192, "cpus": 2, "tmpfs_mb": 4096, "pids_limit": 2048,
        "cache_seeded": False, "automatic_retry": False,
        "full_baseline": False, "accepted_regression_inventory": False,
        "official_survey_updated": False, "readiness": "109/113",
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
    (directory / "short-diagnostic.json").write_text(
        json.dumps(evidence, indent=2) + "\n", encoding="utf-8",
    )
    print(json.dumps({key: value for key, value in evidence.items()
                      if key != "samples"}, indent=2), flush=True)


if __name__ == "__main__":
    main()
