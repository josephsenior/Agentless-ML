import hashlib

from agentless_ml.repair import build_repair_prompt


def test_python_repair_prompt_preserves_published_diff_format() -> None:
    prompt = build_repair_prompt(
        "A byte method is converted incorrectly.",
        "### requests/sessions.py\nmethod = builtin_str(method)",
    )
    assert prompt.startswith("We are currently solving the following issue")
    assert "--- BEGIN ISSUE ---\nA byte method is converted incorrectly." in prompt
    assert "<<<<<<< SEARCH" in prompt
    assert "### requests/sessions.py\nmethod = builtin_str(method)" in prompt
    assert prompt.endswith(
        "Wrap the *SEARCH/REPLACE* edit in blocks ```python...```."
    )


def test_repair_prompt_changes_only_output_fence_vocabulary_for_language() -> None:
    prompt = build_repair_prompt("Fix it", "### main.go\nfunc main() {}", language="go")
    assert "```go" in prompt
    assert "```python" not in prompt


def test_python_prompt_matches_pinned_v1_5_golden_checksum() -> None:
    prompt = build_repair_prompt("Fix it", "### a.py\nold")
    assert len(prompt) == 1143
    assert hashlib.sha256(prompt.encode()).hexdigest() == (
        "29d228544ec722ee5e6b86c47ea8de1da740528181082c63f2f5ae30136242b9"
    )
