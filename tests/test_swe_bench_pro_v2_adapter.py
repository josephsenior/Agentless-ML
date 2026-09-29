import hashlib
from pathlib import Path

import pytest

from agentless_ml.adapters.benchmarks import (
    load_swe_bench_pro_task,
    load_swe_bench_pro_v2_task,
)

INSTANCE = "instance_qutebrowser__qutebrowser-example-v123"
REVISION = "a" * 40
DIGEST = "sha256:" + "b" * 64


def _fixture(directory: Path) -> tuple[object, dict[str, str]]:
    directory.mkdir()
    (directory / "task.toml").write_text(
        'schema_version = "1.4"\n'
        f'[task]\nname = "swebench-pro/{INSTANCE}"\n'
        '[agent]\nnetwork_mode = "no-network"\ntimeout_sec = 3000.0\n'
        '[environment]\nnetwork_mode = "public"\nos = "linux"\n'
        f'docker_image = "ghcr.io/scaleapi/swe-bench_pro-v2:{INSTANCE}"\n'
        "memory_mb = 4096\n",
        encoding="utf-8",
    )
    (directory / "instruction.md").write_text(
        "Fix the public issue.\n", encoding="utf-8"
    )
    # Even a malformed verifier file must not be opened by the adapter.
    (directory / "tests").mkdir()
    (directory / "tests" / "test.sh").write_bytes(b"\xff")
    pins = {
        name: hashlib.sha256((directory / name).read_bytes()).hexdigest()
        for name in ("task.toml", "instruction.md")
    }
    v1 = load_swe_bench_pro_task(
        {
            "repo": "qutebrowser/qutebrowser",
            "instance_id": INSTANCE,
            "base_commit": "c" * 40,
            "problem_statement": "Old V1 wording",
            "requirements": None,
            "interface": None,
            "repo_language": "python",
            "dockerhub_tag": "qutebrowser.example",
        },
        dataset_revision="d" * 40,
    )
    return v1, pins


def test_v2_loads_only_pinned_visible_files(tmp_path: Path) -> None:
    v1, pins = _fixture(tmp_path / INSTANCE)
    task = load_swe_bench_pro_v2_task(
        tmp_path / INSTANCE,
        v1,
        dataset_revision=REVISION,
        visible_sha256=pins,
        container_digest=DIGEST,
    )
    assert task.problem_statement == "Fix the public issue."
    assert task.base_commit == "c" * 40
    assert task.benchmark_revision == REVISION
    assert task.container_image.endswith(INSTANCE)
    assert task.timeout_seconds == 3000


def test_v2_rejects_changed_instruction(tmp_path: Path) -> None:
    directory = tmp_path / INSTANCE
    v1, pins = _fixture(directory)
    (directory / "instruction.md").write_text("Changed", encoding="utf-8")
    with pytest.raises(ValueError, match="does not match its pin"):
        load_swe_bench_pro_v2_task(
            directory,
            v1,
            dataset_revision=REVISION,
            visible_sha256=pins,
            container_digest=DIGEST,
        )


def test_v2_rejects_online_agent(tmp_path: Path) -> None:
    directory = tmp_path / INSTANCE
    v1, pins = _fixture(directory)
    manifest = directory / "task.toml"
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace(
            'network_mode = "no-network"', 'network_mode = "public"'
        ),
        encoding="utf-8",
    )
    pins["task.toml"] = hashlib.sha256(manifest.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="offline Linux"):
        load_swe_bench_pro_v2_task(
            directory,
            v1,
            dataset_revision=REVISION,
            visible_sha256=pins,
            container_digest=DIGEST,
        )
