import pytest

from agentless_ml.repair import (
    EditApplicationError,
    EditParseError,
    apply_search_replace_edits,
    parse_search_replace_edits,
)


def test_parse_and_atomically_apply_multifile_edits() -> None:
    response = f"""The two call sites need the same conversion.
```python
### pkg/first.py
{'<' * 7} SEARCH
value = str(value)
{'=' * 7}
value = decode(value)
{'>' * 7} REPLACE
### pkg/second.py
{'<' * 7} SEARCH
return str(method)
{'=' * 7}
return decode(method)
{'>' * 7} REPLACE
```
"""
    edits = parse_search_replace_edits(response)
    sources = {
        "pkg/first.py": "value = str(value)\n",
        "pkg/second.py": "def convert(method):\n    return str(method)\n",
    }
    applied = apply_search_replace_edits(sources, edits)
    assert applied.changed_paths == ("pkg/first.py", "pkg/second.py")
    assert applied.updated_sources["pkg/first.py"] == "value = decode(value)\n"
    assert "return decode(method)" in applied.updated_sources["pkg/second.py"]
    assert sources["pkg/first.py"] == "value = str(value)\n"


def test_repeated_edit_is_deduplicated() -> None:
    block = f"""```python
### a.py
{'<' * 7} SEARCH
old
{'=' * 7}
new
{'>' * 7} REPLACE
{'<' * 7} SEARCH
old
{'=' * 7}
new
{'>' * 7} REPLACE
```"""
    assert len(parse_search_replace_edits(block)) == 1


@pytest.mark.parametrize("path", ["../secret", "/etc/passwd", "C:\\secret.py"])
def test_parser_rejects_paths_outside_repository(path: str) -> None:
    response = f"""```python
### {path}
{'<' * 7} SEARCH
old
{'=' * 7}
new
{'>' * 7} REPLACE
```"""
    with pytest.raises(EditParseError, match="unsafe"):
        parse_search_replace_edits(response)


def test_application_rejects_ambiguous_search_without_mutating_input() -> None:
    sources = {"a.py": "same\nsame\n"}
    edits = parse_search_replace_edits(
        f"""### a.py
{'<' * 7} SEARCH
same
{'=' * 7}
changed
{'>' * 7} REPLACE"""
    )
    with pytest.raises(EditApplicationError, match="ambiguous"):
        apply_search_replace_edits(sources, edits)
    assert sources == {"a.py": "same\nsame\n"}


def test_localization_intervals_disambiguate_search() -> None:
    sources = {"a.py": "same\nother\nsame\n"}
    edits = parse_search_replace_edits(
        f"""### a.py
{'<' * 7} SEARCH
same
{'=' * 7}
changed
{'>' * 7} REPLACE"""
    )
    applied = apply_search_replace_edits(
        sources, edits, allowed_intervals={"a.py": [(3, 3)]}
    )
    assert applied.updated_sources["a.py"] == "same\nother\nchanged\n"


def test_interval_policy_rejects_an_unlocalized_file() -> None:
    edits = parse_search_replace_edits(
        f"""### a.py
{'<' * 7} SEARCH
old
{'=' * 7}
new
{'>' * 7} REPLACE"""
    )
    with pytest.raises(EditApplicationError, match="no authorized interval"):
        apply_search_replace_edits(
            {"a.py": "old\n"}, edits, allowed_intervals={"other.py": [(1, 1)]}
        )


def _create(path: str, content: str) -> str:
    return f"""### {path}
{'<' * 7} SEARCH
{'=' * 7}
{content}
{'>' * 7} REPLACE"""


def test_empty_search_creates_a_new_file_outside_every_interval() -> None:
    edits = parse_search_replace_edits(
        _create("pkg/rule.go", "package pkg\n\nfunc Rule() {}")
        + f"""
### pkg/rule.go
{'<' * 7} SEARCH
func Rule() {{}}
{'=' * 7}
func Rule() int {{ return 1 }}
{'>' * 7} REPLACE"""
    )
    applied = apply_search_replace_edits(
        {"a.go": "package a\n"},
        edits,
        allowed_intervals={"a.go": [(1, 1)]},
        existing_paths={"a.go", "b.go"},
    )
    assert applied.created_paths == ("pkg/rule.go",)
    assert applied.changed_paths == ("pkg/rule.go",)
    assert "pkg/rule.go" not in applied.original_sources
    assert applied.updated_sources["pkg/rule.go"] == (
        "package pkg\n\nfunc Rule() int { return 1 }\n"
    )


def test_an_empty_new_file_can_be_created() -> None:
    edits = parse_search_replace_edits(_create("pkg/__init__.py", ""))
    applied = apply_search_replace_edits({}, edits, existing_paths=set())
    assert applied.updated_sources == {"pkg/__init__.py": ""}


@pytest.mark.parametrize(
    ("sources", "existing", "path", "message"),
    [
        ({"a.py": "x\n"}, {"a.py"}, "a.py", "must not be empty for an existing file"),
        ({}, {"hidden.py"}, "hidden.py", "already exists"),
        ({}, {"Pkg/Mod.py"}, "pkg/mod.py", "already exists"),
        ({}, None, "new.py", "requires the repository's tracked paths"),
    ],
)
def test_creation_never_overwrites_or_guesses(sources, existing, path, message) -> None:
    edits = parse_search_replace_edits(_create(path, "content"))
    with pytest.raises(EditApplicationError, match=message):
        apply_search_replace_edits(sources, edits, existing_paths=existing)


def test_a_file_cannot_be_created_twice_in_one_response() -> None:
    edits = parse_search_replace_edits(
        _create("new.py", "one") + "\n" + _create("new.py", "two")
    )
    with pytest.raises(EditApplicationError, match="created more than once"):
        apply_search_replace_edits({}, edits, existing_paths=set())
