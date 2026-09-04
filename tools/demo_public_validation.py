"""Two prepared patches, real Docker tests, and selection. No model API calls."""

import argparse
import json
import os
import subprocess
import uuid
from dataclasses import asdict
from pathlib import Path

from agentless_ml.repair import (
    build_patch_candidate,
    build_unified_diff,
    select_candidate,
)
from agentless_ml.validation import (
    DockerTestRunner,
    PublicTestCommand,
    validate_candidate,
)
from agentless_ml.workspace import LocalGitWorkspaceProvider


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="python:3.11-slim")
    parser.add_argument(
        "--output", type=Path, default=Path("artifacts/public-validation")
    )
    args = parser.parse_args()
    root = args.output.resolve() / uuid.uuid4().hex
    source = root / "source"
    source.mkdir(parents=True)
    original = "def add(a, b):\n    return a - b\n"
    (source / "calculator.py").write_bytes(original.encode())
    (source / "test_public.py").write_bytes(
        b"import unittest\nfrom calculator import add\n"
        b"class TestAdd(unittest.TestCase):\n"
        b"    def test_add(self):\n        self.assertEqual(add(2, 3), 5)\n"
    )
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("GIT_")}
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)

    def git(*arguments):
        return (
            subprocess.run(
                [
                    "git",
                    "-c",
                    "core.autocrlf=false",
                    "-c",
                    "core.hooksPath=" + os.devnull,
                    "-c",
                    "user.name=Agentless Demo",
                    "-c",
                    "user.email=demo@example.invalid",
                    *arguments,
                ],
                cwd=source,
                env=env,
                check=True,
                capture_output=True,
            )
            .stdout.decode()
            .strip()
        )

    git("init")
    git("add", ".")
    git("commit", "-m", "Public arithmetic fixture")
    provider = LocalGitWorkspaceProvider(
        source_repository=source,
        base_commit=git("rev-parse", "HEAD"),
        workspace_root=root / "workspaces",
    )
    runner = DockerTestRunner(args.image, root / "executions")
    commands = (PublicTestCommand(("python", "-m", "unittest", "-v", "test_public")),)
    candidates = []
    for index, (name, operator) in enumerate((("incorrect", "*"), ("correct", "+"))):
        candidate = build_patch_candidate(
            candidate_id=name,
            raw_response="prepared demonstration",
            diff=build_unified_diff(
                {"calculator.py": original},
                {"calculator.py": original.replace("a - b", f"a {operator} b")},
            ),
            localization_rank=0,
            sample_index=index,
        )
        candidates.append(validate_candidate(candidate, provider, runner, commands))
    selected = select_candidate(candidates)
    report = {
        "image_id": runner.image_id,
        "candidates": [asdict(c) for c in candidates],
        "selected": selected.candidate.candidate_id,
        "reason": selected.reason,
        "llm_api_calls": 0,
    }
    (root / "summary.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    for candidate in candidates:
        print(f"{candidate.candidate_id}: {candidate.validation[0].status.value}")
    print(
        f"Selected: {selected.candidate.candidate_id}\nEvidence: {root / 'summary.json'}"
    )
    if selected.candidate.candidate_id != "correct":
        raise SystemExit("Demonstration did not select the expected patch")


if __name__ == "__main__":
    main()
