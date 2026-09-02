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
