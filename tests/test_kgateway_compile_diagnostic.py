from pathlib import Path
import pytest


def test_compile_window_has_no_execution_or_package_filter(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "tools"))
    from run_kgateway_compile_diagnostic import diagnostic_command
    command = diagnostic_command()
    script = command.argv[2]
    assert "timeout --signal=TERM --kill-after=10s 300s" in script
    assert "go test -c -p 1 -o /dev/null ./..." in script
    assert "GOCACHE=/tmp/go-build GOTMPDIR=/tmp/compile-work" in script
    assert "-run" not in script and "-exec" not in script
    assert "cp -" not in script
    assert command.report is None
    assert command.counted_test_ids is None
    assert command.timeout_seconds == 1800


def test_full_compile_uses_existing_outer_cap_without_short_cutoff(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "tools"))
    from run_kgateway_compile_diagnostic import diagnostic_command
    command = diagnostic_command(full=True)
    script = command.argv[2]
    assert "go test -c -p 1 -o /dev/null ./..." in script
    assert "timeout --" not in script
    assert "300s" not in script
    assert "-run" not in script and "-exec" not in script
    assert command.timeout_seconds == 1800
    assert command.report is None and command.counted_test_ids is None


def test_sampler_uses_unchanged_limits_without_numba_initialization(monkeypatch, tmp_path):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "tools"))
    import run_kgateway_compile_diagnostic as diagnostic
    captured = {}
    def initialize(self, image, artifacts, **kwargs):
        captured.update(image=image, artifacts=artifacts, **kwargs)
    monkeypatch.setattr(diagnostic.DockerTestRunner, "__init__", initialize)
    diagnostic.CompileSampledRunner()
    assert captured["image"] == diagnostic.IMAGE
    assert captured["memory_mb"] == 8192
    assert captured["tmpfs_mb"] == 4096
    assert captured["cpus"] == 2
    assert captured["pids_limit"] == 2048


def test_keep_awake_released_on_exception(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "tools"))
    from run_kgateway_compile_diagnostic import keep_host_awake
    calls = []
    def set_state(flags):
        calls.append(flags)
        return 0x80000000
    with pytest.raises(ValueError):
        with keep_host_awake(True, set_state):
            raise ValueError("attempt failed")
    assert calls == [0x80000001, 0x80000000]


def test_keep_awake_rejection_prevents_attempt(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "tools"))
    from run_kgateway_compile_diagnostic import keep_host_awake
    with pytest.raises(RuntimeError, match="rejected"):
        with keep_host_awake(True, lambda flags: 0):
            pytest.fail("must not start")
