import pytest

from agentless_ml.adapters.languages import get_language_adapter
from agentless_ml.localization import construct_selected_context
from agentless_ml.localization.edit import (
    parse_edit_locations,
    render_edit_localization_prompt,
)


@pytest.mark.parametrize(
    "language,path,source,location,line",
    [
        ("python", "a.py", "def add(a, b):\n    return a - b\n", "function: add", 2),
        (
            "go",
            "a.go",
            "package p\nfunc Add(a,b int) int { return a-b }\n",
            "function: Add",
            2,
        ),
        (
            "javascript",
            "a.js",
            "function add(a,b) { return a-b; }\n",
            "function: add",
            1,
        ),
        (
            "typescript",
            "a.ts",
            "function add(a:number,b:number):number { return a-b; }\n",
            "function: add",
            1,
        ),
        ("rust", "a.rs", "fn add(a:i32,b:i32)->i32 { a-b }\n", "function: add", 1),
    ],
)
def test_edit_context_across_languages(language, path, source, location, line):
    node = get_language_adapter(language).parse_file(path, source)
    context, intervals = construct_selected_context(
        {path: [location]}, {path: node}, {path: source}, no_line_number=False
    )
    assert f"{line}|" in context
    assert context in render_edit_localization_prompt("fix addition", context)
    locations = parse_edit_locations(f"```\n{path}\nline: {line}\n```", intervals)
    repair_context, _ = construct_selected_context(
        locations, {path: node}, {path: source}
    )
    assert "a" in repair_context and f"{line}|" not in repair_context


@pytest.mark.parametrize(
    "body",
    [
        "a.py\nline: 0",
        "a.py\nline: 30",
        "b.py\nline: 2",
        "line: 2",
        "a.py\nfunction: add",
        "a.py\nline: 2 extra",
        "a.py\nline: -1",
        "a.py",
    ],
)
def test_reject_unseen_or_invalid_edit_locations(body):
    with pytest.raises(ValueError):
        parse_edit_locations(f"```\n{body}\n```", {"a.py": [(1, 3)]})


def test_multiple_files_and_duplicate_lines():
    assert parse_edit_locations(
        "```\na.py\nline: 2\nline: 2\nb.rs\nline: 5\n```",
        {"a.py": [(1, 3)], "b.rs": [(5, 6)]},
    ) == {"a.py": ["line: 2"], "b.rs": ["line: 5"]}


def test_edit_lines_narrow_large_symbol_context():
    source = "def long_function():\n" + "    pass\n" * 80
    node = get_language_adapter("python").parse_file("a.py", source)
    _, coarse = construct_selected_context(
        {"a.py": ["function: long_function"]}, {"a.py": node}, {"a.py": source}
    )
    locations = parse_edit_locations("```\na.py\nline: 40\n```", coarse)
    context, fine = construct_selected_context(
        locations, {"a.py": node}, {"a.py": source}
    )
    assert fine["a.py"] == [(30, 50)]
    assert len(context.splitlines()) < 30
