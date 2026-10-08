"""The native Numba reporter observes outcomes, not test selection."""

import os
import subprocess
import sys
from xml.etree import ElementTree as ET

import pytest

from agentless_ml.adapters.benchmarks.deepswe_numba import NUMBA_REPORTER


def run_reporter(tmp_path, entry_text):
    package = tmp_path / "numba" / "testing"
    package.mkdir(parents=True)
    (package.parent / "__init__.py").write_text("", encoding="utf-8")
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "main.py").write_text(
        "from unittest import TextTestRunner as BasicTestRunner\n", encoding="utf-8",
    )
    entry = tmp_path / "runtests.py"
    entry.write_text(entry_text, encoding="utf-8")
    report = tmp_path / "report.xml"
    result = subprocess.run(
        [sys.executable, "-c", NUMBA_REPORTER, str(entry), str(report)],
        cwd=tmp_path, env=dict(os.environ, PYTHONPATH=str(tmp_path)),
        capture_output=True, text=True, check=False,
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
