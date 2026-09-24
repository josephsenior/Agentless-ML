"""DeepSWE scoring, without Docker: inputs, result parsing and outcomes."""

import io
import json
import os
import subprocess
import tarfile

import pytest

from agentless_ml.schemas import Benchmark, TaskSpec
from agentless_ml.scoring import DeepSWEVerifier, ScoreStatus, ScoringError
from agentless_ml.scoring import deepswe

IMAGE = "public.ecr.aws/d3j8x8q7/swe-bench-202605:demo-v1.1"
DIGEST = "sha256:" + "a" * 64
DOCKERFILE = f"""# Verifier image
FROM {IMAGE}

COPY test.sh /tests/test.sh
COPY test.patch /tests/test.patch
COPY grader.py /tests/grader.py
COPY config.json /tests/config.json
RUN chmod +x /tests/test.sh
"""
TASK_TOML = """schema_version = "1.3"
[verifier]
network_mode = "no-network"
timeout_sec = 1800.0
[verifier.environment]
cpus = 2
memory_mb = 8192
"""


def git(cwd, *args):
    subprocess.run(
        ["git", "-c", "core.autocrlf=false", "-c", "user.name=t", "-c", "user.email=t@t",
         *args],
        cwd=cwd, check=True, capture_output=True,
    )


def make_corpus(tmp_path, dockerfile=DOCKERFILE, task_toml=TASK_TOML):
    root = tmp_path / "deep-swe"
    task = root / "tasks" / "demo"
    (task / "tests").mkdir(parents=True)
    (task / "solution").mkdir()
    (task / "tests" / "Dockerfile").write_bytes(dockerfile.encode())
    (task / "tests" / "test.sh").write_bytes(b"#!/bin/bash\necho run\n")
    (task / "tests" / "test.patch").write_bytes(b"diff --git a/t b/t\n")
    (task / "tests" / "grader.py").write_bytes(b"print('grade')\n")
    (task / "tests" / "config.json").write_bytes(b'{"f2p_node_ids": []}\n')
    (task / "solution" / "solution.patch").write_bytes(b"diff --git a/s b/s\n")
    (task / "task.toml").write_bytes(task_toml.encode())
    git(root, "init", "-q")
    git(root, "add", ".")
    git(root, "commit", "-q", "-m", "corpus")
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True
    ).stdout.strip()
    return root, revision


def task():
    return TaskSpec(
        benchmark=Benchmark.DEEPSWE,
        benchmark_revision="r",
        instance_id="demo",
        language="go",
        repository_url="https://github.com/o/r.git",
        base_commit="b" * 40,
        problem_statement="p",
        container_image=IMAGE,
        container_digest=DIGEST,
    )


def test_verifier_files_are_the_committed_bytes_not_the_checkout(tmp_path):
    # A Windows clone with core.autocrlf=true checks these out with CRLF, and
    # bash and git apply both fail on that; the committed bytes have none.
    root, revision = make_corpus(tmp_path)
    (root / "tasks/demo/tests/test.sh").write_bytes(b"#!/bin/bash\r\necho run\r\n")
    files = DeepSWEVerifier(root, revision).verifier_files(task())
    assert files["test.sh"] == b"#!/bin/bash\necho run\n"
    assert set(files) == {"test.sh", "test.patch", "grader.py", "config.json"}


@pytest.mark.parametrize(
    "dockerfile,message",
    [
        (DOCKERFILE + "RUN pip install extra\n", "unreviewed shape"),
        (DOCKERFILE.replace(IMAGE, "other/image:tag"), "not the task's image"),
    ],
)
def test_an_unreviewed_verifier_dockerfile_is_refused(tmp_path, dockerfile, message):
    root, revision = make_corpus(tmp_path, dockerfile=dockerfile)
    with pytest.raises(ScoringError, match=message):
        DeepSWEVerifier(root, revision).verifier_files(task())


def test_verifier_limits_come_from_the_task_and_forbid_network(tmp_path):
    root, revision = make_corpus(tmp_path)
    assert DeepSWEVerifier(root, revision).verifier_limits(task()) == (2.0, 8192, 1800.0)
    root, revision = make_corpus(
        tmp_path / "net", task_toml=TASK_TOML.replace("no-network", "public")
    )
    with pytest.raises(ScoringError, match="network"):
        DeepSWEVerifier(root, revision).verifier_limits(task())


def test_inputs_place_files_and_patch_where_deepswe_does():
    files = {"test.sh": b"sh", "test.patch": b"tp", "grader.py": b"g", "config.json": b"{}"}
    with tarfile.open(fileobj=io.BytesIO(deepswe._inputs(files, b"PATCH"))) as archive:
        members = {m.name: m for m in archive}
        assert archive.extractfile("logs/artifacts/model.patch").read() == b"PATCH"
        assert archive.extractfile("tests/test.patch").read() == b"tp"
    assert members["tests/test.sh"].mode == 0o755
    assert members["tests/grader.py"].mode == 0o644


def results_tar(entries):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        for name, content, kind in entries:
            info = tarfile.TarInfo(name)
            if kind == "link":
                info.type, info.linkname = tarfile.SYMTYPE, "/etc/passwd"
                archive.addfile(info)
            else:
                info.size = len(content)
                archive.addfile(info, io.BytesIO(content))
    return buffer.getvalue()


def test_result_files_from_the_container_are_filtered():
    # The container ran the patch under test; its output is untrusted.
    found = deepswe._results(
        results_tar(
            [
                ("verifier/reward.json", b'{"reward": 1}', "file"),
                ("verifier/ctrf.json", b"x", "link"),
                ("verifier/reports/reward.json", b'{"reward": 0}', "file"),
                ("verifier/other.txt", b"x", "file"),
            ]
        )
    )
    assert found == {"reward.json": b'{"reward": 1}'}


@pytest.mark.parametrize(
    "reward,status",
    [
        ({"reward": 1, "f2p_passed": 55, "f2p_total": 55}, ScoreStatus.RESOLVED),
        ({"reward": 0, "f2p_passed": 0, "f2p_total": 55}, ScoreStatus.UNRESOLVED),
        ({"reward": 0, "apply_failed": 1}, ScoreStatus.PATCH_NOT_APPLIED),
        ({"reward": True}, ScoreStatus.VERIFIER_ERROR),
        ({"reward": 2}, ScoreStatus.VERIFIER_ERROR),
    ],
)
def test_reward_json_decides_the_outcome(reward, status):
    assert deepswe._status({"reward.json": json.dumps(reward).encode()}, 0)[0] is status


def test_a_crashed_verifier_is_an_error_not_a_zero():
    # test.sh's trap writes reward.txt = -1 when grading never produced reward.json.
    status, message = deepswe._status({"reward.txt": b"-1\n"}, 6)
    assert status is ScoreStatus.VERIFIER_ERROR
    assert "reward.txt=-1" in message


class FakeDocker:
    def __init__(self, reward=None, image_id=DIGEST, timeout=False):
        self.reward, self.image_id, self.timeout = reward, image_id, timeout
        self.calls = []

    def __call__(self, *args, timeout, data=None, check=True):
        self.calls.append(args)
        if args[:2] == ("image", "inspect"):
            out = json.dumps([{"Id": self.image_id}]).encode()
        elif args[0] == "start":
            if self.timeout:
                raise subprocess.TimeoutExpired("docker start", timeout)
            out = b"[verifier] done\n"
        elif args[0] == "cp" and args[-1] == "-":
            entries = [("verifier/reward.json", json.dumps(self.reward).encode(), "file")]
            out = results_tar(entries if self.reward is not None else [])
        else:
            out = b""
        return subprocess.CompletedProcess(args, 0, out, b"")


def run_score(tmp_path, monkeypatch, fake, patch="diff"):
    root, revision = make_corpus(tmp_path)
    monkeypatch.setattr(deepswe, "_docker", fake)
    return DeepSWEVerifier(root, revision).score(task(), patch, tmp_path / "scores")


def test_score_runs_the_verifier_isolated_and_cleans_up(tmp_path, monkeypatch):
    fake = FakeDocker({"reward": 1, "f2p_passed": 3, "f2p_total": 3,
                       "p2p_passed": 5, "p2p_total": 5})
    score = run_score(tmp_path, monkeypatch, fake)
    assert score.resolved and (score.f2p_passed, score.p2p_total) == (3, 5)
    create = next(call for call in fake.calls if call[0] == "create")
    assert "--network=none" in create and "--memory=8192m" in create
    assert "--pull=never" in create and DIGEST in create
    assert any(call[0] == "rm" for call in fake.calls)
    record = json.loads(open(os.path.join(score.artifact_directory, "score.json")).read())
    assert record["status"] == "resolved" and record["verifier_exit_code"] == 0


def test_score_refuses_an_image_other_than_the_pinned_one(tmp_path, monkeypatch):
    with pytest.raises(ScoringError, match="not the pinned"):
        run_score(tmp_path, monkeypatch, FakeDocker(image_id="sha256:" + "b" * 64))


def test_a_verifier_timeout_is_its_own_outcome_and_still_cleans_up(tmp_path, monkeypatch):
    fake = FakeDocker(timeout=True)
    score = run_score(tmp_path, monkeypatch, fake)
    assert score.status is ScoreStatus.TIMEOUT and score.reward is None
    assert [call[0] for call in fake.calls][-2:] == ["kill", "rm"]


def test_missing_reward_is_a_verifier_error(tmp_path, monkeypatch):
    score = run_score(tmp_path, monkeypatch, FakeDocker(reward=None))
    assert score.status is ScoreStatus.VERIFIER_ERROR


def test_the_reference_solution_is_available_only_by_its_explicit_name(tmp_path):
    root, revision = make_corpus(tmp_path)
    verifier = DeepSWEVerifier(root, revision)
    assert verifier.reference_patch_for_harness_validation(task()) == "diff --git a/s b/s\n"
    assert not [name for name in dir(verifier) if "solution" in name and "harness" not in name]
