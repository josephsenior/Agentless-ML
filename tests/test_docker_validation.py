import json
import os
import subprocess
import tarfile
from pathlib import Path

import pytest

from agentless_ml.repair import (
    build_patch_candidate,
    build_unified_diff,
    select_candidate,
)
from agentless_ml.schemas import ValidationStatus
from agentless_ml.validation import (
    DockerTestRunner,
    PublicTestCommand,
    validate_candidate,
)
from agentless_ml.validation.docker import DockerError, _snapshot
from agentless_ml.workspace import LocalGitWorkspaceProvider


@pytest.mark.parametrize(
    "kwargs",
    [
        {"argv": ()},
        {"argv": ("python\0",)},
        {"argv": ("python",), "timeout_seconds": 0},
        {"argv": ("python",), "timeout_seconds": float("nan")},
        {"argv": ("python",), "failure_exit_codes": (0,)},
        {"argv": ("python",), "failure_exit_codes": (137,)},
    ],
)
def test_invalid_command(kwargs):
    with pytest.raises(ValueError):
        PublicTestCommand(**kwargs)


def test_snapshot_excludes_history(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / ".git").mkdir()
    (source / ".git" / "secret").write_text("history")
    (source / "a.py").write_bytes(b"value = 1\n")
    target = tmp_path / "snapshot.tar"
    _snapshot(source, target)
    with tarfile.open(target) as archive:
        assert archive.getnames() == ["a.py"]
        assert archive.extractfile("a.py").read() == b"value = 1\n"


@pytest.mark.parametrize(
    "exit_code,oom,timed_out,expected",
    [
        (0, False, False, "pass"),
        (1, False, False, "fail"),
        (2, False, False, "harness_error"),
        (127, False, False, "harness_error"),
        (137, True, False, "out_of_memory"),
        (137, False, True, "timeout"),
    ],
)
def test_execution_outcomes_and_cleanup(
    tmp_path, monkeypatch, exit_code, oom, timed_out, expected
):
    calls = []

    def docker(*args, **kwargs):
        calls.append(args)
        output = b""
        if args[:2] == ("image", "inspect"):
            output = json.dumps(
                [{"Id": "sha256:fixed", "Os": "linux", "Config": {}}]
            ).encode()
        elif args[0] == "inspect":
            output = json.dumps(
                [{"State": {"ExitCode": exit_code, "OOMKilled": oom}}]
            ).encode()
        elif args[0] == "wait" and timed_out:
            raise subprocess.TimeoutExpired("docker wait", 1)
        elif args[0] == "logs":
            output = b"test evidence\n"
        return subprocess.CompletedProcess(args, 0, output, b"")

    monkeypatch.setattr(DockerTestRunner, "_docker", staticmethod(docker))
    source = tmp_path / "source"
    source.mkdir()
    runner = DockerTestRunner("python:local", tmp_path / "logs")
    execution = runner.run(source, PublicTestCommand(("python", "-m", "unittest")))
    assert execution.result.status.value == expected
    assert calls[-1][:3] == ("rm", "--force", "--volumes")
    create = next(call for call in calls if call[0] == "create")
    assert "--network=none" in create and "--read-only" in create
    assert "--cap-drop=ALL" in create and "--user=65534:65534" in create
    assert "sha256:fixed" in create
    assert not any(arg.startswith("--mount") or arg == "-v" for arg in create)
    record = json.loads(
        Path(execution.artifact_directory, "execution.json").read_text()
    )
    assert record["result"]["status"] == expected
    assert record["image_id"] == "sha256:fixed"


@pytest.mark.parametrize("failed_operation", ["create", "exec", "start", "logs", "rm"])
def test_docker_failures_never_become_test_failures(
    tmp_path, monkeypatch, failed_operation
):
    calls = []

    def docker(*args, **kwargs):
        calls.append(args[0])
        if args[0] == failed_operation:
            raise DockerError("injected infrastructure failure")
        output = b""
        if args[0] == "image":
            output = b'[{"Id":"sha256:fixed","Os":"linux","Config":{}}]'
        elif args[0] == "inspect":
            output = b'[{"State":{"ExitCode":0}}]'
        return subprocess.CompletedProcess(args, 0, output, b"")

    monkeypatch.setattr(DockerTestRunner, "_docker", staticmethod(docker))
    source = tmp_path / "source"
    source.mkdir()
    execution = DockerTestRunner("local", tmp_path / "logs").run(
        source, PublicTestCommand(("true",))
    )
    assert execution.result.status is ValidationStatus.HARNESS_ERROR
    assert calls[-1] == "rm"
    assert "infrastructure" in execution.message


@pytest.mark.parametrize(
    "metadata",
    [
        {"Id": "x", "Os": "windows", "Config": {}},
        {"Id": "x", "Os": "linux", "Config": {"Volumes": {"/data": {}}}},
    ],
)
def test_reject_incompatible_images(tmp_path, monkeypatch, metadata):
    monkeypatch.setattr(
        DockerTestRunner,
        "_docker",
        staticmethod(
            lambda *a, **k: subprocess.CompletedProcess(
                a, 0, json.dumps([metadata]).encode(), b""
            )
        ),
    )
    with pytest.raises(ValueError):
        DockerTestRunner("local", tmp_path)


docker_enabled = pytest.mark.skipif(
    os.environ.get("AGENTLESS_DOCKER_TESTS") != "1",
    reason="opt-in local Docker integration",
)


@docker_enabled
def test_real_two_candidate_selection(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    original = "def add(a, b):\n    return a - b\n"
    (source / "calculator.py").write_bytes(original.encode())
    (source / "test_public.py").write_text(
        "import unittest\nfrom calculator import add\n"
        "class TestAdd(unittest.TestCase):\n"
        "    def test_add(self):\n        self.assertEqual(add(2, 3), 5)\n",
        encoding="utf-8",
    )

    def git(*args):
        return (
            subprocess.run(
                [
                    "git",
                    "-c",
                    "core.autocrlf=false",
                    "-c",
                    "core.hooksPath=",
                    "-c",
                    "user.name=Tests",
                    "-c",
                    "user.email=test@example.invalid",
                    *args,
                ],
                cwd=source,
                capture_output=True,
                check=True,
            )
            .stdout.decode()
            .strip()
        )

    git("init")
    git("add", ".")
    git("commit", "-m", "public fixture")
    provider = LocalGitWorkspaceProvider(
        source_repository=source,
        base_commit=git("rev-parse", "HEAD"),
        workspace_root=tmp_path / "workspaces",
    )
    runner = DockerTestRunner(
        os.environ.get("AGENTLESS_TEST_IMAGE", "python:3.11-slim"), tmp_path / "logs"
    )
    command = PublicTestCommand(("python", "-m", "unittest", "-v", "test_public"))
    candidates = []
    for index, operator in enumerate(("*", "+")):
        candidate = build_patch_candidate(
            candidate_id=f"candidate-{index}",
            raw_response="prepared",
            diff=build_unified_diff(
                {"calculator.py": original},
                {"calculator.py": original.replace("a - b", f"a {operator} b")},
            ),
            localization_rank=0,
            sample_index=index,
        )
        candidates.append(validate_candidate(candidate, provider, runner, [command]))
    assert [c.validation[0].status for c in candidates] == [
        ValidationStatus.FAIL,
        ValidationStatus.PASS,
    ]
    assert select_candidate(candidates).candidate.candidate_id == "candidate-1"
    assert (source / "calculator.py").read_text() == original
    assert not list((tmp_path / "workspaces").iterdir())
    for record in (tmp_path / "logs").glob("*/execution.json"):
        name = json.loads(record.read_text())["container_name"]
        assert (
            subprocess.run(
                ["docker", "inspect", name], capture_output=True, check=False
            ).returncode
            != 0
        )


@docker_enabled
@pytest.mark.parametrize(
    "argv,timeout,status",
    [
        (("python", "-c", "import time; time.sleep(30)"), 1, ValidationStatus.TIMEOUT),
        (("missing-test-executable",), 30, ValidationStatus.HARNESS_ERROR),
        (
            (
                "python",
                "-c",
                (
                    "import os; assert os.getuid() != 0; "
                    "assert not os.path.exists('.git'); open('scratch', 'w').write('ok')"
                ),
            ),
            30,
            ValidationStatus.PASS,
        ),
    ],
)
def test_real_container_boundaries(tmp_path, argv, timeout, status):
    source = tmp_path / "source"
    source.mkdir()
    (source / ".git").mkdir()
    runner = DockerTestRunner(
        os.environ.get("AGENTLESS_TEST_IMAGE", "python:3.11-slim"), tmp_path / "logs"
    )
    execution = runner.run(source, PublicTestCommand(argv, timeout_seconds=timeout))
    assert execution.result.status is status, execution.message
    assert not (source / "scratch").exists()
