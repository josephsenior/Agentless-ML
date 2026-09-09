"""Controlled recorded Rust repair, optionally compiled with the installed rustc."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from agentless_ml.schemas import Benchmark, TaskSpec, ValidationResult, ValidationStatus
from agentless_ml.validation import PublicTestCommand
from agentless_ml.validation import TestExecution as ExecutionRecord
from agentless_ml.workflow import FixedWorkflowController, RecordedStageResponses

SOURCE = """mod scale;
pub struct Counter;
impl Counter {
    pub fn add(a: i32, b: i32) -> i32 { (a - b) * scale::SCALE }
}
#[test]
fn adds() { assert_eq!(Counter::add(2, 3), 5); }
"""


def _git(path, *args):
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("GIT_")}
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
    return subprocess.run(
        [
            "git",
            "-c",
            "user.name=Rust Fixture",
            "-c",
            "user.email=test@example.invalid",
            "-c",
            "core.autocrlf=false",
            "-c",
            "core.hooksPath=" + os.devnull,
            *args,
        ],
        cwd=path,
        env=env,
        capture_output=True,
        check=True,
        text=True,
    ).stdout.strip()


class FixtureRunner:
    image_reference = "rust:controlled-fixture"
    image_id = "sha256:controlled-fixture"

    def __init__(self, native):
        self.native = native

    def run(self, source, command, *, artifact_root=None):
        destination = Path(artifact_root) / "controlled-execution"
        destination.mkdir(parents=True)
        if self.native:
            binary = destination.resolve() / (
                "tests.exe" if os.name == "nt" else "tests"
            )
            compiled = subprocess.run(
                ["rustc", "--test", "lib.rs", "-o", str(binary)],
                cwd=source,
                capture_output=True,
                text=True,
                timeout=60,
            )
            assert compiled.returncode == 0, compiled.stderr
            execution = subprocess.run(
                [str(binary)], capture_output=True, text=True, timeout=30
            )
            (destination / "stdout.txt").write_text(execution.stdout, encoding="utf-8")
            (destination / "stderr.txt").write_text(execution.stderr, encoding="utf-8")
            if execution.returncode:
                assert "assertion" in execution.stdout, execution.stdout
            passed = execution.returncode == 0
        else:
            passed = (
                "a + b" in (Path(source) / "lib.rs").read_text()
                and "= 1;" in (Path(source) / "scale.rs").read_text()
            )
        return ExecutionRecord(
            ValidationResult(
                status=ValidationStatus.PASS if passed else ValidationStatus.FAIL,
                command=command.argv,
                duration_seconds=0,
                exit_code=0 if passed else 1,
                kind=command.kind,
            ),
            self.image_id,
            "controlled-fixture",
            str(destination),
        )


def _run(tmp_path, native=False):
    source = tmp_path / "source"
    source.mkdir()
    files = {"lib.rs": SOURCE, "scale.rs": "pub const SCALE: i32 = 2;\n"}
    for name, content in files.items():
        (source / name).write_bytes(content.encode())
    _git(source, "init")
    _git(source, "add", ".")
    _git(source, "commit", "-m", "controlled Rust fixture")
    runner = FixtureRunner(native)
    task = TaskSpec(
        benchmark=Benchmark.CONTROLLED_FIXTURE,
        benchmark_revision="rust-fixture-v1",
        instance_id="controlled__rust",
        language="rust",
        repository_url="https://example.invalid/fixture",
        base_commit=_git(source, "rev-parse", "HEAD"),
        problem_statement="add should sum both inputs, with SCALE equal to one.",
        container_image=runner.image_reference,
        container_digest=runner.image_id,
    )

    def repair(operator):
        original = SOURCE.splitlines()[3]
        changed = original.replace("a - b", "a " + operator + " b")
        return (
            f"```rust\n### lib.rs\n<<<<<<< SEARCH\n{original}\n=======\n{changed}\n"
            ">>>>>>> REPLACE\n### scale.rs\n<<<<<<< SEARCH\npub const SCALE: i32 = 2;\n"
            "=======\npub const SCALE: i32 = 1;\n>>>>>>> REPLACE\n```"
        )

    result = FixedWorkflowController(
        task=task,
        source_repository=source,
        workspace_root=tmp_path / "workspaces",
        artifact_root=tmp_path / "runs",
        runner=runner,
        public_commands=(PublicTestCommand(("rustc", "--test", "lib.rs")),),
        implementation_revision="fixture",
        harness_revision="controlled-rust-v1",
        model_name="recorded",
    ).run(
        RecordedStageResponses(
            file_localization="```\nlib.rs\nscale.rs\n```",
            symbol_localization="```\nlib.rs\nmethod: Counter::add\nscale.rs\nconstant: SCALE\n```",
            repairs=("malformed", repair("*"), repair("+")),
        )
    )
    assert result.prediction.selected_candidate_id == "repair-2"
    assert [a.status for a in result.attempts] == [
        "repair_error",
        "validated",
        "validated",
    ]
    assert [
        a.candidate.validation[0].status for a in result.attempts if a.candidate
    ] == [ValidationStatus.FAIL, ValidationStatus.PASS]
    assert (
        "lib.rs" in result.prediction.model_patch
        and "scale.rs" in result.prediction.model_patch
    )
    assert result.run.model_calls == 0
    for name, content in files.items():
        assert (source / name).read_bytes() == content.encode()
    assert not list((tmp_path / "workspaces").iterdir())


def test_recorded_rust_workflow(tmp_path):
    _run(tmp_path)


@pytest.mark.skipif(
    os.environ.get("AGENTLESS_RUST_TESTS") != "1" or shutil.which("rustc") is None,
    reason="opt-in rustc execution of authored fixture",
)
def test_recorded_rust_workflow_with_compiler(tmp_path):
    _run(tmp_path, native=True)
