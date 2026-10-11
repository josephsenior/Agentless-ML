"""Run an authored Rust controller diagnostic, not a benchmark solve attempt."""

from __future__ import annotations

import argparse
import base64
from dataclasses import asdict, replace
import hashlib
import json
import os
from pathlib import Path
import subprocess

from agentless_ml.schemas import Benchmark, TaskSpec, ValidationKind, ValidationStatus
from agentless_ml.validation import DockerTestRunner, RegressionTest, rust_reproduction_command
from agentless_ml.validation.reproduction import ReproductionSpec
from agentless_ml.workflow import FixedWorkflowController, RecordedStageResponses

ROOT = Path(__file__).resolve().parents[1]
SOURCE = "pub fn add(a: i32, b: i32) -> i32 { a - b }\n"
FILES = {
    "Cargo.toml": '[package]\nname = "reproduction-fixture"\nversion = "0.1.0"\nedition = "2021"\n',
    "Cargo.lock": 'version = 4\n\n[[package]]\nname = "reproduction-fixture"\nversion = "0.1.0"\n',
    "src/lib.rs": SOURCE,
    "tests/public.rs": '#[test]\nfn zero() { assert_eq!(reproduction_fixture::add(0, 0), 0); }\n',
}


def git(directory: Path, *args: str) -> str:
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("GIT_")}
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
    return subprocess.run(
        ["git", "-c", "safe.directory=" + str(directory),
         "-c", "user.name=Rust Fixture", "-c", "user.email=fixture@example.invalid",
         "-c", "core.autocrlf=false", "-c", "core.hooksPath=" + os.devnull, *args],
        cwd=directory, env=env, check=True, capture_output=True, text=True,
    ).stdout.strip()


def responses() -> RecordedStageResponses:
    def repair(operator: str) -> str:
        return (
            "```rust\n### src/lib.rs\n<<<<<<< SEARCH\n" + SOURCE
            + "=======\n" + SOURCE.replace("a - b", f"a {operator} b")
            + ">>>>>>> REPLACE\n```"
        )

    return RecordedStageResponses(
        file_localization="```\nsrc/lib.rs\n```",
        symbol_localization="```\nsrc/lib.rs\nfunction: add\n```",
        edit_localization="```\nsrc/lib.rs\nline: 1\n```",
        repairs=("malformed recorded response", repair("*"), repair("+")),
        regression_exclusions="",
        reproduction_test=(
            "```rust\n#[test]\nfn issue() { assert_eq!(reproduction_fixture::add(2, 3), 5); }\n```"
        ),
        source="manually authored controlled Rust fixture; no benchmark answer material",
    )


def run_slice(output: Path) -> dict:
    # Refuse to reuse a source checkout or overwrite an earlier diagnostic.
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    source = output / "source"
    source.mkdir()
    for name, content in FILES.items():
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content.encode())
    git(source, "init")
    git(source, "add", ".")
    git(source, "commit", "-m", "authored Rust controller fixture")
    pin = json.loads((ROOT / "experiments/deepswe/corpus_pin.json").read_bytes())
    image = pin["container_digests"]["wasmi-trap-coredumps"]
    runner = DockerTestRunner(
        image, output / "executions", memory_mb=4096, cpus=1,
        tmpfs_mb=4096, pids_limit=2048, run_as_image_user=True,
    )
    task = TaskSpec(
        benchmark=Benchmark.CONTROLLED_FIXTURE,
        benchmark_revision="authored-rust-controller-v1",
        instance_id="controlled__rust_reproduction",
        language="rust", repository_url="https://example.invalid/authored-rust-fixture",
        base_commit=git(source, "rev-parse", "HEAD"),
        problem_statement="add should return the sum of both inputs; add(2, 3) should equal 5.",
        container_image=image, container_digest=image, memory_megabytes=4096,
    )
    regression = replace(
        rust_reproduction_command("tests/public.rs", test_name="zero", timeout_seconds=120),
        kind=ValidationKind.REGRESSION,
    )
    revision = git(ROOT, "rev-parse", "HEAD")
    if git(ROOT, "status", "--porcelain", "--untracked-files=all"):
        revision += "+dirty"
    result = FixedWorkflowController(
        task=task, source_repository=source, workspace_root=output / "workspaces",
        artifact_root=output / "runs", runner=runner, public_commands=(),
        regression_tests=(RegressionTest("existing-zero", regression),),
        reproduction_spec=ReproductionSpec(
            "tests/reproduce.rs",
            rust_reproduction_command("tests/reproduce.rs", test_name="issue", timeout_seconds=120),
        ),
        implementation_revision=revision, harness_revision="authored-rust-controller-v1",
        model_name="recorded/manual-rust-controller",
    ).run(responses())
    directory = Path(result.artifact_directory)
    baseline = json.loads((directory / "reproduction-baseline.json").read_bytes())
    assert baseline["checked_result"]["status"] == "fail"
    assert baseline["checked_result"]["test_cases"][0]["status"] == "failed"
    regressions = json.loads((directory / "regression-baseline.json").read_bytes())
    assert len(regressions) == 1 and regressions[0]["result"]["status"] == "pass"
    reports = list(directory.rglob("report.json"))
    assert len(reports) == 6  # two baselines, then regression + reproduction per candidate
    for report in reports:
        document = json.loads(report.read_bytes())
        assert b"<testcase" in base64.b64decode(document["rust_junit_base64"], validate=True)
    assert [a.status for a in result.attempts] == ["repair_error", "validated", "validated"]
    expected = ((ValidationStatus.PASS, ValidationStatus.FAIL),
                (ValidationStatus.PASS, ValidationStatus.PASS))
    candidates = [a.candidate for a in result.attempts if a.candidate]
    assert [tuple(v.status for v in c.validation) for c in candidates] == list(expected)
    assert result.prediction.selected_candidate_id == "repair-2"
    assert result.run.model_calls == 0
    prediction = json.loads((directory / "prediction.json").read_bytes())
    assert prediction == asdict(result.prediction)
    patch = prediction["model_patch"]
    assert "a + b" in patch and "tests/" not in patch and "Cargo.toml" not in patch
    assert hashlib.sha256(patch.encode()).hexdigest() == result.run.final_patch_sha256
    assert not list((output / "workspaces").iterdir())
    assert not git(source, "status", "--porcelain", "--untracked-files=all")
    for name, content in FILES.items():
        assert (source / name).read_bytes() == content.encode()
    assert not (source / "tests/reproduce.rs").exists()
    summary = {
        "scope": "authored controlled fixture, not a DeepSWE benchmark result",
        "artifact_directory": str(directory),
        "prediction_path": str(directory / "prediction.json"),
        "selected_candidate_id": prediction["selected_candidate_id"],
        "attempt_statuses": [a.status for a in result.attempts],
        "candidate_outcomes": [[v.status.value for v in c.validation] for c in candidates],
        "reproduction_baseline": "fail", "regression_baseline": "pass",
        "retained_raw_junit_reports": len(reports),
        "model_calls": result.run.model_calls,
        "container_digest": runner.image_id,
        "implementation_revision": revision,
        "wall_time_seconds": result.run.wall_time_seconds,
        "final_patch_sha256": result.run.final_patch_sha256,
        "source_unchanged": True, "candidate_workspaces_cleaned": True,
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="new diagnostic directory")
    print(json.dumps(run_slice(parser.parse_args().output), indent=2))
