"""Deterministic Agentless-compatible localization context rendering."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import PurePosixPath

from agentless_ml.adapters.languages import LanguageAdapter, PythonAdapter

FILE_LOCALIZATION_TEMPLATE = """
Please look through the following GitHub problem description and Repository structure and provide a list of files that one would need to edit to fix the problem.

### GitHub Problem Description ###
{problem_statement}

###

### Repository Structure ###
{structure}

###

Please only provide the full path and return at most 5 files.
The returned files should be separated by new lines ordered by most to least important and wrapped with ```
For example:
```
file1.py
file2.py
```
"""


FILE_BLOCK_TEMPLATE = """
### File: {file_name} ###
```python
{file_content}
```
"""


def _insert_path(tree: dict[str, object], parts: tuple[str, ...]) -> None:
    current = tree
    for part in parts[:-1]:
        child = current.setdefault(part, {})
        if not isinstance(child, dict):
            raise ValueError(f"path collides with file entry: {part}")
        current = child
    current.setdefault(parts[-1], None)


def render_legacy_project_tree(ordered_file_paths: Sequence[str]) -> str:
    return render_project_tree(ordered_file_paths, adapter=PythonAdapter())


def render_project_tree(
    ordered_file_paths: Sequence[str],
    *,
    adapter: LanguageAdapter,
) -> str:
    """Render a source tree using the adapter's file and test filters.

    Input order is explicit because the published Python implementation inherits
    ``os.walk``/dictionary insertion order. Paths must include the repository
    root component, for example ``requests/requests/sessions.py``.
    """
    tree: dict[str, object] = {}
    for raw_path in ordered_file_paths:
        parts = tuple(part for part in raw_path.replace("\\", "/").split("/") if part)
        if len(parts) < 2:
            raise ValueError("file path must include a repository root and file")
        if any(part == ".." for part in parts):
            raise ValueError("file path must not contain parent traversal")
        if not adapter.is_source_path("/".join(parts[1:])):
            continue
        if adapter.is_test_path("/".join(parts)):
            continue
        _insert_path(tree, parts)

    def render(node: Mapping[str, object], spacing: int = 0) -> str:
        result = ""
        for name, child in node.items():
            if child is None:
                result += " " * spacing + name + "\n"
            else:
                result += " " * spacing + name + "/\n"
                result += render(child, spacing + 4)  # type: ignore[arg-type]
        return result

    return render(tree)


def render_file_localization_prompt(
    problem_statement: str,
    project_tree: str,
    *,
    extension: str = ".py",
) -> str:
    template = FILE_LOCALIZATION_TEMPLATE.replace("file1.py", "file1" + extension)
    template = template.replace("file2.py", "file2" + extension)
    return template.format(
        problem_statement=problem_statement,
        structure=project_tree.strip(),
    ).strip()


def render_symbol_localization_prompt(
    problem_statement: str,
    ordered_files: Mapping[str, str],
    *,
    adapter: LanguageAdapter | None = None,
    compress_assign: bool = False,
    total_lines: int = 30,
    prefix_lines: int = 10,
    suffix_lines: int = 10,
) -> str:
    parser = adapter or PythonAdapter()
    blocks = []
    for file_name, source in ordered_files.items():
        skeleton = parser.render_skeleton(
            source,
            path=file_name,
            compress_assign=compress_assign,
            total_lines=total_lines,
            prefix_lines=prefix_lines,
            suffix_lines=suffix_lines,
        )
        label = parser.prompts.code_fences.get(
            PurePosixPath(file_name).suffix, parser.language
        )
        template = FILE_BLOCK_TEMPLATE.replace("```python", "```" + label)
        blocks.append(template.format(file_name=file_name, file_content=skeleton))
    return parser.prompts.symbol_localization.format(
        problem_statement=problem_statement,
        file_contents="".join(blocks),
    )
