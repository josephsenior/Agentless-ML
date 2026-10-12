"""Five-minute, two-worker public schedule sample. Never a survey baseline.

Uses the existing pinned image and candidate build, without changing the
official override. The command retains the 1800-second outer limit; an inner
300-second window deliberately stops test execution and discards partial results.
Uses the registered disk-backed scratch, Docker-default swap and BLAS cap.
"""

from __future__ import annotations

import json
import shlex
import subprocess
import tempfile
import threading
import time
from pathlib import Path

from agentless_ml.adapters.benchmarks.deepswe_execution import _NUMBA_IMPORT_CHECK
from agentless_ml.adapters.benchmarks.deepswe_numba import NUMBA_REPORTER
from agentless_ml.validation import DockerTestRunner, PublicTestCommand
from agentless_ml.workspace import LocalGitWorkspaceProvider, verify_sealed_repository
from numba_test_timing import COLLECT_TIMINGS, TIMING_HELPER, summarize_timings

ROOT = Path(__file__).resolve().parents[1]
TASK = "numba-stencil-boundary-modes"
BASE = "5781334aa654972fdc749003e7c1e93e6d277110"
IMAGE = "sha256:d30747d56f59cb61bb9a4e87ba8dc4df29ccbb471a1a1146f20d5d9d58fa90ac"
ARTIFACTS = ROOT.parent / "output/deepswe-survey/numba-two-worker-diagnostic"


def diagnostic_command() -> PublicTestCommand:
    install = "from pathlib import Path; Path('/tmp/numba_diagnostic_timing.py').write_text(" + repr(TIMING_HELPER) + ")"
    reporter = "import numba_diagnostic_timing; numba_diagnostic_timing.install();\n" + NUMBA_REPORTER
    script = (
        "cd /tmp/work || exit 125; export PYTHONPATH=/tmp/work/src:/tmp/work; "
        "export OPENBLAS_NUM_THREADS=1; "
        "command -v timeout || exit 125; "
        "python setup.py build_ext --inplace || exit 125; "
        f"python -c {shlex.quote(_NUMBA_IMPORT_CHECK)} || exit 125; "
        f"python -c {shlex.quote(install)} || exit 125; "
        "export PYTHONPATH=/tmp:/tmp/work/src:/tmp/work; "
        "echo NUMBA_RESOURCE_DIAGNOSTIC_ONLY_300_SECONDS; "
        "AGENTLESS_NUMBA_DIAGNOSTIC=1 timeout --signal=TERM --kill-after=10s 300s "
        f"python -u -c {shlex.quote(reporter)} "
        "/tmp/work/runtests.py /tmp/diagnostic-report.xml -m 2"
    )
    # Even a complete early finish does not become a regression inventory.
    return PublicTestCommand(("/bin/sh", "-c", script), timeout_seconds=1800)


class SampledRunner(DockerTestRunner):
    def __init__(self):
        super().__init__(IMAGE, ARTIFACTS / "logs", memory_mb=8192, cpus=2,
                         pids_limit=2048, tmpfs_mb=4096, scratch_mode="volume",
                         swap_policy="docker-default", run_as_image_user=True)
        self.samples = []
        self.stop_sampling = threading.Event()
        self.sampler = None

    def _docker(self, *args, **kwargs):
        if args[0] == "rm":
            self.stop_sampling.set()
            if self.sampler:
                self.sampler.join(timeout=20)
            self.capture_timings(args[-1])
        result = super()._docker(*args, **kwargs)
        if args[0] == "start":
            self.sampler = threading.Thread(target=self.sample, args=(args[1],), daemon=True)
            self.sampler.start()
        return result

    def capture_timings(self, name):
        target = self.artifact_root / name / "test-timings.json"
        try:
            result = super()._docker("exec", name, "python", "-c", COLLECT_TIMINGS)
            if result.returncode:
                raise RuntimeError(result.stderr.decode(errors="replace"))
            snapshot = json.loads(result.stdout)
            target.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
            summary = summarize_timings(snapshot)
        except (RuntimeError, ValueError, OSError) as error:
            summary = {"capture_error": str(error), "accepted_regression_inventory": False}
        (target.parent / "test-timing-summary.json").write_text(
            json.dumps(summary, indent=2) + "\n", encoding="utf-8",
        )

    def sample(self, name):
        started = time.monotonic()
        # cgroup totals include both workers, the parent and charged page cache.
        probe = (
            'for f in memory.current memory.peak memory.events memory.swap.current cpu.stat pids.current; '
            'do echo "FILE:$f"; cat "/sys/fs/cgroup/$f"; done; '
            'echo PROCESSES; ps -eo pid,ppid,rss,args; '
            'echo PROGRESS; tail -n 4 /tmp/agentless-stdout'
        )
        while not self.stop_sampling.is_set():
            try:
                result = subprocess.run(
                    ["docker", "exec", name, "/bin/sh", "-c", probe],
                    capture_output=True, text=True, timeout=15, check=False,
                )
                self.record_sample(name, {"seconds": round(time.monotonic() - started, 2),
                                     "exit_code": result.returncode,
                                     "stdout": result.stdout, "stderr": result.stderr})
                print(f"resource sample {self.samples[-1]['seconds']}s", flush=True)
            except subprocess.TimeoutExpired:
                self.record_sample(name, {"seconds": round(time.monotonic() - started, 2),
                                     "error": "resource probe timeout"})
            self.stop_sampling.wait(10)

    def record_sample(self, name, sample):
        self.samples.append(sample)
        # The runner created this owned artifact directory before starting
        # the container. Do not hold the only copy until the run ends.
        with (self.artifact_root / name / "resource-samples.jsonl").open(
            "a", encoding="utf-8", newline="\n",
        ) as stream:
            stream.write(json.dumps(sample) + "\n")


def main():
    repository = ROOT.parent / "benchmarks/deepswe/repos" / TASK
    verify_sealed_repository(repository, BASE)
    runner = SampledRunner()
    provider = LocalGitWorkspaceProvider(
        repository, BASE, Path(tempfile.gettempdir()) / "agentless-ml-survey-workspaces",
    )
    try:
        with provider.create() as workspace:
            execution = runner.run(workspace.path, diagnostic_command())
    finally:
        runner.stop_sampling.set()
        if runner.sampler:
            runner.sampler.join(timeout=20)
    evidence = {
        "label": "resource_diagnostic_only_not_baseline", "task_id": TASK,
        "base_commit": BASE, "image_id": runner.image_id, "workers": 2,
        "test_window_seconds": 300, "outer_timeout_seconds": 1800,
        "scratch_mode": runner.scratch_mode, "swap_policy": runner.swap_policy,
        "environment": {"OPENBLAS_NUM_THREADS": "1"},
        "schedule": "native full public schedule; deliberately time-bounded, no selectors",
        "accepted_regression_inventory": False,
        "status": execution.result.status.value, "exit_code": execution.result.exit_code,
        "artifacts": execution.artifact_directory, "samples": runner.samples,
    }
    target = Path(execution.artifact_directory) / "resource-diagnostic.json"
    target.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in evidence.items() if key != "samples"}, indent=2))
    print(target)


if __name__ == "__main__":
    main()
