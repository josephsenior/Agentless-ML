"""Deterministic Agentless-compatible localization context rendering."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from agentless_ml.adapters.languages import PythonAdapter


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


SYMBOL_LOCALIZATION_TEMPLATE = """
Please look through the following GitHub Problem Description and the Skeleton of Relevant Files.
Identify all locations that need inspection or editing to fix the problem, including directly related areas as well as any potentially related global variables, functions, and classes.
For each location you provide, either give the name of the class, the name of a method in a class, the name of a function, or the name of a global variable.

### GitHub Problem Description ###
{problem_statement}

### Skeleton of Relevant Files ###
{file_contents}

###

Please provide the complete set of locations as either a class name, a function name, or a variable name.
Note that if you include a class, you do not need to list its specific methods.
You can include either the entire class or don't include the class name and instead include specific methods in the class.
### Examples:
```
full_path1/file1.py
function: my_function_1
class: MyClass1
function: MyClass2.my_method

full_path2/file2.py
variable: my_var
function: MyClass3.my_method

full_path3/file3.py
function: my_function_2
function: my_function_3
function: MyClass4.my_method_1
class: MyClass5
```

Return just the locations.
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
    """Render the filtered Python tree shown by published Agentless.

    Input order is explicit because the published implementation inherits
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
        if not parts[-1].endswith(".py"):
            continue
        if any(part.startswith("test") for part in parts):
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


def render_file_localization_prompt(problem_statement: str, project_tree: str) -> str:
    return FILE_LOCALIZATION_TEMPLATE.format(
        problem_statement=problem_statement,
        structure=project_tree.strip(),
    ).strip()


def render_symbol_localization_prompt(
    problem_statement: str,
    ordered_files: Mapping[str, str],
    *,
    adapter: PythonAdapter | None = None,
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
            compress_assign=compress_assign,
            total_lines=total_lines,
            prefix_lines=prefix_lines,
            suffix_lines=suffix_lines,
        )
        blocks.append(FILE_BLOCK_TEMPLATE.format(file_name=file_name, file_content=skeleton))
    return SYMBOL_LOCALIZATION_TEMPLATE.format(
        problem_statement=problem_statement,
        file_contents="".join(blocks),
    )
