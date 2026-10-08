"""Record outcomes while Numba's own runner retains discovery and ordering."""

NUMBA_REPORTER = r'''
import runpy
import os
import sys
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET
from numba.testing.main import BasicTestRunner, ParallelTestRunner, ParallelTestResult

records = {}
completed = False
active_result = None
severity = {"passed": 0, "skipped": 1, "failed": 2, "error": 3}

def record_id(result, key, status, message=""):
    if result is not active_result:
        return
    previous = records.get(key)
    if previous is None or severity[status] >= severity[previous[0]]:
        records[key] = (status, message)

def record(result, test, status, message=""):
    record_id(result, test.id(), status, message)

class RecordedResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        global active_result
        if active_result is None:
            active_result = self

    def addSuccess(self, test):
        super().addSuccess(test)
        record(self, test, "passed")

    def addFailure(self, test, err):
        super().addFailure(test, err)
        record(self, test, "failed", self._exc_info_to_string(err, test))

    def addError(self, test, err):
        super().addError(test, err)
        record(self, test, "error", self._exc_info_to_string(err, test))

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        record(self, test, "skipped", reason)

    def addExpectedFailure(self, test, err):
        super().addExpectedFailure(test, err)
        record(self, test, "skipped", "expected failure: " + self._exc_info_to_string(err, test))

    def addUnexpectedSuccess(self, test):
        super().addUnexpectedSuccess(test)
        record(self, test, "failed", "unexpected success (unittest failure)")

    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        if err is not None:
            status = "failed" if issubclass(err[0], test.failureException) else "error"
            record(self, test, status, self._exc_info_to_string(err, subtest))

    def stopTestRun(self):
        super().stopTestRun()
        global completed
        if self is active_result:
            completed = True

BasicTestRunner.resultclass = RecordedResult

class RecordedParallelResult(RecordedResult, ParallelTestResult):
    def add_results(self, child):
        # Keep native aggregation, output and success semantics.
        super().add_results(child)
        outcomes = []
        for status, items in (("failed", child.failures), ("error", child.errors),
                              ("skipped", child.skipped),
                              ("skipped", child.expectedFailures)):
            for case, message in items:
                # Subtest IDs are not separate scheduled test cases.
                target = getattr(case, "test_case", case)
                record(self, target, status, str(message))
                outcomes.append((status, str(message)))
        for case in child.unexpectedSuccesses:
            record(self, case, "failed", "unexpected success (unittest failure)")
            outcomes.append(("failed", "unexpected success (unittest failure)"))
        if child.testsRun == 1:
            status, message = max(outcomes, key=lambda item: severity[item[0]]) if outcomes else ("passed", "")
            record_id(self, child.test_id, status, message)
        elif child.testsRun != 0 or not outcomes:
            raise RuntimeError("refusing ambiguous Numba worker result")
        if os.environ.get("AGENTLESS_NUMBA_DIAGNOSTIC") == "1" and self.testsRun % 25 == 0:
            print("NUMBA_DIAGNOSTIC_COMPLETED", self.testsRun, flush=True)

ParallelTestRunner.resultclass = RecordedParallelResult
entry = sys.argv[1]
report = Path(sys.argv[2])
sys.argv = [entry, *sys.argv[3:]]
try:
    runpy.run_path(entry, run_name="__main__")
except SystemExit as error:
    if error.code not in (None, 0, 1):
        raise
    code = error.code or 0
else:
    code = 0
if not completed or not records:
    raise SystemExit("refusing incomplete or empty Numba test report")
suite = ET.Element("testsuite", name="numba", tests=str(len(records)))
for key, (status, message) in sorted(records.items()):
    classname, _, name = key.rpartition(".")
    case = ET.SubElement(suite, "testcase", classname=classname, name=name or key)
    if status != "passed":
        tag = {"failed": "failure", "error": "error", "skipped": "skipped"}[status]
        ET.SubElement(case, tag, message=message).text = message
ET.ElementTree(suite).write(report, encoding="utf-8", xml_declaration=True)
raise SystemExit(code)
'''.strip()
