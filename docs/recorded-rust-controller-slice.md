# Recorded Rust controller check

The complete slice passed on 11 October 2026. It used recorded responses and
actual offline Docker execution, with no model calls.

This is an authored, dependency-free crate, not a benchmark result. We reused
the pinned Wasmi image for its Rust toolchain; we did not run Wasmi's task or
held-out tests. The older fd smoke fixture deliberately contains non-solution
patches, so it is not suitable for demonstrating a reproduction that becomes
passing after repair.

## What ran

The crate's `add` function initially subtracts. Its existing public test checks
`add(0, 0) == 0`; the recorded reproduction checks `add(2, 3) == 5`.
This intentionally weak public test lets the check establish that reproduction
evidence, rather than regression evidence alone, affects selection.

The normal controller handled file, symbol and edit-line localization, regression
selection with no exclusions, reproduction baseline eligibility, patch creation,
candidate workspaces, validation, selection and final prediction export.

| Input | Public regression | Reproduction | Outcome |
| --- | --- | --- | --- |
| Original subtraction | Pass | Fail | Reproduction eligible |
| Malformed repair | Not run | Not run | Rejected before validation |
| Multiplication repair (`repair-1`) | Pass | Fail | Not selected |
| Addition repair (`repair-2`) | Pass | Pass | Selected |

The exported `prediction.json` contains only the `src/lib.rs` addition patch.
It does not include the reproduction test or changes to existing tests or the
manifest. The source checkout is unchanged and temporary candidate workspaces
were removed. All six executions retain structured results and raw nextest
JUnit bytes inside their `report.json` files.

Execution stayed offline with a read-only container root, dropped capabilities,
no-new-privileges, 4 GiB memory, 4 GiB writable temporary space, one CPU and a
2,048-process cap. Each command had a 120-second timeout; nextest used one build
worker, one test worker and zero retries. The first complete run took 28.9 seconds.
An earlier launch stopped at the local Git provenance check before controller
execution; the helper now trusts only the exact local path for that command,
without changing global Git configuration.

## Reproduce and inspect

From the repository root, with the virtual environment and Docker available:

```powershell
$env:PYTHONPATH='src'
.venv/Scripts/python.exe tools/run_recorded_rust_slice.py --output artifacts/rust-controller-new
```

The output directory must not already exist. The script checks the exported
prediction against the in-memory result and run-record patch hash, baseline
outcomes, both candidate outcomes, all six raw reports and workspace cleanup.
`summary.json` links to the complete controller artifacts, including prompts,
recorded responses, baseline evidence, candidate logs, selection and prediction.

The saved [evidence summary](../experiments/rust/recorded_controller_2026-10-11.json)
identifies the first complete run and its patch hash. Detailed local artifacts are
under `artifacts/rust-controller-20261011-verified/`; they are ignored by Git.
An opt-in end-to-end test lives in `tests/test_recorded_rust_slice.py` and uses
`AGENTLESS_RUST_REPRODUCTION_DOCKER_TESTS=1`.

Verification: the new Docker end-to-end test passed separately in 38.2 seconds.
The related Rust, fixed-workflow, reproduction, regression-selection and patch
selection suite passed 187 tests, with 23 opt-in execution tests skipped in
that run. The complete CLI run above and the new Docker test were both executed.

This checks plumbing and selection on a simple known example, not generated-test
quality, benchmark accuracy or resistance to misleading Rust test code. The
[Rust reporter limitations](rust-reproduction-reporting.md) still apply.
DeepSWE readiness remains 109/113.

Next: review the reproduction-validation coverage across languages and identify
any remaining framework gaps before adding real model integration.
