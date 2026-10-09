from pathlib import Path


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
