"""Controlled Go workflow; native execution is opt-in and uses only this fixture."""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from agentless_ml.schemas import Benchmark, TaskSpec, ValidationResult, ValidationStatus
from agentless_ml.validation import PublicTestCommand
from agentless_ml.validation import TestExecution as ExecutionRecord
from agentless_ml.workflow import FixedWorkflowController, RecordedStageResponses

FILES = {
    "go.mod": "module example.invalid/counter\n\ngo 1.20\n",
    "counter.go": "package counter\n\ntype Counter struct { Value int }\nconst Scale = 2\n",
    "methods.go": (
        "package counter\n\nfunc (c *Counter) Add(v int) int {\n"
        "    c.Value -= v\n    return c.Value * Scale\n}\n"
    ),
    "counter_test.go": (
        'package counter\nimport "testing"\n'
        "func TestAdd(t *testing.T) {\n"
        "    c := Counter{Value: 2}\n"
        '    if got := c.Add(3); got != 5 { t.Fatalf("got %d, want 5", got) }\n}\n'
    ),
}


def _git(path, *args):
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("GIT_")}
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
    return subprocess.run(
        [
            "git",
            "-c",
            "user.name=Go Fixture",
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
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _responses():
    def repair(operator):
        return (
            "```go\n### methods.go\n<<<<<<< SEARCH\n    c.Value -= v\n=======\n"
            f"    c.Value {operator}= v\n>>>>>>> REPLACE\n"
            "### counter.go\n<<<<<<< SEARCH\nconst Scale = 2\n=======\n"
            "const Scale = 1\n>>>>>>> REPLACE\n```"
        )

    return RecordedStageResponses(
        file_localization="```\nmethods.go\ncounter.go\n```",
        symbol_localization=(
            "```\nmethods.go\nmethod: Counter.Add\ncounter.go\nconstant: Scale\n```"
        ),
        repairs=("malformed", repair("*"), repair("+")),
    )


class FixtureRunner:
    image_reference = "go:controlled-fixture"
    image_id = "sha256:controlled-fixture"

    def __init__(self, cache=None):
        self.cache = cache

    def run(self, source, command, *, artifact_root=None):
        destination = Path(artifact_root) / "controlled-execution"
        destination.mkdir(parents=True)
        if self.cache is None:
            passed = "c.Value += v" in (Path(source) / "methods.go").read_text()
        else:
            # No downloaded dependencies, workspace inheritance, or toolchain download.
            env = {
                k: v for k, v in os.environ.items() if not k.upper().startswith("GO")
            }
            env.update(
                GOENV="off",
                GOWORK="off",
                GOPROXY="off",
                GOSUMDB="off",
                GOTOOLCHAIN="local",
                CGO_ENABLED="0",
                GOCACHE=str(self.cache),
            )
            execution = subprocess.run(
                command.argv,
                cwd=source,
                env=env,
                capture_output=True,
                text=True,
                timeout=120,
            )
            (destination / "stdout.txt").write_text(execution.stdout)
            (destination / "stderr.txt").write_text(execution.stderr)
            assert execution.returncode in (0, 1), execution.stderr
            if execution.returncode:
                assert "got " in execution.stdout, execution.stdout + execution.stderr
            passed = execution.returncode == 0
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


def _run(tmp_path, runner):
    source = tmp_path / "source"
    source.mkdir()
    for name, content in FILES.items():
        (source / name).write_bytes(content.encode())
    _git(source, "init")
    _git(source, "add", ".")
    _git(source, "commit", "-m", "controlled Go fixture")
    task = TaskSpec(
        benchmark=Benchmark.CONTROLLED_FIXTURE,
        benchmark_revision="go-fixture-v1",
        instance_id="controlled__go-counter",
        language="go",
        repository_url="https://example.invalid/counter",
        base_commit=_git(source, "rev-parse", "HEAD"),
        problem_statement="Add should add v to Value and return the new value.",
        container_image=runner.image_reference,
        container_digest=runner.image_id,
    )
    result = FixedWorkflowController(
        task=task,
        source_repository=source,
        workspace_root=tmp_path / "workspaces",
        artifact_root=tmp_path / "runs",
        runner=runner,
        public_commands=(PublicTestCommand(("go", "test", "./...")),),
        implementation_revision="fixture",
        harness_revision="controlled-go-v1",
        model_name="recorded",
    ).run(_responses())
    assert result.prediction.selected_candidate_id == "repair-2"
    assert [a.status for a in result.attempts] == [
        "repair_error",
        "validated",
        "validated",
    ]
    assert [
        a.candidate.validation[0].status for a in result.attempts if a.candidate
    ] == [
        ValidationStatus.FAIL,
        ValidationStatus.PASS,
    ]
    assert "counter.go" in result.prediction.model_patch
    assert "methods.go" in result.prediction.model_patch
    assert result.run.model_calls == 0
    for name, content in FILES.items():
        assert (source / name).read_bytes() == content.encode()
    assert not list((tmp_path / "workspaces").iterdir())
    artifacts = Path(result.artifact_directory)
    assert "```go" in (artifacts / "prompts/repair.txt").read_text()
    assert (
        "counter_test.go"
        not in (artifacts / "prompts/file-localization.txt").read_text()
    )
    assert json.loads((artifacts / "task.json").read_text())["language"] == "go"


def test_recorded_go_workflow(tmp_path):
    _run(tmp_path, FixtureRunner())


@pytest.mark.skipif(
    os.environ.get("AGENTLESS_GO_TESTS") != "1" or shutil.which("go") is None,
    reason="opt-in Go compiler check on the controlled fixture",
)
def test_recorded_go_workflow_with_compiler(tmp_path):
    _run(tmp_path, FixtureRunner(tmp_path / "go-cache"))
