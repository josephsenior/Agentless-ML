"""File operations must survive parsing, Git application and voting."""

import pytest

from agentless_ml.repair import (
    EditApplicationError, EditParseError, apply_search_replace_edits,
    parse_search_replace_edits, build_unified_diff, build_patch_candidate,
)
from agentless_ml.workspace import LocalGitWorkspaceProvider, PatchApplicationStatus
from test_local_workspace import git


def apply(sources, response, **kwargs):
    return apply_search_replace_edits(sources, parse_search_replace_edits(response), **kwargs)


def test_rename_then_edit_and_delete_are_atomic():
    sources = {"old.py": "x = 1\n", "obsolete.py": "gone\n"}
    response = (
        "```python\n### old.py\nRENAME FILE TO pkg/new.py\n### pkg/new.py\n"
        "<<<<<<< SEARCH\nx = 1\n=======\nx = 2\n>>>>>>> REPLACE\n"
        "### obsolete.py\nDELETE FILE\n```"
    )
    repaired = apply(sources, response, existing_paths=sources,
                     allowed_intervals={"old.py": [(1, 1)], "obsolete.py": [(1, 1)]})
    assert repaired.updated_sources == {"pkg/new.py": "x = 2\n"}
    assert repaired.renamed_paths == (("old.py", "pkg/new.py"),)
    assert set(repaired.changed_paths) == {"old.py", "pkg/new.py", "obsolete.py"}
    assert sources == {"old.py": "x = 1\n", "obsolete.py": "gone\n"}
    with pytest.raises(EditApplicationError):
        apply(sources, response + "\n```\n### missing.py\nDELETE FILE\n```", existing_paths=sources)
    assert sources == {"old.py": "x = 1\n", "obsolete.py": "gone\n"}


@pytest.mark.parametrize("destination", ["../escape", "/absolute", ".git/config", 'bad"name', "C:/outside"])
def test_rename_rejects_unsafe_destination(destination):
    with pytest.raises(EditParseError):
        parse_search_replace_edits(f"### old.py\nRENAME FILE TO {destination}")


@pytest.mark.parametrize("destination", ["old.py", "OLD.py", "hidden.py", "folder", "old.py/child"])
def test_rename_never_overwrites_or_collides(destination):
    with pytest.raises(EditApplicationError, match="collides"):
        apply({"old.py": "x\n"}, f"### old.py\nRENAME FILE TO {destination}",
              existing_paths={"old.py", "hidden.py", "folder/file.py"})


@pytest.mark.parametrize("operation", ["DELETE FILE", "RENAME FILE TO new.py"])
def test_whole_file_operation_requires_localized_source(operation):
    with pytest.raises(EditApplicationError, match="authorized"):
        apply({"old.py": "x\n"}, f"### old.py\n{operation}", existing_paths={"old.py"}, allowed_intervals={})
    with pytest.raises(EditApplicationError, match="visible"):
        apply({}, f"### old.py\n{operation}", existing_paths={"old.py"})


def test_emptying_is_not_deleting():
    repaired = apply({"a.py": "x"}, "### a.py\n<<<<<<< SEARCH\nx\n=======\n>>>>>>> REPLACE")
    assert repaired.updated_sources == {"a.py": ""}
    assert "deleted file mode" not in build_unified_diff(repaired.original_sources, repaired.updated_sources)


@pytest.mark.parametrize("mode", ["100644", "100755"])
@pytest.mark.parametrize("content", ["", "x = 1", "x = 1\r\n"])
@pytest.mark.parametrize("operation", ["DELETE FILE", "RENAME FILE TO folder/new.py"])
def test_real_git_application_preserves_content_and_modes(tmp_path, mode, content, operation):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init")
    (repo / "old.py").write_bytes(content.encode())
    git(repo, "add", ".")
    if mode == "100755":
        git(repo, "update-index", "--chmod=+x", "old.py")
    git(repo, "commit", "-m", "base")
    commit = git(repo, "rev-parse", "HEAD").decode().strip()
    provider = LocalGitWorkspaceProvider(repo, commit, tmp_path / "workspaces")
    repaired = apply({"old.py": content}, f"### old.py\n{operation}", existing_paths=provider.paths)
    patch = build_unified_diff(repaired.original_sources, repaired.updated_sources,
                               renamed_paths=repaired.renamed_paths, source_modes=provider.file_modes)
    candidate = build_patch_candidate(candidate_id="operation", raw_response=operation,
        diff=patch, localization_rank=0, sample_index=0,
        original_sources=repaired.original_sources, updated_sources=repaired.updated_sources)
    assert candidate.normalized_diff
    with provider.create() as workspace:
        result = workspace.apply_candidate(candidate)
        assert result.status == PatchApplicationStatus.APPLIED, result.message
        assert not (workspace.path / "old.py").exists()
        if operation.startswith("RENAME"):
            assert (workspace.path / "folder/new.py").read_bytes() == content.encode()
            assert git(workspace.path, "ls-files", "--stage", "folder/new.py").startswith(mode.encode())
    assert (repo / "old.py").read_bytes() == content.encode()


def test_rename_with_changed_contents_applies(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init")
    (repo / "old.py").write_bytes(b"x = 1\n")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "base")
    provider = LocalGitWorkspaceProvider(repo, git(repo, "rev-parse", "HEAD").decode().strip(), tmp_path / "ws")
    patch = build_unified_diff({"old.py": "x = 1\n"}, {"new.py": "x = 2\n"}, renamed_paths=(("old.py", "new.py"),))
    candidate = build_patch_candidate(candidate_id="r", raw_response="r", diff=patch, localization_rank=0, sample_index=0)
    with provider.create() as workspace:
        result = workspace.apply_candidate(candidate)
        assert result.status == PatchApplicationStatus.APPLIED, result.message
        assert (workspace.path / "new.py").read_text() == "x = 2\n"


def test_deleted_and_emptied_files_do_not_vote_together():
    def key(updated):
        return build_patch_candidate(candidate_id="k", raw_response="r",
            diff=build_unified_diff({"old.py": "x = 1\n"}, updated),
            localization_rank=0, sample_index=0,
            original_sources={"old.py": "x = 1\n"}, updated_sources=updated).normalized_diff
    assert key({}) != key({"old.py": ""})
    assert key({"a.py": "x = 1\n"}) != key({"b.py": "x = 1\n"})


def test_empty_file_deletions_keep_path_identity_in_voting():
    def key(path):
        original = {path: ""}
        return build_patch_candidate(candidate_id="empty", raw_response="r",
            diff=build_unified_diff(original, {}), localization_rank=0, sample_index=0,
            original_sources=original, updated_sources={}).normalized_diff
    assert key("a.py") != key("b.py")


@pytest.mark.parametrize("response", [
    "DELETE FILE", "### old.py\nDELETE FILE extra",
    "### old.py\nRENAME FILE", "### old.py\nRENAME FILE TO",
])
def test_malformed_operations_are_rejected(response):
    with pytest.raises(EditParseError):
        parse_search_replace_edits(response)
