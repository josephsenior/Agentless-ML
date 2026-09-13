"""What a language contributes to the fixed workflow's model-visible prompts.

The prompt renderers never branch on a language name. Each language supplies
this vocabulary instead: its symbol-localization instructions, the example edit
shown in the repair prompt, and the code-fence label for each file extension.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class RepairExample:
    """The single *SEARCH/REPLACE* edit shown to the model as an example."""

    path: str
    search: str
    replace: str
    indented_line: str


@dataclass(frozen=True, slots=True)
class LanguagePrompts:
    """``symbol_localization`` is a template with ``{problem_statement}`` and
    ``{file_contents}`` fields. Files whose extension is not in ``code_fences``
    are fenced with the language name."""

    symbol_localization: str
    repair_example: RepairExample
    code_fences: Mapping[str, str] = field(default_factory=dict)


def guided_symbol_localization(*, targets: str, naming: str, example: str) -> str:
    """The shared symbol-localization prompt for languages beyond published Agentless.

    Every such language gets the same instructions and return format; only what
    it calls its declarations, how their names are spelled, and the example
    locations differ.
    """

    def literal(text: str) -> str:  # Language text must not become template fields.
        return text.replace("{", "{{").replace("}", "}}")

    return (
        "\nPlease look through the GitHub Problem Description and the Skeleton of "
        "Relevant Files.\n"
        f"Identify the {literal(targets)} that need inspection or editing.\n"
        f"{literal(naming)}\n"
        "\n### GitHub Problem Description ###\n{problem_statement}\n"
        "\n### Skeleton of Relevant Files ###\n{file_contents}\n"
        "\nReturn just the locations in an unlabelled fenced block, using "
        "repository-relative paths:\n"
        f"```\n{literal(example)}\n```\n"
        "Use line: N for an exact source line, including ambiguous or unnamed constructs.\n"
    )
