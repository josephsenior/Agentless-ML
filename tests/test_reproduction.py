import pytest

from agentless_ml.schemas import ValidationKind
from agentless_ml.validation import PublicTestCommand, ReproductionSpec
from agentless_ml.validation.reproduction import (
    parse_reproduction_source,
    reproduction_file,
)


def spec(path="reproduce.py"):
    return ReproductionSpec(
        path, PublicTestCommand(("python", path), kind=ValidationKind.REPRODUCTION)
    )


@pytest.mark.parametrize(
    "language", ["python", "go", "javascript", "typescript", "rust"]
)
def test_recorded_source_parser(language):
    assert (
        parse_reproduction_source(f"```{language}\nsource\n```", language) == "source\n"
    )


@pytest.mark.parametrize(
    "response",
    ["", "source", "```python\n\n```", "```python\nx\n```\n```python\ny\n```"],
)
def test_invalid_source(response):
    with pytest.raises(ValueError):
        parse_reproduction_source(response, "python")


@pytest.mark.parametrize(
    "path",
    [
        "../a.py",
        "/a.py",
        ".git/config",
        "a/../../x",
        "a\\b",
        "a:stream",
        "a//b",
        "a./b",
    ],
)
def test_invalid_paths(path):
    with pytest.raises(ValueError):
        spec(path)


def test_overlay_cleanup_and_collision(tmp_path):
    with pytest.raises(RuntimeError):
        with reproduction_file(tmp_path, spec(), "test source"):
            assert (tmp_path / "reproduce.py").read_text() == "test source"
            raise RuntimeError("runner failure")
    assert not (tmp_path / "reproduce.py").exists()
    (tmp_path / "reproduce.py").write_text("existing")
    with pytest.raises(ValueError, match="already exists"):
        with reproduction_file(tmp_path, spec(), "replacement"):
            pass
    assert (tmp_path / "reproduce.py").read_text() == "existing"
