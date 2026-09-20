"""Sealing a clone must remove the fix that lives after the base commit."""

import subprocess

import pytest

from agentless_ml.workspace import (
    LocalGitWorkspaceProvider,
    WorkspaceError,
    prepare_sealed_repository,
    verify_sealed_repository,
)

FIX = "def add(a, b):\n    return a + b\n"
BUG = "def add(a, b):\n    return a - b\n"


def git(cwd, *args):
    result = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


@pytest.fixture
def upstream(tmp_path):
    """A repository whose later history contains the answer.

    base commit  calculator.py has the bug           <- the only commit a task
    fix commit   calculator.py has the real fix         may see
    v2.0         a tag pointing at the fix commit
    side         a branch pointing at the fix commit
    """
    root = tmp_path / "upstream"
    root.mkdir()
    git(root, "init", "--initial-branch=main", "--quiet")
    git(root, "config", "user.email", "t@example.com")
    git(root, "config", "user.name", "Test")
    (root / "calculator.py").write_text(BUG)
    git(root, "add", "calculator.py")
    git(root, "commit", "--quiet", "-m", "add calculator")
    base = git(root, "rev-parse", "HEAD")
    (root / "calculator.py").write_text(FIX)
    git(root, "commit", "--quiet", "-am", "fix the subtraction bug")
    fix = git(root, "rev-parse", "HEAD")
    git(root, "tag", "v2.0")
    git(root, "branch", "side")
    return root, base, fix


def test_history_after_the_base_commit_is_gone(upstream, tmp_path):
    root, base, fix = upstream
    sealed = prepare_sealed_repository(str(root), base, tmp_path / "sealed")

    assert sealed.base_commit == base
    assert git(sealed.path, "rev-parse", "HEAD") == base
    # One commit, one branch, no tags, no remotes: nothing points past the base.
    assert git(sealed.path, "rev-list", "--all", "--count") == "1"
    assert git(sealed.path, "tag") == ""
    assert git(sealed.path, "remote") == ""
    # The fix commit is not merely unreferenced, it is not in the repository.
    missing = subprocess.run(
        ["git", "cat-file", "-e", fix], cwd=sealed.path, capture_output=True
    )
    assert missing.returncode != 0
    # And its content cannot be recovered from the object database either.
    objects = subprocess.run(
        ["git", "cat-file", "--batch-all-objects", "--batch"],
        cwd=sealed.path,
        capture_output=True,
    )
    assert b"a + b" not in objects.stdout
    assert b"a - b" in objects.stdout


def test_head_is_a_branch_not_a_detached_checkout(upstream, tmp_path):
    root, base, _ = upstream
    sealed = prepare_sealed_repository(str(root), base, tmp_path / "sealed")
    assert sealed.branch == "main"
    assert git(sealed.path, "symbolic-ref", "--short", "HEAD") == "main"


def test_a_tag_inside_the_base_commit_history_is_kept(upstream, tmp_path):
    root, base, _ = upstream
    git(root, "tag", "v1.0", base)
    sealed = prepare_sealed_repository(str(root), base, tmp_path / "sealed")
    assert git(sealed.path, "tag") == "v1.0"


def test_the_sealed_clone_provisions_candidate_workspaces(upstream, tmp_path):
    root, base, _ = upstream
    sealed = prepare_sealed_repository(str(root), base, tmp_path / "sealed")
    provider = LocalGitWorkspaceProvider(sealed.path, base, tmp_path / "workspaces")
    with provider.create() as workspace:
        assert (workspace.path / "calculator.py").read_text() == BUG


def test_verification_rejects_a_repository_that_kept_later_commits(upstream, tmp_path):
    root, base, _ = upstream
    unsealed = tmp_path / "unsealed"
    git(tmp_path, "clone", "--quiet", str(root), str(unsealed))
    # Checking out the base commit is not sealing: the fix is still one
    # `git log --all` away, which is exactly what verification must catch.
    git(unsealed, "checkout", "--quiet", base)
    with pytest.raises(WorkspaceError, match="outside the base commit"):
        verify_sealed_repository(unsealed, base)


def test_a_failed_preparation_leaves_no_half_clone_behind(upstream, tmp_path):
    root, _, _ = upstream
    absent = "0" * 40
    destination = tmp_path / "sealed"
    with pytest.raises(WorkspaceError):
        prepare_sealed_repository(str(root), absent, destination)
    # A leftover directory would look prepared to the next run, which would
    # then hand the workflow a clone that still holds the later history.
    assert not destination.exists()


def test_inputs_must_be_a_full_commit_and_an_unused_destination(upstream, tmp_path):
    root, base, _ = upstream
    with pytest.raises(WorkspaceError, match="full lowercase Git commit"):
        prepare_sealed_repository(str(root), base[:8], tmp_path / "a")
    with pytest.raises(WorkspaceError, match="HTTPS URL or an existing local"):
        prepare_sealed_repository("git@github.com:x/y.git", base, tmp_path / "b")
    (tmp_path / "taken").mkdir()
    with pytest.raises(WorkspaceError, match="already exists"):
        prepare_sealed_repository(str(root), base, tmp_path / "taken")
