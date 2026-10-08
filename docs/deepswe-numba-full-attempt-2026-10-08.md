# Numba: full two-worker attempts

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

## Approved fresh attempt

After explicit approval, one fresh attempt was launched with the same native
schedule, pinned image and resource limits. Before launch, two safeguards were
added: a container-side `timeout` covering build, import checks and the entire
test command, and a resource-sample JSONL journal written after every probe.
The host timeout remains 1,800 seconds; the container deadline is also 1,800
seconds, with a ten-second termination grace. Neither change alters tests or
their outcomes. The focused command, persistence and recorder suite passed
**13 tests** before launch.

This fresh attempt ended at the container-side time limit, not as an accepted
baseline. Its resource journal is under
`../output/deepswe-survey/numba-two-worker-full/logs/agentless-ml-ac2f56c468b6407b987eb13538e416ff/resource-samples.jsonl`.
There is still no automatic retry, official override change or survey update.

## Fresh attempt result

The native schedule did **not finish before the configured 1,800-second
container cutoff**. The last progress marker recorded **1,950 completed tests**
out of the 9,907 parallel entries, with the 702 serial-only entries still
unreached. This is a completion lower bound, not a count of passing tests.
No final JUnit report was written or accepted; recorded report cases are zero.

The timeout wrapper returned **124**. The generic Docker recorder preserves
that as `harness_error` because 124 is not a declared native test-failure exit.
For this known command it is a time-limit stop, not a newly diagnosed bootstrap
failure. The raw status and exit code have not been rewritten or promoted to a
passing inventory. Host execution metadata reports **1,794.4 seconds**; the
configured host and container deadlines both remained 1,800 seconds.

All 165 resource samples were retained both incrementally and in the final
attempt JSON. The largest observed kernel memory peak was **5,355,520,000 bytes
(4.99 GiB)**, below the 8-GiB limit. Recorded memory-event counters showed no
OOM events or OOM kills. The largest sampled PID/thread count was **167**,
below the 2,048 cap. Worker recycling allowed later progress after the long
early batch; it did not make the complete schedule finish within this attempt.

The journal includes one **88.42-second gap** between host sampling offsets.
The cause was not established. A separate monitoring command's permission
review also timed out and was retried once; no test attempt was retried. This
is not a clean uninterrupted timing study, so do not infer an exact intrinsic
full-suite duration or claim that no possible two-worker run could fit. What
is established is that this run hit its independent container deadline without
finishing. The stderr tail reached public dispatcher tests and includes the
resource-tracker shutdown warning about six semaphore objects. Failures and
warnings were not suppressed, and no selectors or exclusions were added.

The owned container and temporary candidate clone were cleaned up. The native
tests were not restarted after the cutoff. The official survey still reports
**100/113 ready**, with Numba unready under its existing timeout record. Memory
was not the observed stopping condition; completion under the time cap remains
unproven. Further retries are parked under the current limits.

The user has explicitly confirmed parking Numba and moving to another unready
task. Keep its existing survey record, pinned image and test configuration;
do not increase limits, narrow the schedule or launch another attempt as part
of the remaining setup work. This is a work-priority decision, not removal
from the benchmark or a claim that the complete suite can never finish.

Final evidence is under
`../output/deepswe-survey/numba-two-worker-full/logs/agentless-ml-ac2f56c468b6407b987eb13538e416ff/`:
`execution.json`, `full-attempt.json`, `resource-samples.jsonl`, `stdout.log`
and `stderr.log`. These are real outputs from the pinned candidate and image,
not replayed responses or model-generated test results.
