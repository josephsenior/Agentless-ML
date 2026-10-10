from pathlib import Path


def load(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "tools"))
    import run_pebble_compile_diagnostic
    return run_pebble_compile_diagnostic


def test_diagnostic_only_compiles_the_failed_package(monkeypatch):
    diagnostic = load(monkeypatch)
    command = diagnostic.diagnostic_command()
    text = command.argv[2]
    assert "go test -c -p 1 -o /tmp/pebble-valblk.test ./sstable/valblk;" in text
    assert "timeout --signal=TERM --kill-after=10s 300s" in text
    assert "GOCACHE=/tmp/go-build" in text
    assert 'rc=$?' in text and 'exit "$rc"' in text
    assert command.timeout_seconds == 1800
    assert command.report is None and command.counted_test_ids is None
    assert "-run" not in text and "./..." not in text and "cp " not in text


def test_sampler_keeps_published_image_and_limits(monkeypatch):
    diagnostic = load(monkeypatch)
    captured = {}
    def initialize(self, image, artifacts, **kwargs):
        captured.update(image=image, artifacts=artifacts, **kwargs)
        self.image_id = image
    monkeypatch.setattr(diagnostic.DockerTestRunner, "__init__", initialize)
    runner = diagnostic.PebbleCompileRunner()
    assert captured["image"] == diagnostic.IMAGE
    assert captured["memory_mb"] == 8192 and captured["cpus"] == 2
    assert captured["tmpfs_mb"] == 4096 and captured["pids_limit"] == 2048
    assert captured["run_as_image_user"] is True
    assert runner.samples == [] and runner.sampler is None


def test_final_state_and_memory_counters_are_retained(monkeypatch):
    import json
    from subprocess import CompletedProcess
    diagnostic = load(monkeypatch)
    runner = object.__new__(diagnostic.PebbleCompileRunner)
    keys = ("NetworkMode", "ReadonlyRootfs", "CapDrop", "SecurityOpt",
            "Memory", "MemorySwap", "NanoCpus", "PidsLimit", "Tmpfs",
            "Privileged", "ExtraHosts", "PortBindings", "Binds")
    metadata = {"State": {"Running": True, "OOMKilled": False},
                "HostConfig": dict.fromkeys(keys)}
    def docker(*args, **kwargs):
        if args[0] == "inspect":
            return CompletedProcess(args, 0, json.dumps([metadata]).encode(), b"")
        assert args[:3] == ("exec", "owned-container", "/bin/sh")
        assert "memory.events" in args[-1]
        return CompletedProcess(args, 0, b"oom_kill 0", b"")
    monkeypatch.setattr(diagnostic.DockerTestRunner, "_docker", staticmethod(docker))
    runner._docker("inspect", "owned-container")
    assert runner.final_state == metadata["State"]
    assert runner.final_probe["stdout"] == "oom_kill 0"
    assert runner.observed_host_config == metadata["HostConfig"]
