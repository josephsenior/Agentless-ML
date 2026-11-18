import importlib
import subprocess
from pathlib import Path

import pytest


def test_census_measures_inputs_and_preserves_unreadable_file_caveat(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).parents[1] / "tools"))
    census = importlib.import_module("survey_source_index_tokens")
    reader = importlib.import_module("inspect_source_index")

    def git(*args):
        return subprocess.run(["git", *args], cwd=tmp_path, capture_output=True,
                              check=True).stdout.decode().strip()

    git("init", "-q")
    git("config", "user.name", "Test")
    git("config", "user.email", "test@example.org")
    (tmp_path / "api.py").write_text("import backend\ndef api():\n    return 123\n")
    (tmp_path / "backend.py").write_text("def backend():\n    return 456\n")
    (tmp_path / "binary.py").write_bytes(b"\x1f\x8b\xff")
    (tmp_path / "test_invalid.py").write_bytes(b"\xff\xfe")
    git("add", ".")
    git("commit", "-qm", "public base")
    commit = git("rev-parse", "HEAD")
    with pytest.raises(ValueError, match="non-UTF-8 source: binary.py"):
        reader.read_pinned_sources(tmp_path, commit, source_policy_only=True)
    result = census.survey_task(tmp_path, commit, "Fix the public API.", graph_budget=100)
    assert result["live_model_calls"] == 0
    assert result["input_coverage"] == "partial-unreadable"
    assert result["files"] == 2
    assert result["source_policy_excluded"] == ["test_invalid.py"]
    assert result["unreadable_source_files"][0]["path"] == "binary.py"
    assert result["bounded_map_tokens"] <= 100
    assert result["index_plus_complete_map_prompt_tokens"] > result["index_prompt_tokens"]
    assert result["index_prompt_tokens"] > result["tree_only_prompt_tokens"]
    assert len(result["inspection_largest_files"]) == 2
    assert result["inspection_bounds_cover_all_indexed_files"] is True
    assert result["inspection_skeleton_tokens_sum_largest_10"] == result["inspection_skeleton_tokens_sum_smallest_10"]
    repeated = census.survey_task(tmp_path, commit, "Fix the public API.", graph_budget=100)
    assert result == repeated
    stats = census.summarize([result])
    assert stats["measured"] == 1 and stats["blocked"] == 0
    assert stats["index_prompt_tokens"]["median"] == result["index_prompt_tokens"]
    report = census.render_report([result])
    assert "partial count" in report
    assert "Largest-10 skeleton payload" in report
