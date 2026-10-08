# Numba: interrupted full two-worker attempt

The requested full attempt used native `-m 2`, the pinned image and candidate
source build, and the same 1,800-second command timeout, 8-GiB memory, two CPUs,
4-GiB tmpfs and Docker protections. No tests were narrowed and no automatic
retry was started. The official override and survey remain unchanged.

The one-shot command lives in `tools/run_numba_two_worker_baseline.py`. It
retains Numba's native discovery, builds candidate extensions, verifies their
imports and declares the complete JUnit report. Resource observations use the
same sampler as the short diagnostics. Before launch, the new command check
and existing recorder suite passed: **12 tests**.

## What is known

The live native loader reported 9,907 parallel tests and 702 serial-only tests.
The last retained progress observation was at least 450 completed tests,
roughly nine minutes into monitoring. The last observed cgroup memory peak
was 2,066,677,760 bytes (1.93 GiB), with zero observed OOM events at that point.
Those are partial observations, not an accepted regression inventory.

On continuation, the host shell session no longer existed, Docker Desktop was
stopped and the artifact directory was empty. After starting Docker solely
for recovery inspection, the original container was stopped with container
exit code 255 and `OOMKilled=false`. This is the container's state, not a
captured native test-runner exit or proof about all worker memory events.
Neither `/tmp/report.xml` nor the two command logs could be recovered from the
stopped container. Its `/tmp` was the normal memory-only mount; no host mount
or persistence exception had been introduced.

The host runner therefore saved no execution record, final report or resource
sample JSON. The cause and precise interruption point were not established.
Container start/finish timestamps alone cannot establish how long tests ran
or whether they finished while the host supervisor was unavailable.

## Outcome

**Interrupted; completion unknown.** Do not reclassify this as a demonstrated
30-minute timeout, test failure, OOM or completed baseline. Numba remains
unready and survey readiness stays 100/113. No further attempt was launched
during recovery. Starting again requires a fresh complete attempt, not a
resume of the terminated Python test processes.

Recovery removed only this attempt's stopped container and its temporary
`candidate-slhyvd7m` clone. The clone's matching base, creation provenance and
clean Git status were verified before cleanup. The pinned source repository
and image remain available to recreate it. Docker is running after recovery.
The 12 focused command/recorder tests also passed again; no benchmark tests
were relaunched.

The failed recovery targeted only
`agentless-ml-2c73354251134efea4ed501bbb12ac3a`, using pinned image
`sha256:d30747d56f59cb61bb9a4e87ba8dc4df29ccbb471a1a1146f20d5d9d58fa90ac`.
Its allocated artifact directory was
`../output/deepswe-survey/numba-two-worker-full/logs/agentless-ml-2c73354251134efea4ed501bbb12ac3a/`.

## One-shot invocation

Only run this after approval for a fresh full attempt, with Docker and the host
kept running throughout. It has no retry loop and does not modify the survey.

```powershell
.\.venv\Scripts\python.exe tools/run_numba_two_worker_baseline.py
```

The [short timing repeat](deepswe-numba-two-worker-diagnostic-2026-10-08.md)
remains the completed timing evidence. It does not establish full-suite runtime.
