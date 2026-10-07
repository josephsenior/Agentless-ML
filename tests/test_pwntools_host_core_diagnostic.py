"""Test restoration and explicit opt-in without touching WSL or Docker."""

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("host_core", ROOT / "tools/run_pwntools_host_core_diagnostic.py")
diagnostic = importlib.util.module_from_spec(spec)
spec.loader.exec_module(diagnostic)


def test_host_change_requires_explicit_opt_in(monkeypatch):
    monkeypatch.setattr(diagnostic.sys, "argv", ["diagnostic"])
    monkeypatch.setattr(diagnostic.subprocess, "check_output", lambda *a, **k: pytest.fail("No host calls before opt-in"))
    with pytest.raises(SystemExit) as error:
        diagnostic.main()
    assert error.value.code == 2


def test_original_pattern_is_one_literal_exec_argument(monkeypatch):
    calls = []
    monkeypatch.setattr(diagnostic.subprocess, "run", lambda *a, **k: calls.append((a, k)))
    diagnostic.set_pattern(diagnostic.EXPECTED_ORIGINAL)
    arguments = calls[0][0][0]
    assert arguments[-1] == "kernel.core_pattern=|/wsl-capture-crash %t %E %p %s"
    assert arguments[-3:-1] == ["/sbin/sysctl", "-w"]
    assert "--exec" in arguments and "sh" not in arguments
    assert calls[0][1] == {"check": True, "timeout": 30}


@pytest.mark.parametrize("pattern", [diagnostic.TEMPORARY, diagnostic.NONCOLLIDING])
def test_restore_changes_temporary_value_back_and_checks_it(monkeypatch, pattern):
    values = iter([pattern, diagnostic.EXPECTED_ORIGINAL])
    writes = []
    monkeypatch.setattr(diagnostic, "read_setting", lambda _: next(values))
    monkeypatch.setattr(diagnostic, "set_pattern", writes.append)
    diagnostic.restore(diagnostic.EXPECTED_ORIGINAL, pattern)
    assert writes == [diagnostic.EXPECTED_ORIGINAL]


def test_restore_does_not_overwrite_concurrent_changes(monkeypatch):
    monkeypatch.setattr(diagnostic, "read_setting", lambda _: "unrelated-setting")
    monkeypatch.setattr(diagnostic, "set_pattern", lambda _: pytest.fail("Concurrent value must not be overwritten"))
    with pytest.raises(RuntimeError, match="concurrently"):
        diagnostic.restore(diagnostic.EXPECTED_ORIGINAL)


def test_restore_rejects_failed_verification(monkeypatch):
    monkeypatch.setattr(diagnostic, "read_setting", lambda _: diagnostic.TEMPORARY)
    monkeypatch.setattr(diagnostic, "set_pattern", lambda _: None)
    with pytest.raises(RuntimeError, match="not restored"):
        diagnostic.restore(diagnostic.EXPECTED_ORIGINAL)


def test_already_restored_value_is_not_written_again(monkeypatch):
    monkeypatch.setattr(diagnostic, "read_setting", lambda _: diagnostic.EXPECTED_ORIGINAL)
    monkeypatch.setattr(diagnostic, "set_pattern", lambda _: pytest.fail("Already restored"))
    diagnostic.restore(diagnostic.EXPECTED_ORIGINAL)


@pytest.mark.parametrize("failure", ["apply", "probe", "schedule"])
@pytest.mark.parametrize("pattern", [diagnostic.TEMPORARY, diagnostic.NONCOLLIDING])
def test_controller_restores_after_failures(monkeypatch, tmp_path, failure, pattern):
    monkeypatch.setattr(diagnostic.sys, "argv", ["diagnostic", "--apply-temporary-host-setting", "--artifacts", str(tmp_path), "--pattern", pattern])
    monkeypatch.setattr(diagnostic.subprocess, "check_output",
                        lambda command, **_: diagnostic.IMAGE_ID if "inspect" in command else "")
    state = {"pattern": diagnostic.EXPECTED_ORIGINAL}
    monkeypatch.setattr(diagnostic, "read_setting", lambda name: state["pattern"] if name == "kernel.core_pattern" else "0")

    def set_pattern(value):
        state["pattern"] = value
        if value == pattern and failure == "apply":
            raise RuntimeError("Failure after applying setting")

    def run(command, **kwargs):
        is_probe = command[0] == "docker"
        return subprocess.CompletedProcess(command, 1 if not is_probe or failure == "probe" else 0,
                                           stdout=b"diagnostic output", stderr=b"")

    monkeypatch.setattr(diagnostic, "set_pattern", set_pattern)
    monkeypatch.setattr(diagnostic.subprocess, "run", run)
    if failure == "schedule":
        assert diagnostic.main() == 1
    else:
        with pytest.raises(RuntimeError):
            diagnostic.main()
    assert state["pattern"] == diagnostic.EXPECTED_ORIGINAL
    evidence = json.loads(next(tmp_path.glob("diagnostic-*/host-setting.json")).read_text())
    assert evidence["restored"] is True
    assert evidence["final_core_uses_pid"] == "0"
    assert evidence["temporary_core_pattern"] == pattern


def test_restore_does_not_accept_the_other_diagnostic_pattern(monkeypatch):
    monkeypatch.setattr(diagnostic, "read_setting", lambda _: diagnostic.TEMPORARY)
    monkeypatch.setattr(diagnostic, "set_pattern", lambda _: pytest.fail("Unexpected concurrent change"))
    with pytest.raises(RuntimeError, match="concurrently"):
        diagnostic.restore(diagnostic.EXPECTED_ORIGINAL, diagnostic.NONCOLLIDING)


def test_noncolliding_probe_requires_both_guest_and_native_checks():
    assert "assert core.eip == core.eax == core.fault_addr" in diagnostic.PROBE
    assert "assert core.arch == 'arm'" in diagnostic.PROBE
    assert "dump_inventory" in diagnostic.PROBE
