"""Deterministic Agentless-compatible localization context rendering."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

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
        label = parser.language
        if parser.language in {"javascript", "typescript"}:
            label = (
                "javascript"
                if file_name.endswith((".js", ".mjs", ".cjs"))
                else "typescript"
            )
            if file_name.endswith((".jsx", ".tsx")):
                label = file_name.rsplit(".", 1)[1]
        template = FILE_BLOCK_TEMPLATE.replace("```python", "```" + label)
        blocks.append(template.format(file_name=file_name, file_content=skeleton))
    template = SYMBOL_LOCALIZATION_TEMPLATE
    if parser.language == "go":
        template = GO_SYMBOL_LOCALIZATION_TEMPLATE
    elif parser.language == "rust":
        template = RUST_SYMBOL_LOCALIZATION_TEMPLATE
    elif parser.language in {"javascript", "typescript"}:
        template = JS_SYMBOL_LOCALIZATION_TEMPLATE.replace(
            "file.js", "file" + parser.extension
        )
    return template.format(
        problem_statement=problem_statement,
        file_contents="".join(blocks),
    )


RUST_SYMBOL_LOCALIZATION_TEMPLATE = """
Identify Rust declarations that need inspection or editing from the issue and skeletons.
Use source-spelled names with :: separators. Inherent methods use Counter::add;
trait implementations use <Counter as Reset>::reset. Include generic arguments
as written in the impl type. Inline modules add their name as a prefix.
A struct does not include its separate impl blocks. Ambiguous names need qualification
or an exact line location. Macro-generated declarations are not expanded.

### GitHub Problem Description ###
{problem_statement}

### Skeleton of Relevant Files ###
{file_contents}

Return locations in an unlabelled fenced block with repository-relative paths:
```
src/lib.rs
function: add
method: Counter::add
type: Counter
trait: Reset
impl: <Counter as Reset>
module: helpers
constant: LIMIT
```
Use line: N for an exact source line.
"""


GO_SYMBOL_LOCALIZATION_TEMPLATE = """
Please look through the GitHub Problem Description and the Skeleton of Relevant Files.
Identify the functions, methods, types, package variables or constants that need inspection or editing.
Use receiver-qualified names for methods, such as Counter.Add. A type declaration
does not include its separately declared methods; list those methods explicitly.

### GitHub Problem Description ###
{problem_statement}

### Skeleton of Relevant Files ###
{file_contents}

Return just the locations in an unlabelled fenced block, using repository-relative paths:
```
path/file.go
function: Add
method: Counter.Add
type: Counter
variable: DefaultLimit
constant: MaxSize
```
You may also use line: N for an exact source line.
"""


JS_SYMBOL_LOCALIZATION_TEMPLATE = """
Please look through the GitHub Problem Description and the Skeleton of Relevant Files.
Identify functions, bound arrow functions, classes, methods, fields, variables or
types that need inspection or editing. Use owner-qualified names for methods and
fields. A class includes its declared members; list either the class or the members
you need. Use default for an anonymous default export and the declared name for a
named default export. Static CommonJS assignments use names such as exports.add.

### GitHub Problem Description ###
{problem_statement}

### Skeleton of Relevant Files ###
{file_contents}

Return just the locations in an unlabelled fenced block with repository-relative paths:
```
path/file.js
function: add
class: Counter
method: Counter.add
field: Counter.value
variable: settings
type: Options
```
Use line: N for an exact source line, including ambiguous or unnamed constructs.
"""
