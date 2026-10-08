# Numba: two-worker resource sample

This is a resource diagnostic, not a baseline. Numba is still not ready and
the official survey remains at 100/113. No full parallel retry was started.

## What changed

The result recorder now observes Numba's native `ParallelTestResult.add_results`
as well as ordinary unittest callbacks. It retains native aggregation and
exit behavior, records worker failures, errors, skips and expected failures,
and handles the serial-only remainder. Subtest failures belong to their
scheduled parent test. Duplicate IDs keep their worst outcome. An empty,
ambiguous, crashed or incomplete run still cannot produce an accepted report.

The worker's normal result envelope contains a test ID and execution count,
not a list of successes. A pass is recorded only when that envelope confirms
one executed test and carries no non-passing outcome. Fixture errors without
an executed test are recorded as errors, never as a passing blocked test.

Spawned-worker fixtures exercise mixed outcomes, nested runner probes, serial
callbacks, interrupted pools and ambiguous worker results. The official
`numba-runtests` override remains serial and unchanged; parallel support alone
does not change the benchmark schedule.

Verification: the recorder-focused suite passed all 11 tests. The separate
full project rerun passed **683 tests**, with 31 opt-in/platform skips, in
318.2 seconds. The first full run had 682 passes, 31 skips and one Windows
subprocess timeout; the same case passed on the rerun without weakening its
60-second timeout or changing its assertions.

## What ran

`tools/run_numba_resource_diagnostic.py` builds the candidate extensions,
checks all seven candidate imports, and starts the native full public schedule
with explicit `-m 2`. It keeps the same pinned image, 8-GiB memory, two CPUs,
4-GiB tmpfs, 2,048-PID cap, 1,800-second outer timeout, offline networking,
read-only root and capability restrictions. An inner `timeout` requests a
300-second test window with a ten-second kill grace. No tests or dependencies
were changed and no held-out tests or solutions were inspected.

The diagnostic has its own artifact directory and does not append to
`survey.jsonl` or declare a report for regression selection. Progress markers
are diagnostic counts, not a partial baseline or a count of passing tests.

The native loader split the schedule into 9,907 parallel tests and 702 serial
tests. It emitted progress through 400 completed tests. Process snapshots
show the pool replacing its workers between 100-test batches, as the public
runner specifies. The serial remainder was not reached.

Thirty-one resource snapshots were retained. The largest observed cgroup
`memory.peak` was **1,648,668,672 bytes (1.54 GiB)**, well below 8 GiB. The largest
sampled `pids.current` was 135, below 2,048; it includes threads, not just the
two worker processes. Sampled memory-event counters reported no OOM or OOM
kills. Cgroup memory includes the parent, workers and charged temporary files.

## Timing caveat and conclusion

This was not a clean inner-timeout completion. The outer runner recorded
`timeout`, no exit code and 2,563.8 seconds of host elapsed time. Live container
process elapsed time was about five minutes, while host sample offsets made
large jumps. The cause of that disagreement was not established. A Windows
unit-test subprocess also hit its timeout during the first full project test
run; that result was retained and the project suite was rerun separately.

Do not extrapolate a full-suite duration from these clock readings. The sample
shows that two workers can run the early schedule within the memory and PID
limits, not that every later test will fit or that all 10,609 tests will finish
within 30 minutes. No complete report was accepted. The owned container and
temporary candidate workspace were cleaned up.

Before a full retry, obtain a clean short timing sample on an uninterrupted
host. There is no reason from this sample to increase memory, but there is
also no evidence yet that the full schedule meets the time limit.

## Evidence and reproduction

Artifacts are under
`../output/deepswe-survey/numba-two-worker-diagnostic/logs/agentless-ml-87dcf61a68174f7e973784b967fcb66d/`:
`resource-diagnostic.json`, `execution.json`, `stdout.log` and `stderr.log`.
The pinned base and image are unchanged from the
[candidate-build review](deepswe-numba-baseline-2026-10-08.md).

```powershell
.\.venv\Scripts\python.exe tools/run_numba_resource_diagnostic.py
```

This command deliberately creates another diagnostic, not a full baseline.
