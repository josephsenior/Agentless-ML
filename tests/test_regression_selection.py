import pytest

from agentless_ml.schemas import (
    TestCaseResult,
    TestCaseStatus,
    ValidationKind,
    ValidationResult,
    ValidationStatus,
)
from agentless_ml.validation import (
    PublicTestCommand,
    RegressionTest,
    ReportFormat,
    TestReport,
)
from agentless_ml.validation.regression import (
    RegressionBaseline,
    parse_regression_exclusions,
    regression_baseline_ids,
    render_regression_selection_prompt,
    select_regression_commands,
)

P, F = TestCaseStatus.PASSED, TestCaseStatus.FAILED


def result(status, test_cases=()):
    return ValidationResult(
        status=status, command=("cmd",), duration_seconds=0, test_cases=test_cases
    )


def suite_test(test_id="suite"):
    return RegressionTest(
        test_id,
        PublicTestCommand(("pytest",), report=TestReport(ReportFormat.JUNIT_XML, "r.xml")),
    )


def test_exclusion_direction_order_and_empty_response():
    passing = ("test_b", "test_a", "test_c")
    assert parse_regression_exclusions("```\ntest_c\ntest_a\ntest_c\n```", passing) == (
        "test_a",
        "test_c",
    )
    assert parse_regression_exclusions("", passing) == ()
    assert parse_regression_exclusions("```\n```", passing) == ()
    assert "exclude" in render_regression_selection_prompt("issue", passing)


@pytest.mark.parametrize(
    "response",
    ["invented", "test_a\nrm -rf /", "```python\ntest_a\n```", "Exclude test_a"],
)
def test_unknown_outputs_cannot_become_commands(response):
    with pytest.raises(ValueError, match="unknown"):
        parse_regression_exclusions(response, ("test_a",))


def test_inventory_validation():
    with pytest.raises(ValueError, match="single line"):
        RegressionTest("a\nb", PublicTestCommand(("pytest",)))
    with pytest.raises(ValueError, match="regression"):
        RegressionTest(
            "a", PublicTestCommand(("pytest",), kind=ValidationKind.REPRODUCTION)
        )


def test_baseline_ids_without_a_report_is_the_whole_command():
    test = RegressionTest("suite", PublicTestCommand(("pytest",)))
    assert regression_baseline_ids(test, result(ValidationStatus.PASS)) == ("suite",)
    assert regression_baseline_ids(test, result(ValidationStatus.FAIL)) == ()


def test_baseline_ids_with_a_report_is_each_passing_test_by_name():
    # test_c is a pre-existing, unrelated failure: the command's own exit is
    # FAIL, but test_a and test_b still count as baseline-passing evidence.
    cases = (
        TestCaseResult("test_a", P),
        TestCaseResult("test_b", P),
        TestCaseResult("test_c", F),
    )
    ids = regression_baseline_ids(suite_test(), result(ValidationStatus.FAIL, cases))
    assert ids == ("test_a", "test_b")


def test_select_commands_without_a_report_is_unchanged():
    keep, drop = RegressionTest("keep", PublicTestCommand(("keep",))), RegressionTest(
        "drop", PublicTestCommand(("drop",))
    )
    baselines = [
        RegressionBaseline(keep, ("keep",), from_report=False),
        RegressionBaseline(drop, ("drop",), from_report=False),
    ]
    selected = select_regression_commands(baselines, excluded=("drop",))
    assert selected == (keep.command,)
    assert selected[0].counted_test_ids is None


def test_select_commands_with_a_report_narrows_counted_test_ids():
    test = suite_test()
    baseline = RegressionBaseline(test, ("test_a", "test_b"), from_report=True)
    selected = select_regression_commands([baseline], excluded=("test_a",))
    assert len(selected) == 1
    assert selected[0].argv == test.command.argv  # same command, still runs
    assert selected[0].counted_test_ids == ("test_b",)  # narrowed to what's left


def test_select_commands_drops_a_report_command_left_with_nothing_counted():
    test = suite_test()
    baseline = RegressionBaseline(test, ("test_a",), from_report=True)
    assert select_regression_commands([baseline], excluded=("test_a",)) == ()
