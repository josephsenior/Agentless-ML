from pathlib import Path

import pytest

from agentless_ml.adapters.benchmarks import deepswe_test_plan


def load(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "tools"))
    import run_wazero_short_diagnostic
    return run_wazero_short_diagnostic


def test_short_mode_keeps_original_script_reporting_and_deadline(monkeypatch, tmp_path):
    diagnostic = load(monkeypatch)
    plan = deepswe_test_plan("go", tmp_path)
    original = plan.command()
    command = diagnostic.diagnostic_command(plan)
    assert command.argv[:4] == original.argv[:4]
    assert command.argv[4:] == ("-short", "-p", "1", "-parallel", "1", "./...")
    assert command.report == original.report
    assert command.failure_exit_codes == original.failure_exit_codes
    assert command.timeout_seconds == 1800
    assert command.counted_test_ids is None
    assert "GOGC" not in command.argv[2] and "GOMEMLIMIT" not in command.argv[2]


def test_wrong_plan_is_refused(monkeypatch, tmp_path):
    diagnostic = load(monkeypatch)
    with pytest.raises(ValueError, match="ordinary Go"):
        diagnostic.diagnostic_command(deepswe_test_plan("python", tmp_path))
    (tmp_path / "go.work").write_text("go 1.24\nuse ./nested\n")
    with pytest.raises(ValueError, match="ordinary Go"):
        diagnostic.diagnostic_command(deepswe_test_plan("go", tmp_path))


def test_original_pin_limits_and_separate_artifacts(monkeypatch):
    diagnostic = load(monkeypatch)
    captured = {}
    def initialize(self, image, artifacts, **limits):
        captured.update(image=image, artifacts=artifacts, **limits)
        self.image_id = image
    monkeypatch.setattr(diagnostic.DockerTestRunner, "__init__", initialize)
    runner = diagnostic.WazeroShortRunner()
    assert captured == dict(
        image=diagnostic.IMAGE, artifacts=diagnostic.ARTIFACTS / "logs",
        memory_mb=8192, cpus=2, tmpfs_mb=4096, pids_limit=2048,
        run_as_image_user=True,
    )
    assert "deepswe-diagnostics" in str(diagnostic.ARTIFACTS)
    assert runner.samples == [] and runner.go_event_tail == b""


def test_mismatched_image_is_refused(monkeypatch):
    diagnostic = load(monkeypatch)
    def initialize(self, *args, **kwargs):
        self.image_id = "sha256:wrong"
    monkeypatch.setattr(diagnostic.DockerTestRunner, "__init__", initialize)
    with pytest.raises(ValueError, match="original pinned image"):
        diagnostic.WazeroShortRunner()
