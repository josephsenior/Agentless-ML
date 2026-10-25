# Shared container rehearsal, 25 October 2026

The actual Agentless Docker runner and Pier 0.3.1 Docker environment matched in
a controlled rehearsal using Actionlint's pinned image as their common parent.
Grinta's core runtime and Python/Go parser assets were installed beforehand.
An authored source fixture exercised native edits and one public unit test.
No model calls or benchmark suites ran, and the 113-task readiness count stayed
unchanged. [Saved evidence](../../experiments/deepswe/shared_container_rehearsal_2026_10_25.json).

## What matched

Both containers used the same prepared image, root user and `/tmp` working
directory. Source files matched in bytes and permissions. Their observed Docker
settings were identical:

| Setting | Observed in both |
| --- | --- |
| Memory and swap ceiling | 8 GiB / 8 GiB |
| CPU and PID limits | 2 CPUs / 2,048 PIDs |
| Scratch | 4-GiB executable tmpfs at `/tmp` |
| Network | `none` |
| Root filesystem | Read-only |
| Capabilities | All dropped; no new privileges |
| Host bind mounts and published ports | None |

Task tool fingerprints, the base Python package inventory and the system package
inventory stayed unchanged through core installation. In particular, Node stayed
at v24.12.0 and Go at go1.25.5. The prepared image's layer ancestry was checked
against the published image. The local diagnostic tag is
`agentless-ml/grinta-shared-core-diagnostic:2026-10-25`; the immutable image ID
is in the evidence record.

## Edit behavior checked

The installed Grinta RuntimeExecutor performed a native file edit and shell
creation, deletion and renaming. The authored public unit test passed, and the
permitted patch was captured through Grinta's final-patch exporter. A binary
write raised the comparison-contract error before ordinary tool feedback; the
next action and final invalid patch were rejected too.

Linux checks also rejected chmod, symlink creation, case collisions and creation
of a new executable. Renaming an existing executable while editing its text was
allowed. Host checks separately cover non-UTF-8 edits, deletion of a binary file,
ignored build products, starting-path collisions and submodule pointers.
An unchanged submodule permits ordinary edits elsewhere; a changed pointer fails.

These checks apply at completed-action boundaries and at final export. Deleting
and restoring a file inside one shell command is intentionally allowed. This is
the agreed persistent-source rule, not continuous filesystem monitoring.

## Setup changes and retained blockers

The older Grinta installer installs Node 22 and system symlinks. The opt-in
`preserve_task_toolchain` recipe keeps existing task tools and uses private
runtime locations instead. The ordinary installer is unchanged.

The first Git-based setup timed out after a TLS-interrupted source fetch.
A local Git archive then delivered the same commit; every delivered blob and
executable bit was verified against Git. Core installation succeeded. The
separate Codex binary download reached its setup cap, so only the completed
core runtime was retained for this model-free check. Model transport remains
unfinished and was never invoked. Both setup failures remain in the evidence.

Pier's normal copy operation also refused the read-only root. Its opt-in shared
profile now streams the source archive into writable `/tmp`, preserving bytes
and modes. Logs stay under `/tmp` too. Session cleanup removes its containers
and volumes without deleting the shared images.

## Scope and reproduction

The installed Grinta revision was `7f8b43a0293c143e2ca6363697baa8185ad3fa34`.
The later starting-path collision refinement has separate host coverage. Exact
host harness hashes are retained in the evidence.

Core setup can be reproduced from Grinta with
`python -m evaluation.deepswe.rehearse_shared_runtime --core-runtime-only`,
supplying the shared task record, exact Grinta commit, optional verified source
archive and a new output directory. Then run Agentless-ML's
`tools/rehearse_shared_containers.py` with the prepared image, Grinta checkout,
Pier interpreter and a new output directory. Both tools accept `--help`.

This establishes one actual environment and the controlled edit behavior.
It does not register the prepared image for benchmark selection, freeze a pilot
protocol or establish all 113 environments. Apply and record the common runtime
setup for the selected pilot tasks before the research run.
