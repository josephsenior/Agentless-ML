# Keeping Git links intact in Linux snapshots

The Docker runner now preserves unchanged, checkout-contained Git symlinks.
This closes the Windows/Linux gap identified in the
[repository review](deepswe-repository-review-2026-10-04.md). It does not let
the model create or edit symlinks, and it does not initialize submodules.

## Why ordinary copying was wrong

On this Windows host, Git checked out the relevant symlinks as ordinary files
containing their targets. Copying one into Docker kept it as text. Following
the target and copying its contents would be wrong too: a directory link, a
chain or an intentionally broken link is not interchangeable with a file.

The snapshot therefore reads the link's path and target from the candidate
checkout's unchanged `HEAD` tree. It checks that the host representation still
matches that target, then writes a tar symlink entry. Native host links are
checked with `readlink`, not opened; Windows placeholders are read as ordinary
files. Ordinary candidate file edits still come from the working tree, not
the base commit. A link consequently reaches the edited candidate file inside
Linux.

Git's `100755` mode also supplies executable permissions that Windows may not
retain. This matters when a link points to a tracked script. Git history is
still excluded from the archive.

## The allowed boundary

Internal relative file and directory links, finite chains and internal dangling
links are supported. A target may use `..` only when its resolved path stays
inside the checkout. Resolution applies symlinks before processing subsequent
parent components; simply normalizing the target string would get that wrong.

The snapshot refuses:

- Absolute, drive-style or backslash targets.
- Paths escaping the checkout, directly or through a chain.
- Links into Git metadata, cycles and chains exceeding 40 expansions.
- Changed, missing or unexpectedly typed tracked links.
- Untracked host symlinks, junctions and other special filesystem entries.

Ordinary files and directories are archived first, and link entries last.
Extraction therefore never writes archived files through a previously created
link. Link directories are not traversed on the host. No host paths, Git
history, Docker socket or credentials are mounted into the test container.

The two Helm tasks remain outside this initial policy because their fixtures
include `/dev/null` and other absolute targets. We did not delete those fixtures
or claim that their behavior was preserved.

## Verification

[Snapshot tests](../tests/test_git_snapshot_links.py) cover Windows placeholders,
directory links, chains, dangling links, candidate content, executable modes,
changed targets, escapes and Git-history access.

An opt-in check extracted a controlled candidate in an existing pinned Linux
image. Reads through both a chain and a directory link returned the edited
candidate's contents; an executable link ran its script, and a dangling link
remained dangling. `.git` was absent.

Windows could not create native symlinks without additional privileges. Instead
of treating those checks as verified, another opt-in check ran the snapshot
tests inside an isolated existing Python image. The native-link checks passed
there, including refusing an untracked host link. The inner container had no
Docker socket and skipped its own Docker checks, avoiding recursive launches.

Both checks can be repeated using already-installed image IDs:

```powershell
$env:AGENTLESS_SNAPSHOT_DOCKER_IMAGE = '<trusted Linux image with sh and tar>'
$env:AGENTLESS_NATIVE_SNAPSHOT_IMAGE = '<trusted Linux image with Python, Git and pytest>'
.\.venv\Scripts\python.exe -m pytest tests/test_git_snapshot_links.py -q
```

The public baseline for `python-statemachine-state-data-scoping`, previously
rejected as unsupported, now reports **1,404 passes and 187 skips** in its pinned
image. It ran the existing full pytest schedule, without test exclusions or
model calls. This is a baseline eligibility check, not a task-solving result.

## What this does not prove

Not every previously unsupported task is ready. Each still needs a public
baseline in its own image. Submodule-only tasks require a separate check of
whether their schedules need the uninitialized contents. The three missing
repositories still need fresh sealed preparation.

Wazero's first unchanged full Go schedule exceeded the 300-second smoke limit.
The follow-up allows 900 seconds without selecting fewer packages. Its outcome
is recorded separately from the link implementation, so a slow suite or report
converter cannot be mistaken for a symlink failure.
