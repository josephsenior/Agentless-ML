import pytest

from agentless_ml.schemas import FileNode, SymbolNode


def test_accepts_nested_language_neutral_structure() -> None:
    method = SymbolNode("method", "run", "Worker.run", "run(self)", 4, 8)
    parent = SymbolNode("class", "Worker", "Worker", "class Worker", 2, 10, (method,))
    file_node = FileNode("src/worker.py", "python", 12, (parent,))
    assert file_node.symbols[0].children[0].qualified_name == "Worker.run"


def test_rejects_child_outside_parent_span() -> None:
    child = SymbolNode("function", "late", "Container.late", "late()", 9, 12)
    with pytest.raises(ValueError, match="outside its parent"):
        SymbolNode("class", "Container", "Container", "class Container", 1, 10, (child,))


@pytest.mark.parametrize("path", ["../secret.py", "/etc/passwd", "src/../../secret.py"])
def test_rejects_unsafe_repository_path(path: str) -> None:
    with pytest.raises(ValueError, match="repository-relative"):
        FileNode(path, "python", 1)


def test_rejects_symbol_beyond_file() -> None:
    symbol = SymbolNode("function", "f", "f", "f()", 1, 3)
    with pytest.raises(ValueError, match="exceeds file line count"):
        FileNode("f.py", "python", 2, (symbol,))
