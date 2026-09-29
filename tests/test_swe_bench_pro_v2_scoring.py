"""V2 final-only scorer checks that do not need Docker or hidden test files."""

import io
import json
import subprocess
import tarfile
from dataclasses import replace
from pathlib import Path

import pytest

from agentless_ml.schemas import Benchmark, TaskSpec
from agentless_ml.scoring import ScoreStatus, ScoringError, SWEbenchProV2Verifier
from agentless_ml.scoring import swe_bench_pro_v2 as scoring

INSTANCE = "instance_demo__repo-abc-vdef"
IMAGE = f"ghcr.io/scaleapi/swe-bench_pro-v2:{INSTANCE}"
IMAGE_ID = "sha256:" + "a" * 64
BASE = "b" * 40


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-c", "user.name=test", "-c", "user.email=test@example.com", *args],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _fixture(tmp_path: Path) -> tuple[Path, str, TaskSpec]:
    root = tmp_path / "benchmark"
    directory = root / "v2" / "tasks" / INSTANCE
    (directory / "tests").mkdir(parents=True)
    (directory / "solution").mkdir()
    (directory / "environment").mkdir()
    (directory / "task.toml").write_text(
        '[verifier]\nnetwork_mode = "public"\ntimeout_sec = 300.0\n'
        f'[environment]\ndocker_image = "{IMAGE}"\ncpus = 1\nmemory_mb = 4096\n',
        encoding="utf-8",
    )
    (directory / "environment" / "Dockerfile").write_text(
        f"FROM {IMAGE}\n", encoding="utf-8"
    )
    for name in scoring.VERIFIER_FILES:
        (directory / "tests" / name).write_bytes(b"verifier-only\n")
    (directory / "solution" / "gold_patch.diff").write_text(
        "reference-only\n", encoding="utf-8"
    )
    _git(root, "init", "-q")
    _git(root, "add", ".")
    _git(root, "commit", "-q", "-m", "fixture")
    revision = _git(root, "rev-parse", "HEAD")
    task = TaskSpec(
        benchmark=Benchmark.SWE_BENCH_PRO,
        benchmark_revision=revision,
        instance_id=INSTANCE,
        language="python",
        repository_url="https://github.com/demo/repo.git",
        base_commit=BASE,
        problem_statement="Fix issue",
        container_image=IMAGE,
        container_digest=IMAGE_ID,
    )
    return root, revision, task


def _tar_result(reward: bytes) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        info = tarfile.TarInfo("verifier/reward.txt")
        info.size = len(reward)
        archive.addfile(info, io.BytesIO(reward))
    return buffer.getvalue()


class FakeDocker:
    def __init__(self, reward: bytes = b"1\n") -> None:
        self.reward = reward
        self.calls: list[tuple[str, ...]] = []

    def __call__(self, *args: str, timeout: float, data=None, check=True):
        self.calls.append(args)
        if args[:2] == ("image", "inspect"):
            output = json.dumps([{"Id": IMAGE_ID}]).encode()
        elif args[:1] == ("cp",) and args[-1] == "-":
            output = _tar_result(self.reward)
        else:
            output = b""
        exit_code = 1 if args[:1] == ("start",) and self.reward == b"0\n" else 0
        return subprocess.CompletedProcess(args, exit_code, output, b"")


@pytest.mark.parametrize(
    ("reward", "status"),
    [(b"1\n", ScoreStatus.RESOLVED), (b"0\n", ScoreStatus.UNRESOLVED)],
)
def test_final_score_uses_fresh_image_and_verifier_reward(
    tmp_path: Path, monkeypatch, reward: bytes, status: ScoreStatus
) -> None:
    root, revision, task = _fixture(tmp_path)
    fake = FakeDocker(reward)
    monkeypatch.setattr(scoring, "_docker", fake)
    score = SWEbenchProV2Verifier(root, revision).score(
        task, "diff", tmp_path / "scores"
    )
    assert score.status is status
    create = next(call for call in fake.calls if call[0] == "create")
    assert "--network=bridge" in create
    assert IMAGE_ID in create
    assert "--3way" in create[-1]
    assert any(call[0] == "rm" for call in fake.calls)
    assert not (Path(score.artifact_directory) / "model.patch").exists()


def test_verifier_blobs_are_from_pinned_commit(tmp_path: Path) -> None:
    root, revision, task = _fixture(tmp_path)
    patch = root / "v2" / "tasks" / INSTANCE / "solution" / "gold_patch.diff"
    patch.write_text("changed checkout\n", encoding="utf-8")
    verifier = SWEbenchProV2Verifier(root, revision)
    assert verifier.reference_patch_for_harness_validation(task) == "reference-only\n"


def test_unreviewed_environment_is_rejected(tmp_path: Path) -> None:
    root, _, task = _fixture(tmp_path)
    dockerfile = root / "v2" / "tasks" / INSTANCE / "environment" / "Dockerfile"
    dockerfile.write_text(f"FROM {IMAGE}\nRUN echo something\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-q", "-m", "changed shape")
    revision = _git(root, "rev-parse", "HEAD")
    with pytest.raises(ScoringError, match="unreviewed shape"):
        SWEbenchProV2Verifier(root, revision)._settings(
            replace(task, benchmark_revision=revision)
        )
