from pathlib import Path

import pytest

from agentless_ml.adapters.benchmarks import deepswe_test_plan


def load(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "tools"))
    import run_pebble_schedule_diagnostic
    return run_pebble_schedule_diagnostic


def test_only_package_concurrency_changes(monkeypatch, tmp_path):
    diagnostic = load(monkeypatch)
    (tmp_path / "go.mod").write_text("module github.com/cockroachdb/pebble\n")
    plan = deepswe_test_plan("go", tmp_path)
    command = diagnostic.diagnostic_command(plan)
    original = plan.command(timeout_seconds=1800)
    assert plan.targets == ("./...",)
    assert command.argv[4:] == original.argv[4:] == ("./...",)
    assert command.argv[2].replace("go test -json -count=1 -p 1 ", "go test -json -count=1 ") == original.argv[2]
    assert command.report == original.report
    assert command.failure_exit_codes == original.failure_exit_codes
    assert command.timeout_seconds == 1800
    assert "-run" not in command.argv[2] and "timeout --" not in command.argv[2]


def test_non_go_plan_is_refused(monkeypatch, tmp_path):
    diagnostic = load(monkeypatch)
    with pytest.raises(ValueError, match="ordinary Go"):
        diagnostic.diagnostic_command(deepswe_test_plan("python", tmp_path))


def test_full_run_has_separate_artifacts_and_same_limits(monkeypatch):
    diagnostic = load(monkeypatch)
    import run_pebble_compile_diagnostic as compile_diagnostic
    captured = {}
    def initialize(self, image, artifacts, **kwargs):
        captured.update(image=image, artifacts=artifacts, **kwargs)
        self.image_id = image
    monkeypatch.setattr(compile_diagnostic.DockerTestRunner, "__init__", initialize)
    runner = diagnostic.FullScheduleRunner()
    assert captured["image"] == diagnostic.IMAGE
    assert captured["artifacts"] == diagnostic.ARTIFACTS / "logs"
    assert captured["memory_mb"] == 8192 and captured["tmpfs_mb"] == 4096
    assert captured["cpus"] == 2 and captured["pids_limit"] == 2048
    assert runner.samples == [] and runner.go_event_tail == b""
