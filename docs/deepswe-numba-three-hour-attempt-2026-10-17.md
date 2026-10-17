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
