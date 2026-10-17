# Numba: one approved three-hour public baseline

The user approved one full public-baseline attempt with a **10,800-second**
cap. This is an explicit change from the earlier 1,800-second public-command
allowance. It does not change the benchmark's final verifier timeout or
establish that a baseline plus multiple candidate evaluations fit the agent's
three-hour budget.

`tools/run_numba_two_worker_baseline.py` now accepts `--timeout-seconds` and
`--artifact-root`. The default remains 1,800 seconds; the explicit upper bound
is 10,800. Host and container deadlines receive the same value. The container
deadline covers the candidate extension build, import checks and complete
native schedule, with the existing ten-second termination grace. There is no
automatic retry.

The attempt keeps the pinned image and base, two native workers, 8 GiB memory,
two CPUs, disk scratch, Docker-default swap, offline networking and
`OPENBLAS_NUM_THREADS=1`. Numba's own thread maximum and full discovery stay
unchanged. The extensions are built from candidate source; tests and assertions
are not modified. The native recorder retains individual outcomes only when
the schedule completes.

An exclusive `attempt-started.json` records the command and settings before
execution. Resource samples retain UTC timestamps as well as elapsed time.
Full runs do not install the short diagnostic's timing hooks, so they no
longer try to collect those nonexistent journals during cleanup. The native
JUnit report and resource journal remain their evidence.

All **16 focused command and native-recorder tests passed** before launch.
The added checks verify that the three-hour option changes only the deadline,
preserves the schedule/report and rejects invalid or larger allowances.

Docker initially exited during startup because Windows could not access its
zero-byte `dockerInference` runtime socket. Moving that individual socket
failed with Windows error 1920. With Docker stopped, its runtime directory
was inspected: it contained only two zero-byte socket entries. Renaming the
directory preserved both entries at
`C:/Users/GIGABYTE/AppData/Local/Docker/run.numba-20261017-backup` so Docker
could recreate its runtime sockets. Image storage, settings and host power
configuration were not changed. The backup has not been deleted.

The selected invocation is:

```powershell
$env:PYTHONPATH='src'
.venv/Scripts/python.exe tools/run_numba_two_worker_baseline.py --timeout-seconds 10800 --artifact-root ../output/deepswe-survey/2026-10-17-numba-three-hour
```

This approval covers one attempt. Its result must retain full completion,
failures, skips or timeout evidence before deciding whether the longer public
schedule can be registered for candidate validation. The canonical readiness
count remains **112/113** until that review; a longer baseline alone does not
silently change the experimental protocol.

## Completed attempt

The one attempt finished after **about 95 minutes**, inside the three-hour
allowance. It produced **10,609 unique reported test IDs**, matching the
reviewed native discovery count. The native summary and structured report
agree:

| Outcome | Count |
| --- | ---: |
| Passed | 9,987 |
| Failed assertions | 1 |
| Test errors | 3 |
| Native skips | 595 |
| Expected failures | 23 |

The structured report represents the 23 expected failures as skipped, so it
contains 618 skipped outcomes. The native command returned **1**, and the
runner correctly retained status `fail` with the full report. This was a
completed baseline with passing-test evidence, not an all-passing suite.

All four nonpassing cases belong to public cache tests:
`TestCache.test_frozen`, `TestCache.test_non_creatable_pycache`,
`TestCache.test_non_writable_pycache` and `TestCacheZip.test_zip_caching`.
The ZIP test explicitly reports a read-only filesystem at
`/root/.cache/numba`. The other tests exercise the user-wide fallback, whose
public implementation rejects a locator when its cache cannot be created.
A writable user-cache location is the next setup fix to assess; no such
change or further test run was made here. All four outcomes remain visible.

There were **551 resource samples**, with a maximum interval of 11.9 seconds.
The largest observed kernel memory peak was **7,576,219,648 bytes** (about
7.06 GiB), below the 8-GiB cap. No sampled OOM events, OOM kills or swap use
were recorded. The owned container, disposable volume and temporary candidate
checkout were cleaned up normally.

The host execution record reports 5,702.42 seconds and the native summary
5,707.688 seconds. Both measurements are retained with their different clock
and measurement scopes; neither is presented as an exact cross-clock study.
The complete attempt ran from 16:12:52 to 17:47:57 on 17 October, Paris time,
including setup before the timed public command. No automatic or manual retry
followed.

The [result record](../experiments/deepswe/numba_three_hour_baseline_2026_10_17.json)
pins the report, execution, resource journal and log hashes. Raw artifacts are
under `../output/deepswe-survey/2026-10-17-numba-three-hour/logs/agentless-ml-5d409d9e5ac347ccb527c09b5146a03f/`.

This establishes a complete Numba public baseline under the approved longer
allowance. Registering a matching candidate-validation profile and accounting
for its cost remain separate decisions. The existing 30-minute profile and
canonical **112/113** survey count were not changed. No held-out verifier or
model was run.
