"""Exercise reporting without requiring Sphinx in the framework's environment."""

import json
import os
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from agentless_ml.adapters.benchmarks.deepswe_execution import (
    deepswe_test_command, deepswe_test_plan, load_test_overrides,
)
from agentless_ml.adapters.benchmarks.deepswe_pwntools import run


@pytest.mark.parametrize("setup,cleanup,failures,tries,status", [
    (0, 0, 0, 3, "passed"), (0, 0, 1, 3, "failed"),
    (1, 0, 0, 0, "other"), (0, 1, 0, 3, "other"),
    (0, 0, 0, 0, None),
])
def test_real_builder_results_are_reported_conservatively(
    monkeypatch, tmp_path, setup, cleanup, failures, tries, status,
):
    class Builder:
        def test_doc(self, name, tree):
            self.test_runner = SimpleNamespace(tries=0, failures=0)
            self.setup_runner = SimpleNamespace(tries=0, failures=0)
            self.cleanup_runner = SimpleNamespace(tries=0, failures=0)
            self.test_group(SimpleNamespace(name="default"))

        def test_group(self, group):
            self.test_runner.tries += tries
            self.test_runner.failures += failures
            self.setup_runner.tries += 1
            self.setup_runner.failures += setup
            self.cleanup_runner.failures += cleanup

    original = Builder.test_group
    argv = sys.argv

    def build_main(arguments):
        assert sys.argv == ["sphinx-build", *arguments]
        assert "doctest" in arguments
        Builder().test_doc("tubes/process", None)
        return int(bool(setup or cleanup or failures))

    for name in ("sphinx", "sphinx.cmd", "sphinx.cmd.build", "sphinx.ext", "sphinx.ext.doctest"):
        monkeypatch.setitem(sys.modules, name, ModuleType(name))
    sys.modules["sphinx.cmd.build"].build_main = build_main
    sys.modules["sphinx.ext.doctest"].DocTestBuilder = Builder
    report = tmp_path / "report.json"
    assert run(report) == int(bool(setup or cleanup or failures))
    cases = json.loads(report.read_text())["results"]["tests"]
    assert len(cases) == (0 if status is None else 1)
    if cases:
        assert cases[0]["status"] == status
        assert cases[0]["suite"] == "tubes/process"
        assert cases[0]["examples"] == tries
    assert Builder.test_group is original
    assert sys.argv is argv


def test_pwntools_plan_runs_public_sphinx_configuration(tmp_path):
    overrides = load_test_overrides(Path(__file__).resolve().parents[1] / "experiments/deepswe/test_overrides.json")
    plan = deepswe_test_plan("python", tmp_path, overrides["pwntools-tube-multiplexing"])
    assert plan.runner == "pwntools-doctest" and plan.targets == ()
    script = plan.command().argv[2]
    assert "cd /tmp/work/docs" in script
    assert "PYTHONPATH=/tmp/work/src:/tmp/work PWNLIB_NOTERM=1 python" in script
    assert "pip install" not in script
    with pytest.raises(ValueError, match="does not support narrowed targets"):
        deepswe_test_command(plan.runner, ("tubes/process",))


def test_unhandled_builder_error_does_not_publish_partial_evidence(monkeypatch, tmp_path):
    class Builder:
        def test_doc(self, name, tree):
            pass

        def test_group(self, group):
            pass

    originals = (Builder.test_doc, Builder.test_group, sys.argv)

    def build_main(arguments):
        raise RuntimeError("builder aborted")

    for name in ("sphinx", "sphinx.cmd", "sphinx.cmd.build", "sphinx.ext", "sphinx.ext.doctest"):
        monkeypatch.setitem(sys.modules, name, ModuleType(name))
    sys.modules["sphinx.cmd.build"].build_main = build_main
    sys.modules["sphinx.ext.doctest"].DocTestBuilder = Builder
    report = tmp_path / "report.json"
    with pytest.raises(RuntimeError, match="builder aborted"):
        run(report)
    assert not report.exists()
    assert (Builder.test_doc, Builder.test_group, sys.argv) == originals


@pytest.mark.skipif(
    not os.environ.get("AGENTLESS_PWNTOOLS_DOCS_IMAGE"),
    reason="opt-in dependency-augmented Pwntools candidate/config probe",
)
def test_sphinx_uses_candidate_source_and_preserves_public_setup_and_flags(tmp_path):
    from agentless_ml.validation import DockerTestRunner
    from agentless_ml.workspace import LocalGitWorkspaceProvider

    repositories = Path(os.environ["AGENTLESS_DELEGATED_TASK_REPOSITORIES"])
    provider = LocalGitWorkspaceProvider(
        repositories / "pwntools-tube-multiplexing",
        "76894a5404a65d2800b6d0adaf3485ecba275caa", tmp_path / "workspaces",
    )
    artifacts = Path(os.environ.get("AGENTLESS_PWNTOOLS_DOCS_ARTIFACTS", str(tmp_path / "logs")))
    runner = DockerTestRunner(
        os.environ["AGENTLESS_PWNTOOLS_DOCS_IMAGE"], artifacts,
        memory_mb=8192, cpus=2, tmpfs_mb=4096,
        pids_limit=2048, run_as_image_user=True,
    )
    with provider.create() as workspace:
        source = workspace.path / "pwnlib/testexample.py"
        source.write_text(source.read_text(encoding="utf-8") + "\nagentless_candidate_marker = True\n", encoding="utf-8")
        docs = workspace.path / "docs/source"
        # Only this synthetic probe is discovered; this is not a full baseline.
        excluded = [path.relative_to(docs).as_posix() for path in docs.rglob("*.rst")]
        conf = docs / "conf.py"
        conf.write_text(conf.read_text(encoding="utf-8") +
                        f"\nexclude_patterns = {excluded!r}\nmaster_doc = 'agentless-candidate-probe'\n", encoding="utf-8")
        (docs / "agentless-candidate-probe.rst").write_text('''Candidate probe
===============

.. testsetup:: *

   from pwnlib.testexample import agentless_candidate_marker

.. doctest:: visible

   >>> agentless_candidate_marker
   True
   >>> False # doctest: +SKIP
   True
   >>> False # doctest: +WINDOWS
   True
   >>> True # doctest: +LINUX
   True

.. doctest:: deliberate-failure

   >>> agentless_candidate_marker
   False

.. testsetup:: setup-error

   raise RuntimeError('intentional setup failure')

.. doctest:: setup-error

   >>> True
   True

.. doctest:: cleanup-error

   >>> True
   True

.. testcleanup:: cleanup-error

   raise RuntimeError('intentional cleanup failure')
''', encoding="utf-8")
        probe_runner = os.environ.get("AGENTLESS_PWNTOOLS_DOCS_RUNNER", "pwntools-doctest")
        execution = runner.run(workspace.path, deepswe_test_command(probe_runner, timeout_seconds=180))
    assert execution.result.status.value == "fail", execution.message
    cases = {case.test_id: case.status.value for case in execution.result.test_cases}
    assert cases == {
        "agentless-candidate-probe::visible": "passed",
        "agentless-candidate-probe::deliberate-failure": "failed",
        "agentless-candidate-probe::setup-error": "error",
        "agentless-candidate-probe::cleanup-error": "error",
    }
    report = json.loads((Path(execution.artifact_directory) / "report.json").read_text(encoding="utf-8"))
    visible = next(case for case in report["results"]["tests"] if case["name"] == "visible")
    # Four examples in the fixture, but Windows is filtered and SKIP is skipped.
    assert visible["examples"] == 2
