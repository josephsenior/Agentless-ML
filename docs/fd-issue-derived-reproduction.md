# An issue-derived Rust reproduction on fd

The recorded controller run completed on 11 October 2026. The same Rust test
failed on the real pinned task base, passed after a partial source repair, and
the controller exported that repair as its final prediction. No model was called.

This is stronger than the earlier [existing-behavior diagnostic](fd-rust-reproduction-diagnostic.md):
that check passed on the base, so it could not establish reproduction eligibility.
This check is derived from fd's public request for deterministic sorting.

## What the test asks for

The public task requires repeatable `--sort` keys, deterministic output and
applying `--max-results` after sorting. The recorded test picks one bounded slice:

- repeatable `--sort path`;
- global ordering of 1,205 lowercase ASCII file paths, exceeding the existing
  1,000-entry output buffer;
- a zero buffering deadline, so ordinary opportunistic buffering cannot supply
  the requested behavior;
- full output and a three-result limit, checked twice against the same expected order.

It creates public input files in a temporary directory and calls
`CARGO_BIN_EXE_fd`, the executable Cargo builds from the current candidate source.
The existing `tempfile` dependency is used; manifests and existing tests are not
edited. A `--version` preflight checks that the built executable runs.

On the base, compilation and preflight succeed. The actual assertion fails
because fd rejects the requested option: `unexpected argument '--sort'`.
That missing CLI behavior is part of the issue, not an import or setup failure.
The saved JUnit contains one ordinary failed test and no errors or skips.

## What the partial repair changes

The recorded SEARCH/REPLACE response changes four production files:

| File | Reason |
| --- | --- |
| `src/cli.rs` | Accept repeatable path-sort requests using the existing CLI parser; reject incompatible execution modes. |
| `src/config.rs` | Carry an explicit path-sorting flag. |
| `src/main.rs` | Transfer that request from parsed options into configuration. |
| `src/walk.rs` | Keep collecting instead of streaming on a deadline or buffer threshold, then sort and apply the result limit. |

Without an explicit sort request, the new flag is false and the old branching
conditions are retained. That source-level observation is not a substitute for
running the public regression suite.

This is deliberately **not a full repair of the benchmark task**. Only the path
key is accepted. Other keys, reverse/grouping/natural/random modifiers,
case-folded comparisons and the remaining full-task semantics are not implemented.
The test covers lowercase ASCII paths, not every filename or platform behavior.

## Observed controller result

| Stage | Result |
| --- | --- |
| Pinned base reproduction | Fail, 119.6 s including source build |
| Malformed recorded repair | Rejected before candidate execution |
| Partial path-sort repair | Pass, 122.5 s including a fresh source build |
| Selection | `repair-1`, reproduction-passed selection |
| Export | `prediction.json`, containing only the four source-file changes |

The complete controller run took 244.3 seconds. Both executions retain their
CTRF report and raw nextest JUnit bytes. The source repository stays sealed at
`227883606023d62275fb48701aeac90f2b604143`; generated tests are absent from the
export and original checkout, and candidate workspaces are cleaned.

This is a reproduction-only recorded slice: there is no separate public
regression schedule, held-out verifier or official score. Passing this test does
not establish that the whole task is solved. DeepSWE readiness stays 109/113.

The pinned image and existing Docker protections are unchanged: offline,
read-only root, dropped capabilities, no-new-privileges, 4 GiB memory, 4 GiB
scratch, one CPU and 2,048 processes. Each command has 600 seconds, one Cargo
build worker, one nextest test worker and zero nextest retries. The test's fixed
repeated CLI invocations check determinism; they are not adaptive retries.

## Evidence and repeat command

The [recorded experiment](../experiments/deepswe/fd_path_sort_reproduction/experiment.json)
keeps the scope and limits beside its localization responses, reproduction and
repair samples. The [evidence summary](../experiments/reproduction/fd_issue_2026-10-11.json)
records the run ID, pins and source/patch/report hashes.
Full local artifacts are under `artifacts/fd-path-sort-reproduction-20261011`.

From the project root, using a new output directory:

```powershell
$env:PYTHONPATH='src'
.venv/Scripts/python.exe tools/run_fd_path_sort_reproduction.py --output artifacts/fd-issue-new --tasks-root ../benchmarks/deepswe/corpus/tasks --repositories ../benchmarks/deepswe/repos
```

The initial post-run audit expected the panic detail inside JUnit's `failure`
element, but nextest stores it in `testcase/system-err`. The controller had already
finished and exported its prediction. The audit was corrected and the saved
artifacts were verified without repeating either Docker execution. Add
`--audit-existing` to the same command to audit a saved run without launching Docker.
The audit checks the failure reason, both report outcomes, frozen source,
prediction/patch hashes, pins and workspace cleanup.

Verification: 117 related fixture, Rust reporting, workflow, repair-selection
and reproduction-overlay tests passed, with 12 opt-in execution tests skipped.
That run includes the saved-evidence audit tests and an isolated pinned-source
edit check. The actual two-execution Docker controller run described above was
performed separately through the CLI, not counted as a passing pytest Docker test.

Next: check the exported partial repair against fd's existing public regression
suite before treating it as anything beyond this reproduction-validation result.
