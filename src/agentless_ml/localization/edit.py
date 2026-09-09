"""Recorded edit-line localization within the source shown after symbol selection."""

from agentless_ml.localization.locations import extract_code_blocks


def render_edit_localization_prompt(
    problem_statement: str, numbered_context: str
) -> str:
    return (
        "Identify the source lines that need editing to solve the issue.\n"
        "Use only file paths and original line numbers shown below.\n"
        "Return an unlabelled fenced block containing a file path followed by\n"
        "one or more entries of the form line: N. Do not generate a repair yet.\n\n"
        f"### Issue ###\n{problem_statement}\n\n"
        f"### Relevant source (original line numbers) ###\n{numbered_context}"
    )


def parse_edit_locations(response: str, visible_intervals) -> dict[str, list[str]]:
    """Reject malformed or unseen targets instead of silently broadening context."""
    result: dict[str, list[str]] = {}
    current = None
    for block in extract_code_blocks(response):
        current = None
        for raw in block.splitlines():
            line = raw.strip()
            if not line:
                continue
            if line in visible_intervals:
                current = line
                continue
            kind, separator, number = line.partition(":")
            number = number.strip()
            if (
                current is None
                or kind != "line"
                or not separator
                or not number.isascii()
                or not number.isdecimal()
            ):
                raise ValueError(f"invalid edit location: {line}")
            value = int(number)
            if value < 1 or not any(
                start <= value <= end for start, end in visible_intervals[current]
            ):
                raise ValueError(f"edit location was not shown: {current}:{value}")
            location = f"line: {value}"
            if location not in result.setdefault(current, []):
                result[current].append(location)
    if not result:
        raise ValueError("edit localization produced no line locations")
    return result
