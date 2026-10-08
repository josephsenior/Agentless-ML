"""The opt-in full attempt keeps the complete schedule and existing limits."""

from pathlib import Path


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
    assert "refusing non-candidate import" in text
    assert command.failure_exit_codes == (1,)


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
