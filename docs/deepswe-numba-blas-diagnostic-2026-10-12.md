# Numba: short sample with one OpenBLAS thread

One approved diagnostic used the existing pinned source and image, a candidate
extension build and explicit native `-m 2` execution. Its test window was
configured to stop after 300 seconds; the outer command cap remained 1,800
seconds. The helper now matches the registered disk-backed scratch,
Docker-default swap and `OPENBLAS_NUM_THREADS=1` settings. RAM remains 8 GiB,
CPU quota remains two, and the other Docker protections are retained.

The focused diagnostic-command and recorder checks passed: **14 tests**.
The complete native schedule was offered without selectors or exclusions.
Discovery reported the same 9,907 parallel and 702 serial-only entries.

## Result

The command stopped at its deliberate cutoff with exit **124**. The generic
execution record calls this `harness_error` because 124 is not a native
test-failure exit; here it represents the diagnostic's timeout wrapper.
The host execution record reports **309.93 seconds**, including surrounding
preparation and cleanup. No complete report was accepted.

The final retained marker was **425 completions**. Markers appear every
25 completions, so this is a lower bound rather than an exact count of passing
tests. The serial-only remainder was not reached.

Across 29 retained snapshots:

- largest observed kernel memory peak: **1,669,271,552 bytes (1.55 GiB)**;
- largest sampled PID/thread count: **30**, below the 2,048 cap;
- observed swap use: **zero**;
- recorded OOM and OOM-kill events: **zero**.

Host sample intervals ranged from 10.22 to 10.32 seconds; the last sample
offset was 287.42 seconds after sampling began. No large sampling gap was
observed. These offsets and execution metadata are retained as reported;
they do not independently measure every phase of the container's clock.
Stderr retains the native shutdown warning about six semaphore objects after
forced termination. It was not suppressed or counted as a passing outcome.

The earlier clean short sample reached at least 350 completions with a
1.42-GiB observed peak. The current sample reached 425, but scratch, swap and
BLAS settings differ, and these are completion lower bounds, not paired
timing measurements. This does not isolate a BLAS speedup or establish that
the complete 10,609-entry schedule fits in 30 minutes. Later phases and
memory peaks remain unmeasured under this condition.

The subsequent [batch review](deepswe-numba-batch-review-2026-10-12.md) maps
the saved worker lifetimes to native test groups. Groups 101–200 and 301–400
were the slower observed groups; exact per-test timings were not recorded.

The container, anonymous volume and temporary candidate workspace were cleaned
up. The survey was not updated; public-baseline readiness remains **112/113**,
with Numba unready. No full attempt or automatic retry was started.

## Evidence

The directory
`../output/deepswe-survey/numba-two-worker-diagnostic/logs/agentless-ml-1024dd72c0424c49bacae8a3d014e11d/`
contains `execution.json`, `resource-diagnostic.json`, the incremental
`resource-samples.jsonl` journal, and both command logs.

The [thread inspection](deepswe-numba-threads-2026-10-12.md) records why the
BLAS-only cap preserves the discovered inventory. The earlier
[full-attempt record](deepswe-numba-full-attempt-2026-10-08.md) remains historical
evidence for its previous runtime settings.
