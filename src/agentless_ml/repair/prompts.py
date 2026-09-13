"""Repair prompts with an explicit Agentless v1.5 compatibility boundary."""

from __future__ import annotations

from agentless_ml.adapters.languages import get_language_adapter

_RELEVANT_FILE_INSTRUCTION = """
Below are some code segments, each from a relevant file. One or more of these files may contain bugs.
"""

_SEARCH_REPLACE_PROMPT = """
We are currently solving the following issue within our repository. Here is the issue text:
--- BEGIN ISSUE ---
{problem_statement}
--- END ISSUE ---

{repair_relevant_file_instruction}
--- BEGIN FILE ---
```
{content}
```
--- END FILE ---

Please first localize the bug based on the issue statement, and then generate *SEARCH/REPLACE* edits to fix the issue.

Every *SEARCH/REPLACE* edit must use this format:
1. The file path
2. The start of search block: <<<<<<< SEARCH
3. A contiguous chunk of lines to search for in the existing source code
4. The dividing line: =======
5. The lines to replace into the source code
6. The end of the replace block: >>>>>>> REPLACE

Here is an example:

```{language}
### {example_path}
{search_marker}
{example_search}
{divider_marker}
{example_replace}
{replace_marker}
```

Please note that the *SEARCH/REPLACE* edit REQUIRES PROPER INDENTATION. If you would like to add the line '{indented_line}', you must fully write that out, with all those spaces before the code!
Wrap the *SEARCH/REPLACE* edit in blocks ```{language}...```.
"""


def build_repair_prompt(
    problem_statement: str,
    selected_context: str,
    *,
    language: str = "python",
) -> str:
    """Build the fixed repair-stage prompt.

    Python output is byte-compatible with the v1.5.0 ``--cot --diff_format``
    template. Every language supplies its own example edit; the instructions
    around it are shared.
    """
    if not problem_statement.strip():
        raise ValueError("problem_statement must not be empty")
    if not selected_context.strip():
        raise ValueError("selected_context must not be empty")
    adapter = get_language_adapter(language)
    example = adapter.prompts.repair_example
    return _SEARCH_REPLACE_PROMPT.format(
        problem_statement=problem_statement,
        repair_relevant_file_instruction=_RELEVANT_FILE_INSTRUCTION,
        content=selected_context.rstrip(),
        language=adapter.language,
        example_path=example.path,
        example_search=example.search,
        example_replace=example.replace,
        indented_line=example.indented_line,
        search_marker="<" * 7 + " SEARCH",
        divider_marker="=" * 7,
        replace_marker=">" * 7 + " REPLACE",
    ).strip()
