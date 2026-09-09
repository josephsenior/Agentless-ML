"""Select existing regression checks by ID, never by model-generated commands."""

from dataclasses import dataclass

from agentless_ml.schemas import ValidationKind

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
