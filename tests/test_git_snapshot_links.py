"""Preserve Linux link behavior without reading linked host destinations."""

import os
import shutil
import subprocess
import tarfile
from pathlib import Path

import pytest

from agentless_ml.validation import DockerTestRunner, PublicTestCommand
from agentless_ml.validation.docker import DockerError, _snapshot


def git(repository, *args, data=None):
    env = {key: value for key, value in os.environ.items() if not key.upper().startswith("GIT_")}
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
    return subprocess.run(["git", "-c", "core.autocrlf=false", "-c", "core.symlinks=false",
                           "-c", "user.name=Snapshot tests", "-c", "user.email=tests@example.invalid",
                           *args], cwd=repository, env=env, input=data,
                          capture_output=True, check=True).stdout


def repository(tmp_path, links):
    source = tmp_path / "repo"
    source.mkdir()
    git(source, "init")
    (source / "dir").mkdir()
    (source / "dir" / "value.txt").write_bytes(b"candidate data\n")
    (source / "run.sh").write_bytes(b"#!/bin/sh\nprintf 'candidate data\\n'\n")
    git(source, "add", ".")
    git(source, "update-index", "--chmod=+x", "run.sh")
    for name, target in links.items():
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(target.encode("utf-8"))
        oid = git(source, "hash-object", "-w", "--stdin", data=target.encode("utf-8")).decode().strip()
        git(source, "update-index", "--add", "--cacheinfo", "120000", oid, name)
    git(source, "commit", "-m", "pinned links")
    return source


def test_windows_placeholders_become_links_last_and_preserve_executable_mode(tmp_path):
    links = {"file-link": "dir/value.txt", "directory-link": "dir",
             "chain": "file-link", "dangling": "missing.txt", "script-link": "run.sh"}
    source = repository(tmp_path, links)
    (source / "dir" / "value.txt").write_bytes(b"edited candidate\n")
    snapshot = tmp_path / "source.tar"
    _snapshot(source, snapshot)
    with tarfile.open(snapshot) as archive:
        assert not any(".git" in Path(name).parts for name in archive.getnames())
        for name, target in links.items():
            info = archive.getmember(name)
            assert info.issym() and info.linkname == target
        members = archive.getmembers()
        assert all(info.issym() for info in members[-len(links):])
        assert archive.getmember("run.sh").mode == 0o755
        assert archive.extractfile("dir/value.txt").read() == b"edited candidate\n"
    assert (source / "file-link").read_text() == "dir/value.txt"


@pytest.mark.parametrize("links", [
    {"link": "../outside"}, {"link": "/dev/null"}, {"link": "C:/outside"},
    {"link": "..\\outside"}, {"link": ".git/config"},
    {"link": ".GIT/config"}, {"link": "git~1/config"},
    {"link": "link"}, {"a": "b", "b": "a"},
    {"alias": ".", "link": "alias/../outside"},
    {"alias": ".", "link": "alias/.git/config"},
])
def test_unsafe_link_metadata_is_rejected_before_archiving(tmp_path, links):
    source = repository(tmp_path, links)
    target = tmp_path / "source.tar"
    with pytest.raises(DockerError):
        _snapshot(source, target)
    assert not target.exists()


def test_parent_components_are_resolved_after_directory_links(tmp_path):
    # Lexically collapsing alias/.. would incorrectly reject this as an escape.
    source = repository(tmp_path, {"alias": "dir", "link": "alias/../run.sh"})
    _snapshot(source, tmp_path / "source.tar")


@pytest.mark.parametrize("change", ["changed", "missing", "directory", "binary"])
def test_tracked_link_cannot_be_silently_changed_or_removed(tmp_path, change):
    source = repository(tmp_path, {"link": "dir/value.txt"})
    path = source / "link"
    if change == "changed":
        path.write_text("other.txt")
    elif change == "binary":
        path.write_bytes(b"\xff")
    else:
        path.unlink()
        if change == "directory":
            path.mkdir()
    with pytest.raises(DockerError):
        _snapshot(source, tmp_path / "source.tar")


def test_native_tracked_links_are_not_followed(tmp_path):
    source = repository(tmp_path, {"directory-link": "dir"})
    link = source / "directory-link"
    link.unlink()
    try:
        link.symlink_to("dir", target_is_directory=True)
    except OSError:
        pytest.skip("host cannot create native symlinks")
    snapshot = tmp_path / "source.tar"
    _snapshot(source, snapshot)
    with tarfile.open(snapshot) as archive:
        assert archive.getmember("directory-link").issym()
        assert not any(name.startswith("directory-link/") for name in archive.getnames())


def test_untracked_host_symlink_is_refused_even_to_an_internal_file(tmp_path):
    source = repository(tmp_path, {})
    try:
        (source / "untracked").symlink_to("run.sh")
    except OSError:
        pytest.skip("host cannot create native symlinks")
    with pytest.raises(DockerError, match="unsupported snapshot entry"):
        _snapshot(source, tmp_path / "source.tar")


@pytest.mark.skipif(not os.environ.get("AGENTLESS_SNAPSHOT_DOCKER_IMAGE"),
                    reason="opt-in Linux snapshot extraction check")
def test_linux_container_observes_links_not_windows_placeholder_files(tmp_path):
    source = repository(tmp_path, {"file-link": "dir/value.txt", "directory-link": "dir",
                                   "chain": "file-link", "dangling": "missing.txt",
                                   "script-link": "run.sh"})
    (source / "dir" / "value.txt").write_bytes(b"edited candidate\n")
    runner = DockerTestRunner(os.environ["AGENTLESS_SNAPSHOT_DOCKER_IMAGE"], tmp_path / "logs")
    command = PublicTestCommand(("sh", "-c", """
      set -e; cd /tmp/work
      test -L file-link; test -L directory-link; test -L chain; test -L dangling
      test ! -e dangling
      test "$(cat chain)" = 'edited candidate'
      test "$(cat directory-link/value.txt)" = 'edited candidate'
      test "$(./script-link)" = 'candidate data'
      test ! -e .git
    """))
    execution = runner.run(source, command)
    assert execution.result.status.value == "pass", execution.message


@pytest.mark.skipif(not os.environ.get("AGENTLESS_NATIVE_SNAPSHOT_IMAGE"),
                    reason="opt-in native Linux symlink safety checks")
def test_snapshot_safety_checks_with_native_linux_host_links(tmp_path):
    source = tmp_path / "linux-check"
    source.mkdir()
    project = Path(__file__).resolve().parents[1]
    shutil.copytree(project / "src" / "agentless_ml", source / "src" / "agentless_ml",
                    ignore=shutil.ignore_patterns("__pycache__"))
    tests = source / "native-tests"
    tests.mkdir()
    shutil.copyfile(__file__, tests / "test_snapshot.py")
    runner = DockerTestRunner(os.environ["AGENTLESS_NATIVE_SNAPSHOT_IMAGE"],
                              tmp_path / "logs", memory_mb=512, tmpfs_mb=512)
    # Both nested Docker checks stay skipped: this container has no socket or
    # image access. Its native host-link tests run on Linux without elevation.
    execution = runner.run(source, PublicTestCommand(("sh", "-c",
        "cd /tmp/work && PYTHONPATH=/tmp/work/src python -m pytest "
        "-p no:cacheprovider native-tests/test_snapshot.py -q"), timeout_seconds=120))
    assert execution.result.status.value == "pass", execution.message
