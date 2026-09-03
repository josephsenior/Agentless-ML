import hashlib
import json
import os
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from agentless_ml.repair import build_patch_candidate, build_unified_diff
from agentless_ml.workspace import (
    LocalGitWorkspaceProvider,
    PatchApplicationStatus,
    WorkspaceError,
)


def git(repository: Path, *args: str, data: bytes | None = None) -> bytes:
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("GIT_")}
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
    return subprocess.run(
        [
            "git",
            "-c",
            "core.autocrlf=false",
            "-c",
            "core.hooksPath=" + os.devnull,
            "-c",
            "user.name=Workspace Tests",
            "-c",
            "user.email=tests@example.invalid",
            *args,
        ],
        cwd=repository,
        input=data,
        capture_output=True,
        check=True,
        env=env,
    ).stdout


@pytest.fixture
def source(tmp_path: Path):
    repository = tmp_path / "source repo"
    repository.mkdir()
    git(repository, "init")
    (repository / "a.py").write_bytes(b"value = 1\n")
    (repository / "b.py").write_bytes(b"other = 1\n")
    (repository / ".gitignore").write_bytes(b"ignored.txt\n")
    git(repository, "add", ".")
    git(repository, "commit", "-m", "base")
    commit = git(repository, "rev-parse", "HEAD").decode().strip()
    return repository, commit, tmp_path / "candidate workspaces"


def candidate(value=2):
    return build_patch_candidate(
        candidate_id=f"candidate-{value}",
        raw_response="fixture response",
        diff=build_unified_diff(
            {"a.py": "value = 1\n"}, {"a.py": f"value = {value}\n"}
        ),
        localization_rank=0,
        sample_index=0,
    )


def test_independent_candidates_and_source_are_isolated(source) -> None:
    repository, commit, root = source
    provider = LocalGitWorkspaceProvider(repository, commit, root)
    with provider.create() as first, provider.create() as second:
        assert first.path != second.path
        one = first.apply_candidate(candidate(2))
        two = second.apply_candidate(candidate(3))
        assert one.status is two.status is PatchApplicationStatus.APPLIED
        assert one.changed_paths == ("a.py",)
        assert (first.path / "a.py").read_bytes() == b"value = 2\n"
        assert (second.path / "a.py").read_bytes() == b"value = 3\n"
        assert (repository / "a.py").read_bytes() == b"value = 1\n"
        assert git(repository, "status", "--porcelain") == b""
        assert git(first.path, "rev-parse", "HEAD").decode().strip() == commit
        assert git(first.path, "remote") == b""
    assert not first.path.exists()
    assert not second.path.exists()
    assert list(root.iterdir()) == []


def test_checkout_uses_pinned_commit_not_dirty_source_or_current_head(source) -> None:
    repository, commit, root = source
    (repository / "a.py").write_bytes(b"value = 99\n")
    git(repository, "commit", "-am", "later commit")
    (repository / "a.py").write_bytes(b"dirty user changes\n")
    (repository / "untracked.txt").write_bytes(b"do not copy")
    (repository / "ignored.txt").write_bytes(b"do not copy")
    before = git(repository, "status", "--porcelain", "--ignored")
    with LocalGitWorkspaceProvider(repository, commit, root).create() as workspace:
        assert (workspace.path / "a.py").read_bytes() == b"value = 1\n"
        assert not (workspace.path / "untracked.txt").exists()
        assert not (workspace.path / "ignored.txt").exists()
        manifest = json.loads((workspace.path.parent / "provenance.json").read_text())
        assert manifest["base_commit"] == commit
        assert (
            manifest["base_tree"]
            == git(repository, "rev-parse", commit + "^{tree}").decode().strip()
        )
        assert manifest["backend"] == "local-git-v1"
    assert git(repository, "status", "--porcelain", "--ignored") == before
    assert (repository / "a.py").read_bytes() == b"dirty user changes\n"


@pytest.mark.parametrize("ref", ["HEAD", "main", "123abc", "f" * 40])
def test_invalid_or_unpinned_commit_is_rejected(source, ref) -> None:
    repository, _, root = source
    with pytest.raises(WorkspaceError):
        LocalGitWorkspaceProvider(repository, ref, root)
    assert not root.exists()


def test_workspace_root_cannot_be_inside_source(source) -> None:
    repository, commit, _ = source
    with pytest.raises(WorkspaceError, match="separate"):
        LocalGitWorkspaceProvider(repository, commit, repository / "candidates")


def test_digest_mismatch_and_reuse_are_rejected(source) -> None:
    repository, commit, root = source
    with LocalGitWorkspaceProvider(repository, commit, root).create() as workspace:
        result = workspace.apply_candidate(replace(candidate(), diff_sha256="0" * 64))
        assert result.status is PatchApplicationStatus.PATCH_ERROR
        assert "digest" in result.message
        assert git(workspace.path, "status", "--porcelain") == b""
        with pytest.raises(WorkspaceError, match="one candidate"):
            workspace.apply_candidate(candidate())


@pytest.mark.parametrize("file", ["a.py", "extra.txt", "ignored.txt"])
def test_dirty_workspace_is_rejected_including_ignored_files(source, file) -> None:
    repository, commit, root = source
    with LocalGitWorkspaceProvider(repository, commit, root).create() as workspace:
        (workspace.path / file).write_bytes(b"unexpected content")
        with pytest.raises(WorkspaceError, match="dirty"):
            workspace.apply_candidate(candidate())


def test_unappliable_multifile_patch_does_not_partially_apply(source) -> None:
    repository, commit, root = source
    patch = build_unified_diff(
        {"a.py": "value = 1\n", "b.py": "wrong old content\n"},
        {"a.py": "value = 2\n", "b.py": "other = 2\n"},
    )
    bad = replace(
        candidate(), diff=patch, diff_sha256=hashlib.sha256(patch.encode()).hexdigest()
    )
    with LocalGitWorkspaceProvider(repository, commit, root).create() as workspace:
        assert (
            workspace.apply_candidate(bad).status is PatchApplicationStatus.PATCH_ERROR
        )
        assert git(workspace.path, "status", "--porcelain") == b""
        assert (workspace.path / "a.py").read_bytes() == b"value = 1\n"


@pytest.mark.parametrize(
    "path", ["../outside.py", "/outside.py", "missing.py", ".git/config"]
)
def test_unsafe_or_untracked_patch_paths_are_rejected(source, path) -> None:
    repository, commit, root = source
    patch = build_unified_diff({path: "value = 1\n"}, {path: "value = 2\n"})
    bad = replace(
        candidate(), diff=patch, diff_sha256=hashlib.sha256(patch.encode()).hexdigest()
    )
    with LocalGitWorkspaceProvider(repository, commit, root).create() as workspace:
        assert (
            workspace.apply_candidate(bad).status is PatchApplicationStatus.PATCH_ERROR
        )
        assert git(workspace.path, "status", "--porcelain") == b""


def test_symlink_tree_is_rejected_before_checkout(source) -> None:
    repository, _, root = source
    blob = (
        git(repository, "hash-object", "-w", "--stdin", data=b"../outside")
        .decode()
        .strip()
    )
    git(repository, "update-index", "--add", "--cacheinfo", "120000", blob, "link")
    git(repository, "commit", "-m", "symlink fixture")
    commit = git(repository, "rev-parse", "HEAD").decode().strip()
    with pytest.raises(WorkspaceError, match="symlinks"):
        LocalGitWorkspaceProvider(repository, commit, root)
    assert not root.exists()


def test_cleanup_on_exception_and_closed_workspace_rejection(source) -> None:
    repository, commit, root = source
    with (
        pytest.raises(RuntimeError, match="caller failure"),
        LocalGitWorkspaceProvider(repository, commit, root).create() as workspace,
    ):
        raise RuntimeError("caller failure")
    assert list(root.iterdir()) == []
    workspace.close()
    with pytest.raises(WorkspaceError, match="closed"):
        workspace.apply_candidate(candidate())


def test_git_patch_timeout_is_not_a_test_failure(source, monkeypatch) -> None:
    import agentless_ml.workspace.local_git as module

    repository, commit, root = source
    with LocalGitWorkspaceProvider(repository, commit, root).create() as workspace:
        original = module._git

        def timeout_apply(cwd, *args, **kwargs):
            if args[0] == "apply":
                raise subprocess.TimeoutExpired("git apply", 1)
            return original(cwd, *args, **kwargs)

        monkeypatch.setattr(module, "_git", timeout_apply)
        result = workspace.apply_candidate(candidate())
        assert result.status is PatchApplicationStatus.TIMEOUT


def test_git_environment_overrides_and_template_hooks_are_not_inherited(
    source, monkeypatch
) -> None:
    repository, commit, root = source
    template = root.parent / "unwanted-template"
    hooks = template / "hooks"
    hooks.mkdir(parents=True)
    hook = hooks / "post-checkout"
    hook.write_text("#!/bin/sh\nprintf injected > hook-ran.txt\n", encoding="utf-8")
    hook.chmod(0o755)
    monkeypatch.setenv("GIT_TEMPLATE_DIR", str(template))
    monkeypatch.setenv("GIT_WORK_TREE", str(repository))
    monkeypatch.setenv("GIT_INDEX_FILE", str(repository / "bad-index"))
    with LocalGitWorkspaceProvider(repository, commit, root).create() as workspace:
        assert not (workspace.path / "hook-ran.txt").exists()
        assert (
            workspace.apply_candidate(candidate()).status
            is PatchApplicationStatus.APPLIED
        )
    assert not (repository / "bad-index").exists()
    assert (repository / "a.py").read_bytes() == b"value = 1\n"


def test_cleanup_refuses_changed_ownership_marker(source) -> None:
    repository, commit, root = source
    workspace = LocalGitWorkspaceProvider(repository, commit, root).create()
    marker = workspace.path.parent / ".owner"
    token = marker.read_text(encoding="ascii")
    try:
        marker.write_text("not-owned", encoding="ascii")
        with pytest.raises(WorkspaceError, match="ownership"):
            workspace.close()
        assert workspace.path.exists()
    finally:
        marker.write_text(token, encoding="ascii")
        workspace.close()


def test_failed_clone_cleans_only_its_new_directory(source, monkeypatch) -> None:
    import agentless_ml.workspace.local_git as module

    repository, commit, root = source
    provider = LocalGitWorkspaceProvider(repository, commit, root)
    root.mkdir()
    sentinel = root / "caller-owned.txt"
    sentinel.write_text("preserve me", encoding="utf-8")
    original = module._git

    def failed_clone(cwd, *args, **kwargs):
        if args[0] == "clone":
            raise OSError("simulated clone failure")
        return original(cwd, *args, **kwargs)

    monkeypatch.setattr(module, "_git", failed_clone)
    with pytest.raises(WorkspaceError):
        provider.create()
    assert list(root.iterdir()) == [sentinel]
    assert sentinel.read_text() == "preserve me"


@pytest.mark.parametrize(
    "patch",
    [
        "--- a/a.py\n+++ /dev/null\n@@ -1 +0,0 @@\n-value = 1\n",
        "diff --git a/a.py b/a.py\nold mode 100644\nnew mode 120000\n",
        "diff --git a/a.py b/a.py\nGIT binary patch\nliteral 1\nA\n",
        "not a patch at all\n",
    ],
)
def test_unsupported_patch_operations_are_not_applied(source, patch) -> None:
    repository, commit, root = source
    bad = replace(
        candidate(), diff=patch, diff_sha256=hashlib.sha256(patch.encode()).hexdigest()
    )
    with LocalGitWorkspaceProvider(repository, commit, root).create() as workspace:
        result = workspace.apply_candidate(bad)
        assert result.status is PatchApplicationStatus.PATCH_ERROR
        assert (workspace.path / "a.py").read_bytes() == b"value = 1\n"


def test_fatal_git_apply_error_is_classified_as_infrastructure(
    source, monkeypatch
) -> None:
    import agentless_ml.workspace.local_git as module

    repository, commit, root = source
    with LocalGitWorkspaceProvider(repository, commit, root).create() as workspace:
        original = module._git

        def lock_failure(cwd, *args, **kwargs):
            if args[0] == "apply" and "--index" in args:
                return subprocess.CompletedProcess(
                    args, 128, b"", b"fatal: cannot lock index"
                )
            return original(cwd, *args, **kwargs)

        monkeypatch.setattr(module, "_git", lock_failure)
        assert (
            workspace.apply_candidate(candidate()).status
            is PatchApplicationStatus.HARNESS_ERROR
        )
