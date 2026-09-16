"""Select existing regression checks by ID, never by model-generated commands."""

from collections.abc import Sequence
from dataclasses import dataclass, replace

from agentless_ml.schemas import (
    TestCaseStatus,
    ValidationKind,
    ValidationResult,
    ValidationStatus,
)

from .docker import PublicTestCommand


@dataclass(frozen=True, slots=True)
class RegressionTest:
    test_id: str
    command: PublicTestCommand

    def __post_init__(self):
        if (
            not self.test_id.strip()
            or self.test_id != self.test_id.strip()
            or any(c in self.test_id for c in "\r\n\0`")
        ):
            raise ValueError("test ID must be a nonempty single line without fences")
        if self.command.kind != ValidationKind.REGRESSION:
            raise ValueError("inventory commands must be regression checks")


def render_regression_selection_prompt(
    problem: str, passing_ids: tuple[str, ...]
) -> str:
    return (
        f"### Issue ###\n{problem}\n\n"
        "These existing checks pass on the original repository revision:\n```\n"
        + "\n".join(passing_ids)
        + "\n```\nIdentify checks to exclude because fixing the issue may change their expected behavior.\n"
        "Return only exact test IDs, one per line, optionally inside an unlabelled fenced block.\n"
        "Return an empty response to exclude none. Do not invent tests or commands."
    )


def regression_baseline_ids(test: RegressionTest, result: ValidationResult) -> tuple[str, ...]:
    """Which IDs this command's baseline run contributes as passing evidence.

    A command with a declared report contributes each test that individually
    passed, by name, whether the command's own exit was PASS or FAIL: a suite
    that mixes already-broken tests with working ones should not lose the
    working ones as evidence. A command with no report contributes its own
    ``test_id`` as one unit, and only if the whole command passed.
    """
    if result.test_cases:
        return tuple(
            case.test_id for case in result.test_cases if case.status is TestCaseStatus.PASSED
        )
    return (test.test_id,) if result.status is ValidationStatus.PASS else ()


@dataclass(frozen=True, slots=True)
class RegressionBaseline:
    """One command's baseline outcome, kept to build the frozen schedule."""

    test: RegressionTest
    passing_ids: tuple[str, ...]
    from_report: bool


def select_regression_commands(
    baselines: Sequence[RegressionBaseline], excluded: tuple[str, ...]
) -> tuple[PublicTestCommand, ...]:
    """The frozen commands for candidates: unchanged, or narrowed to kept tests.

    A command is dropped once none of its baseline-passing IDs survive
    exclusion: it would contribute exactly zero counted tests either way.
    """
    excluded_set = set(excluded)
    commands = []
    for baseline in baselines:
        kept = tuple(test_id for test_id in baseline.passing_ids if test_id not in excluded_set)
        if not kept:
            continue
        commands.append(
            replace(baseline.test.command, counted_test_ids=kept)
            if baseline.from_report
            else baseline.test.command
        )
    return tuple(commands)


def parse_regression_exclusions(
    response: str, passing_ids: tuple[str, ...]
) -> tuple[str, ...]:
    lines = response.strip().splitlines()
    if lines and lines[0] == "```" and lines[-1] == "```" and len(lines) >= 2:
        lines = lines[1:-1]
    requested = {line.strip() for line in lines if line.strip()}
    unknown = requested - set(passing_ids)
    if unknown:
        raise ValueError(
            "unknown or nonpassing regression IDs: " + ", ".join(sorted(unknown))
        )
    return tuple(test_id for test_id in passing_ids if test_id in requested)
