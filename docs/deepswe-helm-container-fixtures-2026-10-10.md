# Helm: container-only fixture links

Both Helm tasks need four public fixture links that the normal snapshot policy
correctly rejects: two point to `/dev/null`, one to `/non/existing/file`, and one
contains a literal Windows path. Replacing them with ordinary files would change
what the tests exercise. Allowing arbitrary absolute links would be too broad.

The scoped runner instead checks the exact task, base commit, original image ID
and complete Git symlink map. It verifies the host checkout's fixture target
text, but leaves the four special links out of the archive. After extraction it
creates them inside the disposable Linux container, before any public command.
The fifth, ordinary relative link still goes through the existing safe-link
checks. No host symlinks are created or followed.

Setup refuses to overwrite an existing destination, traverse a symlink parent,
or proceed if either supposedly missing target exists. It also checks that the
container's `/dev/null` is the native character device, major 1, minor 3. The
Windows-looking target stays literal; it is not translated to a host path.
Successful setup is recorded in `execution.json`.

This policy applies only to the two pinned tasks at commit
`42f78ba60edf531d5161e00d9819a7c34d976343`, using their original images.
Explicit image substitutions do not receive it. General snapshot rejection of
absolute, escaping, cyclic, altered and untracked links remains in place.

## Short diagnostics, not baselines

`tools/check_helm_fixture_links.py` exercised both pinned images with fresh
candidate workspaces. Both exited 0:

| Task | Elapsed, including setup |
|---|---:|
| `helm-array-merge-strategies` | 36.89 seconds |
| `helm-unified-manifest-stream` | 19.29 seconds |

Each diagnostic checked all five links. The two device links resolved to native
`/dev/null`; the invalid and Windows-looking links remained dangling; the safe
relative link resolved to candidate fixture bytes. Copying each link's metadata
preserved its exact target text. No Git metadata entered the container workspace.
This is a small Python behavior check, not execution of Helm's Go copy helper or
its public tests.

Observed protections stayed unchanged: no network, read-only root, no host
binds, no added capabilities, no-new-privileges, 8 GiB RAM with no extra swap,
two CPUs, 2,048 PIDs and a 4 GiB `/tmp` tmpfs. No image was built or modified.
No test source, public schedule, corpus pin or held-out scorer changed.

Host checks passed: 101 focused tests and 174 workflow/report/selection tests.
Seventeen checks were skipped because they require opt-in Docker integration or
Windows native-symlink privileges. The two short pinned-image diagnostics above
ran separately and passed.

At this diagnostic checkpoint, readiness remained **106/113**. Neither Helm baseline was run in this step, and
the official survey was not refreshed. The next step is an unchanged public
baseline for each task using this setup, followed by its official survey update.

The later approved [unchanged public baselines](deepswe-helm-public-baselines-2026-10-10.md)
have now completed, bringing official readiness to 108/113. The results above
remain diagnostic-only records of the earlier checkpoint.

Pinned image IDs, artifact locations and hashes are recorded in
[`helm_container_fixtures_2026_10_10.json`](../experiments/deepswe/helm_container_fixtures_2026_10_10.json).
