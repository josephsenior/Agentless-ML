"""Reporter bookkeeping must not change lib0's execution contract."""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from agentless_ml.adapters.benchmarks.deepswe_execution import deepswe_test_command
from agentless_ml.adapters.benchmarks.deepswe_yjs import YJS_PREPARE, YJS_REPORTER
from agentless_ml.validation import DockerTestRunner
from agentless_ml.workspace import LocalGitWorkspaceProvider


@pytest.fixture
def node():
    executable = shutil.which("node")
    if not executable:
        pytest.skip("Node is needed for the JavaScript reporter contract checks")
    return executable


def test_yjs_candidate_link_and_public_invocation():
    command = deepswe_test_command("yjs-lib0", ("--filter", "map"))
    script = command.argv[2]
    assert "cp -a /app/node_modules node_modules" in script
    assert 'readlink -f node_modules/@y/y' in script
    assert '= "/tmp/work"' in script
    assert 'NODE_ENV=development node tests/.agentless-entry.mjs --repetition-time 50 "$@"' in script
    assert command.argv[-2:] == ("--filter", "map")


@pytest.mark.parametrize("source, succeeds", [
    ("import { runTests } from 'lib0/testing'\nrunTests({})", True),
    ('import {runTests} from "lib0/testing";\nrunTests({})', True),
    ("import { runTests as run } from 'lib0/testing'", False),
    ("import { runTests } from 'lib0/testing'\n" * 2, False),
])
def test_entry_rewrite_is_narrow_and_fails_closed(node, tmp_path, source, succeeds):
    tests = tmp_path / "tests"
    tests.mkdir()
    entry = tests / "index.js"
    entry.write_text(source, encoding="utf-8")
    result = subprocess.run([node, "-e", YJS_PREPARE], cwd=tmp_path, capture_output=True)
    assert (result.returncode == 0) == succeeds
    assert entry.read_text(encoding="utf-8") == source
    output = tests / ".agentless-entry.mjs"
    assert output.exists() == succeeds
    if succeeds:
        assert "runTests({})" in output.read_text(encoding="utf-8")
        assert "./.agentless-reporter.mjs" in output.read_text(encoding="utf-8")


def test_reporter_delegates_repetitions_context_and_skips(node, tmp_path):
    dependency = tmp_path / "node_modules" / "lib0"
    dependency.mkdir(parents=True)
    (dependency / "package.json").write_text(
        '{"type":"module","exports":{"./testing":"./testing.js"}}', encoding="utf-8")
    # A controlled original-runner stand-in owns scheduling. It invokes a
    # repeated test twice with the same context and leaves one test filtered.
    (dependency / "testing.js").write_text("""
      class SkipError extends Error {}
      export const skip = () => { throw new SkipError() }
      export const runTests = async modules => {
        let success = true
        const context = { marker: 42 }
        for (const mod of Object.values(modules)) {
          for (const [name, fn] of Object.entries(mod)) {
            if (!name.startsWith('test') && !name.startsWith('benchmark')) continue
            if (name === 'testFiltered') continue
            for (let i = 0; i < (name === 'testRepeat' ? 2 : 1); i++) {
              try { await fn(context) }
              catch (error) { if (error.constructor !== SkipError) success = false; break }
            }
          }
        }
        return success
      }
    """, encoding="utf-8")
    report = tmp_path / "report.json"
    (tmp_path / "reporter.mjs").write_text(
        YJS_REPORTER.replace("'/tmp/ctrf.json'", json.dumps(str(report))), encoding="utf-8")
    (tmp_path / "entry.mjs").write_text("""
      import { runTests } from './reporter.mjs'
      import { skip } from 'lib0/testing'
      let repetitions = 0
      const success = await runTests({map: {
        testPass: tc => { if (tc.marker !== 42) throw Error('context lost') },
        testAsync: async () => {},
        testRepeat: () => { if (++repetitions === 2) throw Error('later failure') },
        testSkip: () => skip(),
        testFakeSkip: () => { throw new (class SkipError extends Error {})() },
        testFiltered: () => { throw Error('must not be invoked') },
        benchmarkPass: () => {},
        helper: () => { throw Error('not a test') }
      }})
      if (success || repetitions !== 2) throw Error('runner result changed')
    """, encoding="utf-8")
    subprocess.run([node, "entry.mjs"], cwd=tmp_path, check=True, capture_output=True)
    cases = json.loads(report.read_text())["results"]["tests"]
    assert [(case["name"], case["status"]) for case in cases] == [
        ("testPass", "passed"), ("testAsync", "passed"), ("testRepeat", "failed"),
        ("testSkip", "skipped"), ("testFakeSkip", "failed"),
        ("testFiltered", "skipped"), ("benchmarkPass", "passed"),
    ]
    assert all(case["suite"] == "map" for case in cases)
    # A runner-level error cannot leave a partial report, even after a pass.
    report.unlink()
    (dependency / "testing.js").write_text("""
      export const skip = () => { throw new Error('skip') }
      export const runTests = async modules => {
        await modules.map.testPass({marker: 42})
        throw new Error('runner setup broke')
      }
    """, encoding="utf-8")
    result = subprocess.run([node, "entry.mjs"], cwd=tmp_path, capture_output=True)
    assert result.returncode != 0
    assert not report.exists()


@pytest.mark.skipif(not os.environ.get("AGENTLESS_YJS_REPOSITORY"),
                    reason="opt-in pinned Yjs Docker check")
def test_pinned_lib0_detects_candidate_code_repetition_and_skip(tmp_path):
    provider = LocalGitWorkspaceProvider(
        Path(os.environ["AGENTLESS_YJS_REPOSITORY"]),
        "7795050a749bd1111cbbdd9d0219b27226a8e710", tmp_path / "workspaces")
    artifacts = Path(os.environ.get("AGENTLESS_YJS_ARTIFACTS", str(tmp_path / "logs")))
    runner = DockerTestRunner(
        "sha256:91b1986f864befaef716579fa641d57051257ea5484515f9befd30a4f5d800ef",
        artifacts, memory_mb=4096, cpus=2, tmpfs_mb=4096,
        pids_limit=2048, run_as_image_user=True)
    with provider.create() as workspace:
        source = workspace.path / "src" / "index.js"
        source.write_text(source.read_text(encoding="utf-8") +
                          "\nexport const agentlessCandidateProbe = true\n", encoding="utf-8")
        tests = workspace.path / "tests" / "y-map.tests.js"
        tests.write_text(tests.read_text(encoding="utf-8") + """
          import { agentlessCandidateProbe } from '@y/y'
          export const testAgentlessCandidateProbe = () => {
            if (!agentlessCandidateProbe) throw Error('candidate source missing')
            throw Error('candidate source confirmed')
          }
          let agentlessRepeats = 0
          export const testRepeatAgentlessProbe = () => {
            if (++agentlessRepeats === 2) throw Error('later repetition failed')
          }
          export const testAgentlessSkipProbe = () => t.skip()
        """, encoding="utf-8")
        execution = runner.run(workspace.path, deepswe_test_command(
            "yjs-lib0", ("--filter", "agentless"), timeout_seconds=120))
    cases = {case.test_id: case.status.value for case in execution.result.test_cases}
    assert execution.result.status.value == "fail", execution.message
    assert cases["map::testAgentlessCandidateProbe"] == "failed"
    assert cases["map::testRepeatAgentlessProbe"] == "failed"
    assert cases["map::testAgentlessSkipProbe"] == "skipped"
    assert all(status == "skipped" for name, status in cases.items()
               if "Agentless" not in name)
