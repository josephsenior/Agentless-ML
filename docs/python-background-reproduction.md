# Python background failures and Docker verification

The review found a real reporting bug: a script could return normally after a
worker thread raised `RuntimeError`, and the Python wrapper would report a pass.
The main-thread `try` block never saw that exception.

## Fix

The existing wrapper now records errors delivered through `threading.excepthook`,
`sys.unraisablehook`, and the standard asyncio loop's `call_exception_handler`.
It keeps their normal diagnostics, including a repository's custom asyncio
handler. Reported background errors override both a main-thread pass and an
assertion failure: they produce an error, not an eligible issue reproduction.
Only a main-thread `AssertionError` without background errors is an ordinary fail.

Before writing the report, it collects cyclic garbage and waits for threads
created during the script, including daemon threads. The existing Docker command
timeout bounds this wait. A nonterminating worker must therefore time out rather
than receive a passing report. No new service, runner interface or retry was added.

`background_errors` in the retained CTRF report records the channels observed:
`thread`, `asyncio`, or `unraisable`. The normal stdout/stderr evidence remains.

This is not a sandbox inside the process. Code can replace hooks, catch its own
errors or perform no meaningful assertion. Exceptions handled by the script are
not failures. Errors that only occur during interpreter shutdown or `atexit`,
unobserved pending async work, subprocess failures not checked by the script,
and custom event-loop implementations are not generally proven by these hooks.
Generated source still belongs in Docker, and a report is not semantic proof.

## Complete recorded slice

The authored fixture starts with a subtracting `add` function. Its existing
public check tests `(0, 0)`; its reproduction tests `(2, 3)` against an expected
sum of five. The controller runs all normal stages through prediction export.

| Input | Public regression | Reproduction | Selection |
| --- | --- | --- | --- |
| Original subtraction | Pass | Fail | Eligible baseline |
| Malformed repair | Not run | Not run | Rejected |
| Correct sum with a failing daemon worker | Pass | Harness error | Excluded |
| Multiplication | Pass | Fail | Not selected |
| Clean addition | Pass | Pass | `repair-3` |

The background-failing candidate returns the right value, so this specifically
checks the bug: an assertion-only wrapper would have accepted it. The final patch
contains only the clean source repair; neither the reproduction nor public check
is exported. The original checkout stays unchanged and workspaces are cleaned.

## Reproduction-sample selection

A second complete Docker slice supplies five recorded samples: malformed source,
an already-passing check, two copies of the same failing issue check, and one
different failing check. The malformed sample is excluded, the passing sample is
ineligible, and the duplicate source wins with two votes (selected index 2;
eligible indices 2, 3 and 4). Its source and digest are frozen before repairs.
Candidate outcomes and final selection match the single-source slice.

A separate Docker test supplies a sample with both a main-thread assertion
failure and a worker error. The controller stops with a harness error before
selection or repair evaluation; it does not quietly discard the broken sample.

These are controlled fixtures, not benchmark scores. They use the local pinned
Wasmi image for Python, not Wasmi's task. Commands remain offline, read-only at
the container root, capability-dropped and no-new-privileges, with 4 GiB memory,
4 GiB scratch, one CPU and 2,048 processes. Normal commands retain 60 seconds;
the intentional nonterminating-worker diagnostic uses a two-second command cap.
No live model, downloads, held-out tests or readiness changes are involved.

## Run again

Use a new output directory for each run:

```powershell
$env:PYTHONPATH='src'
.venv/Scripts/python.exe tools/run_recorded_python_reproduction.py --output artifacts/python-reproduction-new
.venv/Scripts/python.exe tools/run_recorded_python_reproduction.py --output artifacts/python-samples-new --samples
```

The opt-in tests in `tests/test_recorded_python_reproduction.py` use
`AGENTLESS_PYTHON_REPRODUCTION_DOCKER_TESTS=1`. Unit tests additionally cover
background assertion failures, delayed daemon errors, asyncio callback/task
errors (including a custom handler), unraisable cleanup errors and clean workers.

Detailed first-run artifacts are under `artifacts/python-reproduction-20261011`
and `artifacts/python-reproduction-samples-20261011`; final-wrapper test artifacts
are under `artifacts/python-reproduction-final-tests-20261011`. These are ignored
by Git. The source fix and repeatable test scripts are tracked.

The final focused run passed 41 tests, including all four Docker tests. The
[committed evidence summary](../experiments/reproduction/validation_followup_2026-10-11.json)
records the final-wrapper run IDs, selected source digest and patch digest.
The final shared reproduction/workflow/selection/Docker-recorder regression run
passed 239 tests, with 34 opt-in execution tests skipped. The four new Python
Docker tests above ran separately and passed; the two real fd controls also ran.
