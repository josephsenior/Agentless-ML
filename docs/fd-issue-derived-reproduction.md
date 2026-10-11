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
running the public regression suite. The follow-up below records that check.

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

This was a reproduction-only recorded slice: there was no separate public
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

## Public regression follow-up

The exported repair was checked separately against fd's existing full public
nextest schedule on the same day. No generated reproduction test was added to
this checkout. The exact patch hash was checked against the earlier export;
only the same four production files changed.

The repair ran all 241 tests: **240 passed and one failed**, in 127.2 seconds.
The failure was `fd-find::tests::test_exec_nulls`: its `--print0 --exec printf`
command produced concatenated output with misplaced NUL separators.

An older fd workflow had all 241 tests passing, so a fresh unpatched control
was run with this diagnostic's exact command, image and limits. That control
also had **240 passes and the same failure**, in 132.1 seconds. All test IDs
and outcomes match; all 240 baseline-passing tests still pass after the repair.
There is no added regression in this comparison. Both raw suite results remain
`FAIL`—the shared failure is recorded, not filtered out or relabelled as a pass.
Why this setup differs from the historical 241-pass run has not been established.

Both runs used the existing whole-suite `cargo-nextest` command without target
filters or an override. The plan was derived from the pristine pinned checkout
before applying the export. They kept the same offline protections, 4 GiB
memory/scratch, one CPU, 2,048-process limit and 600-second cap. Both rebuilt
from source; neither was retried. No model or held-out verifier was called.
The original source remains sealed and both temporary workspaces were cleaned.
Readiness stays 109/113; this is still a partial repair, not a full task solution.

The [regression evidence](../experiments/reproduction/fd_public_regression_2026-10-11.json)
records both outcomes, the matched comparison and hashes of the local reports.
Full local artifacts are in `artifacts/fd-exported-regression-20261011` and
`artifacts/fd-exported-regression-base-20261011`. The historical reproduction
evidence above is unchanged; its `public_regression_suite_run: false` describes
that earlier controller run, not this later check.

To repeat against the same saved export, choose a new output directory:

```powershell
$env:PYTHONPATH='src'
.venv/Scripts/python.exe tools/run_fd_exported_regression.py --prediction artifacts/fd-path-sort-reproduction-20261011/runs/run-43edeceeded64781ba8eec67c1300aa1/prediction.json --output artifacts/fd-public-new --tasks-root ../benchmarks/deepswe/corpus/tasks --repositories ../benchmarks/deepswe/repos
```

Add `--baseline` and use another fresh output directory for the unpatched
control. The tool exits nonzero for a failing suite while retaining its report.
The related local checks now have 122 passes and 12 opt-in skips; the two real
Docker suite runs were performed separately, not counted as pytest passes.

## Both checks in one controller run

The combined run also completed on 11 October. It uses the controller's existing
regression inventory and reproduction specification together; no framework
implementation change was needed. The recorded localization, reproduction
source and repair responses are unchanged. The regression-exclusion response
is empty: no baseline-passing test was manually removed.

| Check | Observed result | Time, including fresh build |
| --- | --- | --- |
| Base reproduction | Fail: requested `--sort` option absent | 183.0 s |
| Base public suite | 240 passed, `test_exec_nulls` failed | 216.4 s |
| Repair public suite | Same 240 passed and same failure | 181.9 s |
| Repair reproduction | Pass | 166.7 s |

The controller froze all 240 baseline-passing IDs before candidate validation.
The repair preserved every one. Both public commands still ran all 241 tests
without filters, and both raw results remain `FAIL`. The shared failure is kept
in the reports, not turned into a passing test. The generated reproduction
appears only in its own checks, not in either public-suite inventory.

The malformed repair was rejected before execution. The valid partial repair
was selected through `best_regression_then_reproduction_passed_then_normalized_majority`
and exported. Its prediction is byte-for-byte identical to the earlier
reproduction-only export. Only one valid repair was supplied, so this checks
integration and selection execution, not comparative ranking performance.

The run took 752.7 seconds across four isolated Docker checks, each under the
unchanged 600-second cap and resource protections. There were no retries, model
calls or held-out tests. The source remains sealed, temporary workspaces are
cleaned, and the repair still does not implement the full multi-key request.
DeepSWE readiness remains 109/113.

The [combined evidence](../experiments/reproduction/fd_combined_validation_2026-10-11.json)
records the run ID, selection, limits and four report hashes. Local artifacts
are under `artifacts/fd-combined-validation-20261011`. The related fixture,
Rust/controller, regression-selection and report-parser checks passed 179 tests,
with 12 opt-in tests skipped; the real Docker controller run was separate.

Use the existing reproduction tool with the combined option and a fresh output:

```powershell
$env:PYTHONPATH='src'
.venv/Scripts/python.exe tools/run_fd_path_sort_reproduction.py --with-public-regressions --output artifacts/fd-combined-new --tasks-root ../benchmarks/deepswe/corpus/tasks --repositories ../benchmarks/deepswe/repos
```

`--audit-existing` also understands combined runs and verifies their saved
reports without launching Docker. It checks that raw JUnit agrees with the
saved outcomes, both complete public inventories are present, counted IDs match
the baseline passes, no manual exclusions were introduced, and the exported
patch matches the original repair. Audit tests cover newly failed or skipped
tests, missing tests, changed reports and incorrectly counted IDs.

Next: verify multiple-reproduction-sample selection on a real Rust task,
using recorded samples and the existing controller rather than a model call.
