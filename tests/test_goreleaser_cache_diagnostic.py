from pathlib import Path


def test_cache_diagnostic_preserves_full_public_plan(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "tools"))
    from run_goreleaser_cache_diagnostic import diagnostic_command
    from agentless_ml.adapters.benchmarks.deepswe_execution import GO, DeepSWETestPlan

    native = GO.command(("./...",), timeout_seconds=1800)
    command = diagnostic_command(DeepSWETestPlan("go", ("./...",)))
    assert command.argv[:4] == ("timeout", "--signal=TERM", "--kill-after=10s", "1800s")
    assert command.argv[6].endswith(native.argv[2])
    assert command.argv[-1] == "./..."
    assert command.report == native.report
    assert command.failure_exit_codes == native.failure_exit_codes
    assert command.timeout_seconds == 1800
    assert command.counted_test_ids is None


def test_image_only_relocates_existing_environment_caches(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "tools"))
    from run_goreleaser_cache_diagnostic import PARENT
    dockerfile = (Path(__file__).resolve().parents[1] /
                  "experiments/deepswe/goreleaser/Dockerfile.cache").read_text()
    assert "mv /tmp/gomodcache /opt/agentless-go/modules" in dockerfile
    assert "mv /tmp/gocache /opt/agentless-go/build-seed" in dockerfile
    assert "GOPROXY=off" in dockerfile
    assert "GOTOOLCHAIN=local" in dockerfile
    assert "go mod download" not in dockerfile
    assert "go build" not in dockerfile
    assert "COPY" not in dockerfile
    assert "@" + PARENT in dockerfile.splitlines()[0]
