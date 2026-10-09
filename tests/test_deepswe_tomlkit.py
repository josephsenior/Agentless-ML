import hashlib
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from agentless_ml.adapters.benchmarks.deepswe_execution import (
    TEST_COMMANDS, deepswe_test_command, deepswe_test_plan, load_test_overrides,
)
from agentless_ml.adapters.benchmarks.deepswe_tomlkit import (
    INDEX, _safe_path, provision_fixtures, verify_candidate_import,
)


@pytest.fixture
def source(tmp_path):
    root = tmp_path / "image"
    root.mkdir()
    files = {
        INDEX: b"valid/a.toml\nvalid/a.json\ninvalid/b.toml\ninvalid/encoding/c.toml\n",
        "tests/valid/a.toml": b"a = 1\n",
        "tests/valid/a.json": b'{"a": {"type": "integer", "value": "1"}}',
        "tests/invalid/b.toml": b"a = \n",
        "tests/invalid/encoding/c.toml": b"\xff\xfe",
        "README.md": b"not copied",
        "runner.py": b"raise RuntimeError('not copied')",
    }
    for name, content in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    def git(*args):
        return subprocess.check_output(["git", "-C", str(root), *args])

    git("init", "-q")
    git("config", "core.autocrlf", "false")
    git("config", "user.name", "Fixture")
    git("config", "user.email", "fixture@example.invalid")
    git("add", ".")
    git("commit", "-qm", "public fixture snapshot")
    commit = git("rev-parse", "HEAD").decode().strip()
    manifest = []
    for record in git("ls-tree", "-rz", "HEAD").split(b"\0"):
        if not record:
            continue
        metadata, path = record.split(b"\t", 1)
        mode, kind, oid = metadata.decode().split()
        name = path.decode()
        data = files[name]
        manifest.append({"path": name, "mode": mode, "git_blob": oid,
                         "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    digest = hashlib.sha256(json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()
    return root, commit, digest, files


def test_only_indexed_data_is_copied_exactly(source, tmp_path):
    root, commit, digest, files = source
    destination = tmp_path / "candidate/tests/toml-test"
    destination.mkdir(parents=True)
    record = provision_fixtures(root, destination, commit, digest)
    copied = {path.relative_to(destination).as_posix(): path.read_bytes()
              for path in destination.rglob("*") if path.is_file()}
    assert copied == {name: data for name, data in files.items() if name.startswith("tests/")}
    assert record["verified_source_files"] == 7 and record["copied_files"] == 5
    assert record["fixture_index_entries"] == 4
    assert record["source_manifest_sha256"] == digest
    assert not (destination / ".git").exists()


@pytest.mark.parametrize("path", ["", "../outside.toml", "/outside.toml", "valid/../../outside.toml", "valid\\outside.toml"])
def test_unsafe_fixture_paths_are_refused(path):
    with pytest.raises(ValueError, match="unsafe public fixture path"):
        _safe_path(path)


@pytest.mark.parametrize("problem", ["commit", "manifest", "changed_data", "changed_nonfixture", "occupied"])
def test_setup_refuses_mismatch_or_overwrite_before_copying(source, tmp_path, problem):
    root, commit, digest, files = source
    destination = tmp_path / "candidate/tests/toml-test"
    if problem == "commit":
        commit = "0" * 40
    elif problem == "manifest":
        digest = "0" * 64
    elif problem in ("changed_data", "changed_nonfixture"):
        (root / ("tests/valid/a.toml" if problem == "changed_data" else "README.md")).write_bytes(b"changed")
    else:
        destination.mkdir(parents=True)
        (destination / "candidate.txt").write_bytes(b"keep")
    with pytest.raises(ValueError):
        provision_fixtures(root, destination, commit, digest)
    if problem == "occupied":
        assert list(destination.iterdir()) == [destination / "candidate.txt"]
        assert (destination / "candidate.txt").read_bytes() == b"keep"
    else:
        assert not destination.exists()


def test_setup_refuses_a_destination_link(source, tmp_path):
    root, commit, digest, files = source
    real = tmp_path / "elsewhere"
    real.mkdir()
    link = tmp_path / "candidate"
    try:
        link.symlink_to(real, target_is_directory=True)
    except OSError:
        pytest.skip("host cannot create directory symlinks")
    with pytest.raises(ValueError, match="symlink"):
        provision_fixtures(root, link / "tests/toml-test", commit, digest)
    assert not list(real.iterdir())


@pytest.mark.parametrize("image", [False, True])
def test_tomlkit_import_origin_is_checked(tmp_path, monkeypatch, image):
    candidate = tmp_path / "candidate/tomlkit"
    parent = tmp_path / "image/tomlkit" if image else candidate
    monkeypatch.setitem(sys.modules, "tomlkit", SimpleNamespace(__file__=str(parent / "__init__.py")))
    if image:
        with pytest.raises(ValueError, match="non-candidate import"):
            verify_candidate_import(candidate)
    else:
        verify_candidate_import(candidate)


def test_tomlkit_plan_preserves_pytest_schedule_arguments_and_limits(tmp_path):
    overrides = Path(__file__).resolve().parents[1] / "experiments/deepswe/test_overrides.json"
    plan = deepswe_test_plan("python", tmp_path, load_test_overrides(overrides)["tomlkit-toml-table-converters"])
    assert plan.runner == "tomlkit-pytest" and plan.targets == ()
    command = plan.command(timeout_seconds=123)
    assert command.report == TEST_COMMANDS["pytest"].report
    assert command.failure_exit_codes == (1,) and command.timeout_seconds == 123
    assert command.argv[2].split("python -m pytest", 1)[1] == TEST_COMMANDS["pytest"].script.split("python -m pytest", 1)[1]
    assert "|| exit 125" in command.argv[2]
    assert "export PYTHONPATH=/tmp/work/src:/tmp/work;" in command.argv[2]
    assert "submodule update" not in command.argv[2] and "pip install" not in command.argv[2]
    assert deepswe_test_command("tomlkit-pytest", ("tests/test_api.py",)).argv[4:] == ("tests/test_api.py",)
