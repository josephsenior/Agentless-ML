# Isolated candidate workspaces

`LocalGitWorkspaceProvider` gives each candidate an independent Git checkout at
a full, pinned commit ID. The source repository is only read: its current branch,
index, uncommitted changes, untracked files, and ignored files are left alone.
Each clone has its own objects and index, with no hardlinks or borrowed objects.

This is **repository-state isolation, not a security sandbox**. Do not run model
patches or repository test commands on the host through this backend. Container
execution, resource limits, and hidden-verifier isolation are separate future
work. A clone contains repository history; the caller must supply a trusted,
agent-visible repository with no verifier material in that history.

## Lifecycle

1. Validate the local repository and full base commit. Reject unsupported tree
   entries before checkout (symlinks, submodules, unsafe or case-colliding paths).
2. Allocate a uniquely named directory under an explicitly configured workspace
   root, separate from the source repository.
3. Clone without hardlinks or inherited templates and check out the pinned
   commit in detached mode. Remove the clone's remote.
4. Record the base commit, tree ID, Git version, workspace ID, backend version,
   source path, and creation time in `provenance.json` outside the checkout.
5. Accept one candidate attempt. Verify its patch digest, require a clean tree,
   reject unsupported targets, and run `git apply --check --index` before applying.
6. Return an application result and changed paths. Application is not a passing
   test result; it proves only that Git accepted the patch on the expected base.
7. Close the handle to delete only its owned directory. Create another workspace
   for another attempt; never reset or reuse a mutated candidate checkout.

Git subprocesses use argument lists rather than shell command strings. Inherited
Git directory/config overrides, global filters, fsmonitor, and executable hooks
are disabled for provider operations. No remote clone, dependency installation,
or test command is performed.

## Example

```python
from pathlib import Path
from agentless_ml.workspace import LocalGitWorkspaceProvider, PatchApplicationStatus

provider = LocalGitWorkspaceProvider(
    source_repository=Path("/research/repositories/example"),
    base_commit=task.base_commit,  # a full immutable commit ID
    workspace_root=Path("/research/candidate-workspaces"),
)

with provider.create() as workspace:
    result = workspace.apply_candidate(candidate)
    if result.status is PatchApplicationStatus.APPLIED:
        # Archive provenance/result here. Public tests are not executed yet.
        print(workspace.provenance.base_commit, result.changed_paths)
```

Keep any artifacts needed after cleanup outside the owned directory. The caller
receives frozen provenance and application records suitable for serialization.

## Current limits

The backend accepts patches to existing regular text files only. File creation,
deletion, rename/copy, executable-mode changes, symlink changes, binary patches,
and submodules are rejected explicitly. These are initial capability limits,
not evidence that such tasks should be excluded from the eventual study.

Patch errors, command timeouts, and infrastructure errors have distinct outcomes.
After a timeout or failed operation, discard the workspace; do not infer that its
contents are usable. Dirty or reused handles raise `WorkspaceError`.

Integration tests exercise independent candidates, a dirty source at a different
HEAD, patch failure atomicity, digest mismatches, path restrictions, environment
overrides, cleanup ownership, and missing-final-newline/CRLF patch round trips.
