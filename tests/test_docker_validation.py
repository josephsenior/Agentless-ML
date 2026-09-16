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


def fake_docker(calls, *, exit_code=0, oom=False, running=True, timed_out=False, files=None, image_user=""):
    """A Docker CLI stand-in for the exec-based lifecycle.

    ``files`` maps container paths to the bytes a command left there.
    """
    files = files or {}

    def docker(*args, **kwargs):
        calls.append(args)
        if args[:2] == ("image", "inspect"):
            output = json.dumps([{"Id": "sha256:fixed", "Os": "linux", "Config": {"User": image_user}}])
            return subprocess.CompletedProcess(args, 0, output.encode(), b"")
        if args[0] == "inspect":
            state = {"Running": running, "OOMKilled": oom}
            return subprocess.CompletedProcess(args, 0, json.dumps([{"State": state}]).encode(), b"")
        if args[0] == "exec" and "public-test" in args:
            if timed_out:
                raise subprocess.TimeoutExpired("docker exec", 1)
            return subprocess.CompletedProcess(args, exit_code, b"", b"")
        if args[0] == "exec" and ("read-file" in args or "tail-file" in args):
            path = args[args.index("read-file" if "read-file" in args else "tail-file") + 1]
            if path in files:
                return subprocess.CompletedProcess(args, 0, files[path], b"")
            return subprocess.CompletedProcess(args, 1, b"", b"")
        return subprocess.CompletedProcess(args, 0, b"", b"")

    return docker


def run_fake(tmp_path, monkeypatch, command, run_as_image_user=False, **state):
    calls = []
    monkeypatch.setattr(DockerTestRunner, "_docker", staticmethod(fake_docker(calls, **state)))
    source = tmp_path / "source"
    source.mkdir(exist_ok=True)
    runner = DockerTestRunner(
        "python:local", tmp_path / "logs", run_as_image_user=run_as_image_user
    )
    return runner.run(source, command), calls


@pytest.mark.parametrize(
    "exit_code,oom,running,timed_out,expected",
    [
        (0, False, True, False, "pass"),
        (1, False, True, False, "fail"),
        (2, False, True, False, "harness_error"),
        (127, False, True, False, "harness_error"),
        (137, True, True, False, "out_of_memory"),
        (137, False, False, False, "harness_error"),
        (None, False, True, True, "timeout"),
    ],
)
def test_execution_outcomes_and_cleanup(
    tmp_path, monkeypatch, exit_code, oom, running, timed_out, expected
):
    execution, calls = run_fake(
        tmp_path,
        monkeypatch,
        PublicTestCommand(("python", "-m", "unittest")),
        exit_code=exit_code,
        oom=oom,
        running=running,
        timed_out=timed_out,
        files={"/tmp/agentless-stdout": b"test evidence\n"},
    )
    assert execution.result.status.value == expected
    assert calls[-1][:3] == ("rm", "--force", "--volumes")
    create = next(call for call in calls if call[0] == "create")
    assert "--network=none" in create and "--read-only" in create
    assert "--cap-drop=ALL" in create and "--user=65534:65534" in create
    assert "--env=HOME=/tmp" in create
    assert "sha256:fixed" in create
    assert not any(arg.startswith("--mount") or arg == "-v" for arg in create)
    tmpfs = create[create.index("--tmpfs") + 1]
    assert tmpfs.startswith("/tmp:") and ",exec," in tmpfs and "noexec" not in tmpfs
    # The command reaches the container only as positional exec arguments.
    assert "unittest" not in create
    command_exec = next(call for call in calls if "public-test" in call)
    assert command_exec[-3:] == ("python", "-m", "unittest")
    record = json.loads(
        Path(execution.artifact_directory, "execution.json").read_text()
    )
    assert record["result"]["status"] == expected
    assert record["image_id"] == "sha256:fixed"
    assert record["report"] is None
    assert record["user"] == {"run_as_image_user": False, "user": "65534:65534"}
    # Output is still collected after a timeout: it explains what was running.
    assert Path(execution.artifact_directory, "stdout.log").read_bytes() == b"test evidence\n"


@pytest.mark.parametrize("image_user,expected_user", [("", "root"), ("node", "node")])
def test_run_as_image_user_keeps_every_other_restriction(
    tmp_path, monkeypatch, image_user, expected_user
):
    execution, calls = run_fake(
        tmp_path,
        monkeypatch,
        PublicTestCommand(("go", "test", "./...")),
        run_as_image_user=True,
        image_user=image_user,
    )
    assert execution.result.status is ValidationStatus.PASS
    create = next(call for call in calls if call[0] == "create")
    # The image decides the user and HOME, so toolchains find their own caches.
    assert not any(arg.startswith("--user") for arg in create)
    assert not any(arg.startswith("--env=HOME") for arg in create)
    for restriction in ("--network=none", "--read-only", "--cap-drop=ALL",
                        "--security-opt=no-new-privileges", "--pull=never", "--init"):
        assert restriction in create
    assert not any(arg.startswith("--mount") or arg == "-v" for arg in create)
    record = json.loads(Path(execution.artifact_directory, "execution.json").read_text())
    assert record["user"] == {"run_as_image_user": True, "user": expected_user}


JUNIT = b"""<?xml version="1.0" encoding="utf-8"?>
<testsuites><testsuite name="pytest" tests="3">
<testcase classname="tests.test_calc" name="test_add"/>
<testcase classname="tests.test_calc" name="test_sub"><failure message="boom"/></testcase>
<testcase classname="tests.test_calc" name="test_skip"><skipped/></testcase>
</testsuite></testsuites>"""


@pytest.mark.parametrize(
    "exit_code,files,expected,cases,message",
    [
        (1, {"/tmp/work/report.xml": JUNIT}, "fail", 3, ""),
        (0, {"/tmp/work/report.xml": JUNIT}, "harness_error", 0, "contradicts"),
        (1, {}, "harness_error", 0, "was not written"),
        (1, {"/tmp/work/report.xml": b"<not xml"}, "harness_error", 0, "malformed"),
        (
            1,
            {"/tmp/work/report.xml": JUNIT.replace(b"<failure message=\"boom\"/>", b"")},
            "harness_error",
            0,
            "shows no failed test",
        ),
    ],
)
def test_declared_report_becomes_per_test_evidence(
    tmp_path, monkeypatch, exit_code, files, expected, cases, message
):
    from agentless_ml.validation import ReportFormat, TestReport

    command = PublicTestCommand(
        ("python", "-m", "pytest", "--junitxml=report.xml"),
        report=TestReport(ReportFormat.JUNIT_XML, "report.xml"),
    )
    execution, _ = run_fake(tmp_path, monkeypatch, command, exit_code=exit_code, files=files)
    assert execution.result.status.value == expected
    assert len(execution.result.test_cases) == cases
    assert message in execution.message
    record = json.loads(Path(execution.artifact_directory, "execution.json").read_text())
    assert record["report"]["format"] == "junit-xml"
    if cases:
        assert record["report"]["artifact"] == "report.xml"
        assert Path(execution.artifact_directory, "report.xml").read_bytes() == JUNIT
        assert execution.result.failure_count() == 1


def test_report_is_not_read_after_infrastructure_failure(tmp_path, monkeypatch):
    from agentless_ml.validation import ReportFormat, TestReport

    command = PublicTestCommand(
        ("pytest",), report=TestReport(ReportFormat.JUNIT_XML, "/tmp/report.xml")
    )
    execution, calls = run_fake(
        tmp_path, monkeypatch, command, timed_out=True, files={"/tmp/report.xml": JUNIT}
    )
    assert execution.result.status is ValidationStatus.TIMEOUT
    assert not any("read-file" in call for call in calls)


@pytest.mark.parametrize("failed_operation", ["create", "exec", "start", "inspect", "rm"])
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


@docker_enabled
@pytest.mark.parametrize("exit_code,status", [(1, ValidationStatus.FAIL), (0, ValidationStatus.PASS)])
def test_real_report_is_read_from_read_only_container(tmp_path, exit_code, status):
    from agentless_ml.validation import ReportFormat, TestReport

    source = tmp_path / "source"
    source.mkdir()
    failure = "<failure message='x'/>" if exit_code else ""
    # Written by the command itself inside /tmp/work, then read before removal.
    (source / "write_report.py").write_text(
        "import sys\n"
        "open('report.xml', 'w').write(\"<testsuites><testsuite>"
        "<testcase classname='suite' name='kept'/>"
        f"<testcase classname='suite' name='changed'>{failure}</testcase>"
        "</testsuite></testsuites>\")\n"
        f"sys.exit({exit_code})\n",
        encoding="utf-8",
    )
    runner = DockerTestRunner(
        os.environ.get("AGENTLESS_TEST_IMAGE", "python:3.11-slim"), tmp_path / "logs"
    )
    command = PublicTestCommand(
        ("python", "write_report.py"),
        report=TestReport(ReportFormat.JUNIT_XML, "report.xml"),
    )
    execution = runner.run(source, command)
    assert execution.result.status is status, execution.message
    assert [(c.test_id, c.status.value) for c in execution.result.test_cases] == [
        ("suite::kept", "passed"),
        ("suite::changed", "failed" if exit_code else "passed"),
    ]
    assert Path(execution.artifact_directory, "report.xml").exists()
    assert not (source / "report.xml").exists()


@docker_enabled
def test_real_out_of_memory_is_not_a_test_failure(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    runner = DockerTestRunner(
        os.environ.get("AGENTLESS_TEST_IMAGE", "python:3.11-slim"),
        tmp_path / "logs",
        memory_mb=64,
    )
    command = PublicTestCommand(
        ("python", "-c", "b = bytearray(512 * 1024 * 1024); print(len(b))"),
        timeout_seconds=60,
    )
    execution = runner.run(source, command)
    assert execution.result.status is ValidationStatus.OUT_OF_MEMORY, execution.message


@docker_enabled
def test_real_image_user_keeps_read_only_root_and_no_network(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    # Checks run by the command itself, inside the container.
    (source / "check.py").write_text(
        "import os, socket, subprocess\n"
        "assert os.getuid() == 0, os.getuid()\n"
        "try:\n    open('/usr/agentless-probe', 'w')\nexcept OSError:\n    pass\n"
        "else:\n    raise SystemExit('root filesystem is writable')\n"
        "try:\n    socket.create_connection(('1.1.1.1', 53), timeout=2)\n"
        "except OSError:\n    pass\nelse:\n    raise SystemExit('network is reachable')\n"
        "open('/tmp/tool.sh', 'w').write('#!/bin/sh\\necho compiled-ok\\n')\n"
        "os.chmod('/tmp/tool.sh', 0o755)\n"
        "assert subprocess.run(['/tmp/tool.sh'], capture_output=True, text=True).stdout.strip() == 'compiled-ok'\n",
        encoding="utf-8",
    )
    runner = DockerTestRunner(
        os.environ.get("AGENTLESS_TEST_IMAGE", "python:3.11-slim"),
        tmp_path / "logs",
        run_as_image_user=True,
    )
    execution = runner.run(source, PublicTestCommand(("python", "check.py")))
    stderr = Path(execution.artifact_directory, "stderr.log").read_text(errors="replace")
    assert execution.result.status is ValidationStatus.PASS, execution.message + stderr
