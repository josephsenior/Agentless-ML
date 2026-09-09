"""Repair prompts with an explicit Agentless v1.5 compatibility boundary."""

from __future__ import annotations

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
### mathweb/flask/app.py
{search_marker}
from flask import Flask
{divider_marker}
import math
from flask import Flask
{replace_marker}
```

Please note that the *SEARCH/REPLACE* edit REQUIRES PROPER INDENTATION. If you would like to add the line '        print(x)', you must fully write that out, with all those spaces before the code!
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
    template. Other supported languages use matching code examples.
    """
    if not problem_statement.strip():
        raise ValueError("problem_statement must not be empty")
    if not selected_context.strip():
        raise ValueError("selected_context must not be empty")
    if not language.strip() or "`" in language or "\n" in language:
        raise ValueError("language must be a non-empty code-fence label")
    template = _SEARCH_REPLACE_PROMPT
    if language == "go":
        template = template.replace("mathweb/flask/app.py", "mathutil/format.go")
        template = template.replace(
            "from flask import Flask\n{divider_marker}\nimport math\nfrom flask import Flask",
            'return "hello"\n{divider_marker}\nreturn "Hello"',
        )
        template = template.replace("        print(x)", "    fmt.Println(x)")
    elif language == "rust":
        template = template.replace("mathweb/flask/app.py", "src/lib.rs")
        template = template.replace(
            "from flask import Flask\n{divider_marker}\nimport math\nfrom flask import Flask",
            "a - b\n{divider_marker}\na + b",
        )
        template = template.replace("        print(x)", "    dbg!(x);")
    elif language in {"javascript", "typescript"}:
        suffix = "ts" if language == "typescript" else "js"
        template = template.replace("mathweb/flask/app.py", "src/format." + suffix)
        template = template.replace(
            "from flask import Flask\n{divider_marker}\nimport math\nfrom flask import Flask",
            'return "hello";\n{divider_marker}\nreturn "Hello";',
        )
        template = template.replace("        print(x)", "    console.log(x);")
    return template.format(
        problem_statement=problem_statement,
        repair_relevant_file_instruction=_RELEVANT_FILE_INSTRUCTION,
        content=selected_context.rstrip(),
        language=language,
        search_marker="<" * 7 + " SEARCH",
        divider_marker="=" * 7,
        replace_marker=">" * 7 + " REPLACE",
    ).strip()
