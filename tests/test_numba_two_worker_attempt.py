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
    text = command.argv[2]
    assert "/tmp/work/runtests.py /tmp/report.xml -m 2" in text
    assert "timeout --signal" not in text
    assert "numba.tests." not in text
    assert "build_ext --inplace" in text
    assert "refusing non-candidate import" in text
    assert command.failure_exit_codes == (1,)
