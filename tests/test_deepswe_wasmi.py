import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from agentless_ml.adapters.benchmarks.deepswe_execution import (
    TEST_COMMANDS, deepswe_test_command, deepswe_test_plan, load_test_overrides,
)
from agentless_ml.adapters.benchmarks.deepswe_wasmi import provision_fixtures, _safe_path


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args])


def init(root, paths):
    git(root, "init", "-q")
    git(root, "config", "core.autocrlf", "false")
    git(root, "config", "user.name", "Fixture")
    git(root, "config", "user.email", "fixture@example.invalid")
    git(root, "add", "--", *paths)
    git(root, "commit", "-qm", "public fixture snapshot")
    return git(root, "rev-parse", "HEAD").decode().strip()


def digest(entries):
    return hashlib.sha256(json.dumps(entries, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()


@pytest.fixture
def image(tmp_path):
    root = tmp_path / "image"
    tests = root / "crates/wast/tests"
    tests.mkdir(parents=True)
    (tests / "mod.rs").write_text('fn one("spec/a");\nfn two("wasmi/nested/b");\n', encoding="utf-8")
    base = init(root, ["crates/wast/tests/mod.rs"])
    pins = {}
    for name, wanted in (("spec", "a.wast"), ("wasmi", "nested/b.wast")):
        submodule = tests / name
        submodule.mkdir()
        files = {wanted: b"(module)\n", "unused.wast": b"(module)\n", "README.md": b"not copied", "tool.rs": b"not copied"}
        for relative, data in files.items():
            path = submodule / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        commit = init(submodule, list(files))
        manifest = []
        for record in git(submodule, "ls-tree", "-rz", "HEAD").split(b"\0"):
            if not record:
                continue
            metadata, raw_path = record.split(b"\t", 1)
            mode, kind, blob = metadata.decode().split()
            relative = raw_path.decode()
            data = files[relative]
            manifest.append({"path": relative, "mode": mode, "git_blob": blob,
                             "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
        pins[name] = {"commit": commit, "manifest": digest(manifest),
                      "selected_manifest": digest([entry for entry in manifest if entry["path"] == wanted])}
    return root, base, pins


def test_copies_only_the_verified_allowlist_from_both_submodules(image, tmp_path):
    root, base, pins = image
    candidate = tmp_path / "candidate"
    summaries = provision_fixtures(root, candidate, base, pins)
    copied = {path.relative_to(candidate).as_posix(): path.read_bytes()
              for path in candidate.rglob("*") if path.is_file()}
    assert copied == {"crates/wast/tests/spec/a.wast": b"(module)\n",
                      "crates/wast/tests/wasmi/nested/b.wast": b"(module)\n"}
    assert [summary["copied_files"] for summary in summaries] == [1, 1]
    assert [summary["verified_source_files"] for summary in summaries] == [4, 4]
    assert not list(candidate.rglob(".git"))


@pytest.mark.parametrize("problem", ["base", "commit", "manifest", "selected_manifest", "modified_data", "modified_nonfixture", "occupied"])
def test_second_submodule_problem_prevents_all_copying(image, tmp_path, problem):
    root, base, pins = image
    candidate = tmp_path / "candidate"
    if problem == "base":
        base = "0" * 40
    elif problem in ("commit", "manifest", "selected_manifest"):
        pins["wasmi"][problem] = "0" * len(pins["wasmi"][problem])
    elif problem.startswith("modified"):
        relative = "nested/b.wast" if problem == "modified_data" else "README.md"
        (root / "crates/wast/tests/wasmi" / relative).write_bytes(b"changed")
    else:
        destination = candidate / "crates/wast/tests/wasmi"
        destination.mkdir(parents=True)
        (destination / "candidate.wast").write_bytes(b"keep")
    with pytest.raises(ValueError):
        provision_fixtures(root, candidate, base, pins)
    assert not (candidate / "crates/wast/tests/spec").exists()
    if problem == "occupied":
        assert (candidate / "crates/wast/tests/wasmi/candidate.wast").read_bytes() == b"keep"


@pytest.mark.parametrize("relative", ["", "../a.wast", "/a.wast", "nested/../../a.wast", "nested\\a.wast"])
def test_refuses_unsafe_wast_paths(relative):
    with pytest.raises(ValueError, match="unsafe"):
        _safe_path(relative)


def test_wasmi_preserves_the_existing_complete_nextest_command(tmp_path):
    override_file = Path(__file__).resolve().parents[1] / "experiments/deepswe/test_overrides.json"
    plan = deepswe_test_plan("rust", tmp_path, load_test_overrides(override_file)["wasmi-trap-coredumps"])
    assert plan.runner == "wasmi-cargo-nextest" and plan.targets == ()
    command = plan.command(timeout_seconds=123)
    native = TEST_COMMANDS["cargo-nextest"]
    assert command.report == native.report
    assert command.failure_exit_codes == (100,) and command.timeout_seconds == 123
    assert command.argv[2].endswith(native.script.split("cd /tmp/work && ", 1)[1])
    assert 'python -c ' in command.argv[2] and '|| exit 125;' in command.argv[2]
    assert "CARGO_NET_OFFLINE=true" in command.argv[2]
    assert "submodule update" not in command.argv[2]
    assert "-p wasmi" not in command.argv[2] and "--all-targets" not in command.argv[2]
    assert deepswe_test_command("wasmi-cargo-nextest", ("--lib",)).argv[4:] == ("--lib",)
