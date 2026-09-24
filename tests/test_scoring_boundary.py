"""Only the scorer may reach held-out material, and nothing in the workflow uses it.

The scorer reads each task's tests/ and solution/. If a workflow module could
import it, held-out answers would be one function call away from a prompt or a
selection decision; this test fails the moment such an import appears.
"""

import ast
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1] / "src" / "agentless_ml"


def _imports(path: Path) -> set[str]:
    names = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_no_module_outside_scoring_imports_the_scorer():
    offenders = [
        str(path.relative_to(PACKAGE))
        for path in PACKAGE.rglob("*.py")
        if "scoring" not in path.relative_to(PACKAGE).parts
        and any(name.startswith("agentless_ml.scoring") for name in _imports(path))
    ]
    assert offenders == []


def test_the_scorer_depends_on_no_workflow_stage():
    stages = ("localization", "repair", "validation", "workflow", "workspace")
    for path in (PACKAGE / "scoring").rglob("*.py"):
        imported = _imports(path)
        assert not any(
            name.startswith(f"agentless_ml.{stage}") for stage in stages for name in imported
        ), path.name
