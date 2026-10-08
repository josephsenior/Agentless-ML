"""The native Numba reporter observes outcomes, not test selection."""

import os
import subprocess
import sys
from xml.etree import ElementTree as ET

import pytest

from agentless_ml.adapters.benchmarks.deepswe_numba import NUMBA_REPORTER


def run_reporter(tmp_path, entry_text, *flags):
    package = tmp_path / "numba" / "testing"
    package.mkdir(parents=True)
    (package.parent / "__init__.py").write_text("", encoding="utf-8")
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "main.py").write_text(
        '''import unittest
class BasicTestRunner(unittest.TextTestRunner): pass
class ParallelTestResult(unittest.TextTestResult):
    def add_results(self, result):
        self.testsRun += result.testsRun
        for name in ("failures", "errors", "skipped", "expectedFailures", "unexpectedSuccesses"):
            getattr(self, name).extend(getattr(result, name))
class ParallelTestRunner(unittest.TextTestRunner):
    resultclass = ParallelTestResult
''', encoding="utf-8",
    )
    entry = tmp_path / "runtests.py"
    if flags:
        # Real Numba cases live in importable modules, not __main__.
        definitions, schedule = entry_text.split('if __name__ == "__main__":', 1)
        (tmp_path / "worker_cases.py").write_text(definitions, encoding="utf-8")
        entry_text = 'from worker_cases import *\nif __name__ == "__main__":' + schedule
    entry.write_text(entry_text, encoding="utf-8")
    report = tmp_path / "report.xml"
    result = subprocess.run(
        [sys.executable, "-c", NUMBA_REPORTER, str(entry), str(report), *flags],
        cwd=tmp_path, env=dict(os.environ, PYTHONPATH=str(tmp_path)),
        capture_output=True, text=True, check=False, timeout=60,
    )
    return result, report


def test_native_reporter_records_failures_and_ignores_nested_runner_probes(tmp_path):
    result, report = run_reporter(tmp_path, '''
import unittest
from numba.testing.main import BasicTestRunner
class Inner(unittest.TestCase):
    def test_probe(self): self.fail("nested runner probe")
class Cases(unittest.TestCase):
    def test_ok(self): pass
    def test_failure(self): self.fail("real failure")
    def test_error(self): raise RuntimeError("real error")
    @unittest.skip("normal skip")
    def test_skip(self): pass
    @unittest.expectedFailure
    def test_expected(self): self.fail("expected")
    @unittest.expectedFailure
    def test_unexpected(self): pass
    def test_subtests(self):
        with self.subTest(x=1): self.fail("subtest failure")
        with self.subTest(x=2): pass
    def test_nested(self):
        result = BasicTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(Inner))
        self.assertFalse(result.wasSuccessful())
class BrokenFixture(unittest.TestCase):
    @classmethod
    def setUpClass(cls): raise RuntimeError("fixture failed")
    def test_blocked(self): pass
suite = unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(Cases),
                           unittest.defaultTestLoader.loadTestsFromTestCase(BrokenFixture)])
result = BasicTestRunner().run(suite)
raise SystemExit(0 if result.wasSuccessful() else 1)
''')
    assert result.returncode == 1
    cases = ET.parse(report).getroot().findall("testcase")
    assert len(cases) == 9
    assert not any("Inner" in case.get("classname", "") for case in cases)
    assert not any(case.get("name") == "test_blocked" for case in cases)
    assert sum(case.find("failure") is not None for case in cases) == 3
    assert sum(case.find("error") is not None for case in cases) == 2
    assert sum(case.find("skipped") is not None for case in cases) == 2
    assert sum(len(case) == 0 for case in cases) == 2


@pytest.mark.parametrize("entry", [
    "raise RuntimeError('bootstrap failure')",
    "raise SystemExit(125)",
    "raise SystemExit(0)",
    "from numba.testing.main import BasicTestRunner\nimport unittest\n"
    "BasicTestRunner().run(unittest.TestSuite())\nraise SystemExit(0)",
])
def test_native_reporter_refuses_bootstrap_failure_and_empty_runs(tmp_path, entry):
    result, report = run_reporter(tmp_path, entry)
    assert result.returncode != 0
    assert not report.exists()


PARALLEL_ENTRY = '''
import unittest
from numba.testing.main import ParallelTestRunner, BasicTestRunner
class Cases(unittest.TestCase):
    def test_ok(self): pass
    def test_failure(self): self.fail("worker failure")
    def test_error(self): raise RuntimeError("worker error")
    @unittest.skip("worker skip")
    def test_skip(self): pass
    @unittest.expectedFailure
    def test_expected(self): self.fail("expected")
    @unittest.expectedFailure
    def test_unexpected(self): pass
    def test_subtest(self):
        with self.subTest(x=1): self.fail("worker subtest")
    def test_nested(self):
        class Inner(unittest.TestCase):
            def test_probe(self): self.fail("nested")
        inner = BasicTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(Inner))
        self.assertFalse(inner.wasSuccessful())
class BrokenFixture(unittest.TestCase):
    @classmethod
    def setUpClass(cls): raise RuntimeError("fixture error")
    def test_blocked(self): pass
def child_outcome(case):
    import io
    from types import SimpleNamespace
    result = unittest.TextTestRunner(stream=io.StringIO()).run(unittest.TestSuite([case]))
    return SimpleNamespace(test_id=case.id(), testsRun=result.testsRun,
        failures=result.failures, errors=result.errors, skipped=result.skipped,
        expectedFailures=result.expectedFailures, unexpectedSuccesses=result.unexpectedSuccesses)
if __name__ == "__main__":
    import multiprocessing, sys
    assert sys.argv[1:] == ["-m", "2"]
    cases = list(unittest.defaultTestLoader.loadTestsFromTestCase(Cases))
    cases += list(unittest.defaultTestLoader.loadTestsFromTestCase(BrokenFixture))
    def schedule(result):
        with multiprocessing.get_context("spawn").Pool(2) as pool:
            for child in pool.imap_unordered(child_outcome, cases):
                result.add_results(child)
        # Exercise the callbacks used for Numba's serial-only remainder.
        unittest.TestSuite([Cases("test_ok")]).run(result)
    result = ParallelTestRunner().run(schedule)
    raise SystemExit(0 if result.wasSuccessful() else 1)
'''


def test_parallel_reporter_merges_spawned_workers_and_serial_remainder(tmp_path):
    result, report = run_reporter(tmp_path, PARALLEL_ENTRY, "-m", "2")
    assert result.returncode == 1, result.stderr
    cases = ET.parse(report).getroot().findall("testcase")
    assert len(cases) == 9
    assert not any(case.get("name") in ("test_probe", "test_blocked") for case in cases)
    assert sum(case.find("failure") is not None for case in cases) == 3
    assert sum(case.find("error") is not None for case in cases) == 2
    assert sum(case.find("skipped") is not None for case in cases) == 2
    assert sum(len(case) == 0 for case in cases) == 2


def test_parallel_reporter_refuses_incomplete_worker_merge(tmp_path):
    entry = PARALLEL_ENTRY.replace("result.add_results(child)",
                                   "result.add_results(child); raise RuntimeError('interrupted pool')")
    result, report = run_reporter(tmp_path, entry, "-m", "2")
    assert result.returncode != 0
    assert not report.exists()


@pytest.mark.parametrize("count", [0, 2])
def test_parallel_reporter_refuses_ambiguous_worker_success(tmp_path, count):
    entry = '''
from types import SimpleNamespace
from numba.testing.main import ParallelTestRunner
def schedule(result):
    result.add_results(SimpleNamespace(test_id="worker.case", testsRun=COUNT,
        failures=[], errors=[], skipped=[], expectedFailures=[], unexpectedSuccesses=[]))
ParallelTestRunner().run(schedule)
'''.replace("COUNT", str(count))
    result, report = run_reporter(tmp_path, entry)
    assert result.returncode != 0
    assert not report.exists()


def test_parallel_reporter_duplicate_case_retains_worst_outcome(tmp_path):
    entry = PARALLEL_ENTRY.replace('unittest.TestSuite([Cases("test_ok")]).run(result)',
                                 'unittest.TestSuite([Cases("test_failure")]).run(result)')
    result, report = run_reporter(tmp_path, entry, "-m", "2")
    assert result.returncode == 1
    cases = ET.parse(report).getroot().findall("testcase")
    failures = [case for case in cases if case.get("name") == "test_failure"]
    assert len(failures) == 1 and failures[0].find("failure") is not None


def test_resource_diagnostic_is_separate_and_keeps_outer_limit():
    import importlib.util
    from pathlib import Path
    path = Path(__file__).resolve().parents[1] / "tools/run_numba_resource_diagnostic.py"
    spec = importlib.util.spec_from_file_location("numba_diagnostic", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    command = module.diagnostic_command()
    assert command.timeout_seconds == 1800
    assert command.report is None and command.counted_test_ids is None
    script = command.argv[2]
    assert "--kill-after=10s 300s" in script
    assert script.endswith("/tmp/diagnostic-report.xml -m 2")
    assert "numba.tests." not in script  # no narrowed test schedule
    assert "build_ext --inplace" in script and "refusing non-candidate import" in script
