# Rust reproduction reporting on real fd source

Both controls passed on 11 October 2026, using fd's pinned repository revision
`227883606023d62275fb48701aeac90f2b604143` and its pinned DeepSWE image
`sha256:31c4201bbe4b79457ab34494b84767d417926e1cf9e8e24ac7d44d9a8e4bc538`.

This closes the real-repository build/discovery check for the Rust reporter.
It is not an implementation or solve attempt for the multi-key sorting task,
not a full public-suite run, and not another complete controller trajectory.

## What the check establishes

The same authored integration test is installed in a fresh candidate workspace
for each control. It creates two public input files, invokes the candidate-built
`fd` binary through Cargo's `CARGO_BIN_EXE_fd`, and checks existing buffered output
contains both names in sorted order. It uses the existing `tempfile` dependency;
the manifest and all existing tests remain untouched.

| Workspace | Expected | Observed | Time |
| --- | --- | --- | --- |
| Pinned base | Pass | Pass | 189.9 s |
| Source control replacing buffer sort with buffer clear | Fail | Fail | 189.2 s |

Each command builds from source in a fresh temporary Cargo target directory.
The negative control proves that the binary under test reflects the candidate
source, rather than an executable borrowed from the image. Both outcomes contain
the named test `fd-find::agentless_reproduction::buffered_output`; their raw JUnit
bytes and CTRF reports are retained.

The negative control is explicitly a seeded regression, not a proposed repair.
The check passes on the original revision, so it is **not eligible** as a generated
issue reproduction. An issue-derived Rust check that fails on an actual task's
base revision and passes after repair remains a separate, stronger verification
step. The [complete recorded controller slice](recorded-rust-controller-slice.md)
already exercises that eligibility/selection sequence on an authored crate.

Only the sealed base checkout, its public source/tests and the agent-visible
corpus pin are used. No reference patch or held-out tests are read. The source
repository is unchanged, generated tests are removed, and workspaces are cleaned.
No model calls, official scoring or readiness changes follow from this diagnostic.

## Protections and repeat command

The normal Docker runner remains offline, read-only at the root, capability-dropped
and no-new-privileges. Limits are 4 GiB memory, 4 GiB scratch, one CPU and 2,048
processes. Each command has 600 seconds, with one build worker, one test worker
and zero nextest retries. No tooling is downloaded and no features are disabled.

From the project root, use a new output directory:

```powershell
$env:PYTHONPATH='src'
.venv/Scripts/python.exe tools/check_fd_rust_reproduction.py --output artifacts/fd-reproduction-new --tasks-root ../benchmarks/deepswe/corpus/tasks --repositories ../benchmarks/deepswe/repos
```

The helper verifies the sealed repository and pinned image, applies the negative
control through the normal candidate workspace API, and preserves provenance
even when a diagnostic assertion fails. Detailed local evidence is under
`artifacts/fd-rust-reproduction-20261011`; its compact
[evidence summary](../experiments/reproduction/validation_followup_2026-10-11.json)
is tracked in Git. Rust panic/early-exit classification limits still apply.
