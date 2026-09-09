import pytest

from agentless_ml.schemas import ValidationKind
from agentless_ml.validation import PublicTestCommand, RegressionTest
from agentless_ml.validation.regression import (
    parse_regression_exclusions,
    render_regression_selection_prompt,
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
