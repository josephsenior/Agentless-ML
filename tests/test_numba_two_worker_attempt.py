"""The opt-in full attempt keeps the complete schedule and existing limits."""

from pathlib import Path

import pytest


def test_full_attempt_has_native_report_without_short_cutoff(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "tools"))
    import run_numba_two_worker_baseline as attempt
    from agentless_ml.adapters.benchmarks.deepswe_execution import NUMBA_RUNTESTS

    command = attempt.full_command()
    assert command.timeout_seconds == 1800
    assert command.report == NUMBA_RUNTESTS.report
    assert command.counted_test_ids is None
    assert command.argv[:4] == ("timeout", "--signal=TERM", "--kill-after=10s", "1800s")
    text = command.argv[6]
    assert "/tmp/work/runtests.py /tmp/report.xml -m 2" in text
    assert "timeout --signal" not in text
    assert "numba.tests." not in text
    assert "build_ext --inplace" in text
    assert "export OPENBLAS_NUM_THREADS=1;" in text
    assert text.index("export XDG_CACHE_HOME=/tmp/numba-user-cache;") < text.index("python setup.py")
    assert 'mkdir -p "$XDG_CACHE_HOME" || exit 125;' in text
    assert "export NUMBA_CACHE_DIR=" not in text
    assert "refusing non-candidate import" in text
    assert command.failure_exit_codes == (1,)


def test_three_hour_attempt_preserves_schedule_and_reports(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "tools"))
    import run_numba_two_worker_baseline as attempt

    default = attempt.full_command()
    extended = attempt.full_command(10800)
    assert extended.timeout_seconds == 10800
    assert extended.argv[:4] == ("timeout", "--signal=TERM", "--kill-after=10s", "10800s")
    assert extended.argv[4:] == default.argv[4:]
    assert extended.report == default.report
    assert extended.counted_test_ids is None
    assert extended.failure_exit_codes == default.failure_exit_codes
    for invalid in (0, -1, 10801, 1.5, True):
        with pytest.raises(ValueError, match="integer"):
            attempt.full_command(invalid)


def test_registered_numba_timeout_defaults_and_explicit_override(tmp_path):
    from agentless_ml.adapters.benchmarks.deepswe_execution import (
        load_test_overrides, deepswe_test_plan,
    )
    override = load_test_overrides(
        Path(__file__).resolve().parents[1] / "experiments/deepswe/test_overrides.json"
    )["numba-stencil-boundary-modes"]
    plan = deepswe_test_plan("python", tmp_path, override)
    assert plan.command().timeout_seconds == 10800
    assert plan.command(timeout_seconds=None).argv[3] == "10800s"
    assert plan.command(timeout_seconds=60).timeout_seconds == 60
    assert plan.command(timeout_seconds=60).argv[3] == "60s"
    ordinary = deepswe_test_plan("go", tmp_path)
    assert ordinary.command().timeout_seconds == 1800


@pytest.mark.parametrize("invalid", [0, -1, True, 1.5, "10800"])
def test_registered_timeout_rejects_invalid_allowance(tmp_path, invalid):
    import json
    from agentless_ml.adapters.benchmarks.deepswe_execution import load_test_overrides
    path = tmp_path / "override.json"
    path.write_text(json.dumps({"example": {"timeout_seconds": invalid,
                                            "reason": "reviewed allowance"}}))
    with pytest.raises(ValueError, match="timeout_seconds must be a positive integer"):
        load_test_overrides(path)


def test_full_run_does_not_collect_uninstalled_diagnostic_hooks(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "tools"))
    import run_numba_two_worker_baseline as attempt

    runner = attempt.FullBaselineRunner.__new__(attempt.FullBaselineRunner)
    monkeypatch.setattr(attempt.SampledRunner, "capture_timings",
                        lambda *args: pytest.fail("full baseline has no timing hooks to collect"))
    runner.capture_timings("owned-container")


def test_short_diagnostic_matches_registered_resource_settings(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "tools"))
    import run_numba_resource_diagnostic as diagnostic
    from agentless_ml.validation import DockerTestRunner

    received = {}

    def capture(self, *args, **kwargs):
        received.update(kwargs)

    monkeypatch.setattr(DockerTestRunner, "__init__", capture)
    diagnostic.SampledRunner()
    assert received["memory_mb"] == 8192 and received["cpus"] == 2
    assert received["scratch_mode"] == "volume"
    assert received["swap_policy"] == "docker-default"
    command = diagnostic.diagnostic_command()
    text = command.argv[2]
    assert text.index("export OPENBLAS_NUM_THREADS=1;") < text.index("python setup.py")
    assert "export NUMBA_NUM_THREADS=" not in text
    assert "300s" in text and text.endswith("/tmp/diagnostic-report.xml -m 2")
    assert command.timeout_seconds == 1800 and command.report is None


def test_samples_are_saved_before_the_run_finishes(tmp_path, monkeypatch):
    import json
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "tools"))
    from run_numba_resource_diagnostic import SampledRunner
    runner = SampledRunner.__new__(SampledRunner)
    runner.artifact_root = tmp_path
    runner.samples = []
    (tmp_path / "owned-container").mkdir()
    runner.record_sample("owned-container", {"seconds": 10, "stdout": "first"})
    path = tmp_path / "owned-container/resource-samples.jsonl"
    assert json.loads(path.read_text()) == runner.samples[0]
    runner.record_sample("owned-container", {"seconds": 20, "error": "probe timeout"})
    assert [json.loads(line) for line in path.read_text().splitlines()] == runner.samples
