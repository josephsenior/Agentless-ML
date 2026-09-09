"""Recorded JS/TS repairs with an optional Node check on authored fixtures only."""

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


def _files(language):
    typed = language == "typescript"
    main = "math.ts" if typed else "math.mjs"
    helper = "scale.js" if typed else "scale.mjs"
    signature = "(a: number, b: number): number" if typed else "(a, b)"
    return (
        main,
        helper,
        {
            "package.json": '{"type":"module"}\n',
            main: (
                f'import {{ scale }} from "./{helper}";\n'
                f"export const add = {signature} => (a - b) * scale;\n"
            ),
            helper: "export const scale = 2;\n",
            "check.mjs": (
                'import assert from "node:assert/strict";\n'
                f'import {{ add }} from "./{main}";\n'
                "assert.equal(add(2, 3), 5);\n"
            ),
        },
    )


def _git(path, *args):
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("GIT_")}
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
    return subprocess.run(
        [
            "git",
            "-c",
            "user.name=JS Fixture",
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
    image_reference = "node:controlled-fixture"
    image_id = "sha256:controlled-fixture"

    def __init__(self, main, native=False):
        self.main = main
        self.native = native

    def run(self, source, command, *, artifact_root=None):
        destination = Path(artifact_root) / "controlled-execution"
        destination.mkdir(parents=True)
        if self.native:
            env = {
                k: v
                for k, v in os.environ.items()
                if not k.upper().startswith(("NODE_", "NPM_"))
            }
            execution = subprocess.run(
                command.argv,
                cwd=source,
                env=env,
                capture_output=True,
                check=False,
                text=True,
                timeout=30,
            )
            (destination / "stdout.txt").write_text(execution.stdout, encoding="utf-8")
            (destination / "stderr.txt").write_text(execution.stderr, encoding="utf-8")
            if execution.returncode:
                assert "AssertionError" in execution.stderr, execution.stderr
            passed = execution.returncode == 0
        else:
            passed = "(a + b)" in (Path(source) / self.main).read_text()
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


def _run(tmp_path, language, native=False):
    main, helper, files = _files(language)
    source = tmp_path / "source"
    source.mkdir()
    for name, content in files.items():
        (source / name).write_bytes(content.encode())
    _git(source, "init")
    _git(source, "add", ".")
    _git(source, "commit", "-m", "controlled JS/TS fixture")
    runner = FixtureRunner(main, native)
    task = TaskSpec(
        benchmark=Benchmark.CONTROLLED_FIXTURE,
        benchmark_revision="js-ts-fixture-v1",
        instance_id="controlled__" + language,
        language=language,
        repository_url="https://example.invalid/fixture",
        base_commit=_git(source, "rev-parse", "HEAD"),
        problem_statement="add should return the sum of its arguments, with scale equal to one.",
        container_image=runner.image_reference,
        container_digest=runner.image_id,
    )

    def repair(operator):
        original = files[main].splitlines()[1]
        changed = original.replace("a - b", "a " + operator + " b")
        return (
            f"```{language}\n### {main}\n<<<<<<< SEARCH\n{original}\n=======\n"
            f"{changed}\n>>>>>>> REPLACE\n### {helper}\n<<<<<<< SEARCH\n"
            "export const scale = 2;\n=======\nexport const scale = 1;\n>>>>>>> REPLACE\n```"
        )

    command = (
        ("node", "--experimental-strip-types", "check.mjs")
        if language == "typescript"
        else ("node", "check.mjs")
    )
    result = FixedWorkflowController(
        task=task,
        source_repository=source,
        workspace_root=tmp_path / "workspaces",
        artifact_root=tmp_path / "runs",
        runner=runner,
        public_commands=(PublicTestCommand(command),),
        implementation_revision="fixture",
        harness_revision="controlled-node-v1",
        model_name="recorded",
    ).run(
        RecordedStageResponses(
            file_localization=f"```\n{main}\n{helper}\n```",
            symbol_localization=f"```\n{main}\nfunction: add\n{helper}\nconstant: scale\n```",
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
        main in result.prediction.model_patch
        and helper in result.prediction.model_patch
    )
    assert result.run.model_calls == 0
    assert result.selected_files == (main, helper)
    for name, content in files.items():
        assert (source / name).read_bytes() == content.encode()
    assert not list((tmp_path / "workspaces").iterdir())
    artifacts = Path(result.artifact_directory)
    assert "flask" not in (artifacts / "prompts/repair.txt").read_text()
    assert (
        "```javascript" in (artifacts / "prompts/symbol-localization.txt").read_text()
    )
    assert json.loads((artifacts / "task.json").read_text())["language"] == language


@pytest.mark.parametrize("language", ["javascript", "typescript"])
def test_recorded_javascript_typescript_workflow(tmp_path, language):
    _run(tmp_path, language)


@pytest.mark.skipif(
    os.environ.get("AGENTLESS_JS_TESTS") != "1" or shutil.which("node") is None,
    reason="opt-in Node execution of authored fixtures (Node 22.6+ for TS stripping)",
)
@pytest.mark.parametrize("language", ["javascript", "typescript"])
def test_recorded_workflow_with_node(tmp_path, language):
    _run(tmp_path, language, native=True)
