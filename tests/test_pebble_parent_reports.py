import json

import pytest

from agentless_ml.schemas import ValidationResult, ValidationStatus
from agentless_ml.validation.reports import (
    PEBBLE_RANDOM_PARENTS, PEBBLE_RANDOM_PARENT_POLICY,
    ReportFormat, TestReport, parse_report,
)


def report(entries):
    return json.dumps({"results": {"tests": [
        {"suite": test_id.split("::")[0], "name": test_id.split("::")[1], "status": status}
        for test_id, status in entries
    ]}}).encode()


def parse(data, policy=PEBBLE_RANDOM_PARENT_POLICY):
    return parse_report(data, ReportFormat.CTRF_JSON, id_policy=policy)


def failures(cases, parent):
    return ValidationResult(
        ValidationStatus.FAIL, ("public-tests",), 0, exit_code=1,
        test_cases=cases, counted_test_ids=(parent,),
    ).failure_count()


@pytest.mark.parametrize("parent", PEBBLE_RANDOM_PARENTS)
def test_random_children_change_but_parent_matches_and_raw_bytes_survive(parent):
    a = report([(parent + "/seed=1/nested", "passed"), (parent, "passed")])
    b = report([(parent, "passed"), (parent + "/seed=99", "passed"),
                (parent + "/different-shape", "passed")])
    original = bytes(a)
    assert parse(a) == parse(b)
    assert failures(parse(b), parent) == 0
    assert a == original
    assert len(parse(a, None)) == 2


@pytest.mark.parametrize("parent", PEBBLE_RANDOM_PARENTS)
@pytest.mark.parametrize("entries", [
    (("", "passed"), ("/child", "failed")),
    (("", "passed"), ("/child/nested", "failed")),
    (("", "passed"), ("/child", "other")),
    (("", "skipped"), ("/child", "passed")),
    (("/child", "passed"),),
    (("", "passed"),),
    (("", "passed"), ("/child", "skipped")),
    (("", "failed"), ("/child", "passed")),
    (("", "skipped"), ("", "passed"), ("/child", "passed")),
    (("", "passed"), ("/child", "failed"), ("/child", "passed")),
])
def test_nonpassing_or_incomplete_group_is_a_regression(parent, entries):
    cases = parse(report([(parent + suffix, status) for suffix, status in entries]))
    assert len(cases) == 1
    assert failures(cases, parent) == 1


def test_wholly_missing_group_is_still_a_regression():
    cases = parse(report([("other/package::TestOther", "passed")]))
    assert failures(cases, PEBBLE_RANDOM_PARENTS[0]) == 1


def test_exact_allowlist_boundaries_do_not_group_other_tests():
    root = PEBBLE_RANDOM_PARENTS[0]
    ids = [root + "Extra/k=1", root.replace("pebble::", "other::") + "/k=1",
           "other/package::TestRandom/seed=1"]
    data = report([(test_id, "passed") for test_id in ids])
    assert parse(data) == parse(data, None)


def test_child_failure_not_masked_by_parent_order_or_repeated_pass():
    root = PEBBLE_RANDOM_PARENTS[0]
    entries = [(root, "passed"), (root + "/a", "failed"), (root + "/b", "passed")]
    assert parse(report(entries)) == parse(report(list(reversed(entries))))
    assert failures(parse(report(entries)), root) == 1


def test_pebble_policy_is_ctrf_only():
    with pytest.raises(ValueError, match="unsupported test ID policy"):
        TestReport(ReportFormat.JUNIT_XML, "/tmp/report.xml",
                   id_policy=PEBBLE_RANDOM_PARENT_POLICY)
