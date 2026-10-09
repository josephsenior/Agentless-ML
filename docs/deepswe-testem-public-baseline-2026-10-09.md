# Testem: full public attempt, interrupted host

One full public baseline was started against the verified Firefox image. It
ended with the runner's `timeout` status and no usable test report. **This is
not a completed baseline or a clean measurement of the schedule's runtime.**

The command reused the existing Mocha runner with both targets from the pinned
public package.json: `tests/*_tests.js` and `tests/**/*_tests.js`. The xUnit
reporter was unchanged. No tests, assertions, browser flags, environment fixes
or exclusions were added. The candidate was a fresh sealed checkout at
`158f61ea91c9613d2011c41ee9be40ada1d7a307`, not the image's source tree.

Image:

```
sha256:290cd40e1e05814859e3a0430b7bcbea77d92b8fcdd5161fd6ef1c1fc14e969d
```

The run retained offline networking, read-only root, dropped capabilities,
no-new-privileges, 8 GiB memory without additional swap, two CPUs, 2,048 PIDs
and the same 4 GiB /tmp. The configured timeout was 1,800 seconds.

## What happened

Firefox processes launched repeatedly. Read-only probes observed low memory
use (roughly 133–186 MiB at sampled points), ample temporary space and zero
cgroup OOM events. These are samples, not peak-use measurements. The public
launcher passed `-profile --headless <temporary-profile> <localhost-url>`;
that matches the pinned source. We did not alter or establish the correctness
of that argument order.

A host/tool wait requested for 50 seconds returned after roughly 3,695 seconds.
Afterwards the container's process elapsed time was only about six minutes,
despite over an hour of host wall time. This is consistent with a host/VM
pause, but the precise cause was not established. A scoped Windows keep-awake
request had been active; it does not guarantee protection from every kind of
pause. It was released when the runner returned.

The runner recorded 4,026.891 seconds and timeout, with no exit code or test
cases. The report file was empty when probed before cleanup. The runner does
not export reports on its timeout path. Thus zero recorded cases means
**results unavailable**, not that zero tests executed or that all tests failed.
The observed overrun is not a new timeout setting or evidence that Testem needs
more than 30 uninterrupted minutes. No automatic retry was started.

The owned container was removed. Raw evidence remains under
`../output/deepswe-survey/testem-firefox/logs/agentless-ml-bbb2422a90a746ab933ebb2a152c9ad6/`:
`execution.json`, `public-schedule.json`, `stdout.log` and `stderr.log`.
The [compact record](../experiments/deepswe/testem_public_baseline_2026_10_09.json)
preserves the timeout together with its timing caveat.

## What follows

Testem is still unready; canonical readiness stays 100/113. This separately
supplemented image did not update the original-image survey. No held-out tests
or solutions were read. KGateway, Numba and Pwntools remain parked.

The next useful step is one explicitly approved repeat of the same schedule on
an uninterrupted host, with the same cap and protections. That repeat has not
started. If it still stalls, inspect public Firefox launch/cleanup behavior
before making any further environment changes.

Host-side checks for the wrapper, image helpers and shared execution commands:
96 passed, four opt-in checks skipped. Global Python's unrelated libtmux pytest
plugin initially prevented collection; disabling host plugin auto-loading
resolved that. The benchmark command and image were not changed by this fix.
