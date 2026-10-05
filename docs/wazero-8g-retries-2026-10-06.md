# Wazero retries at the published 8-GiB limit

Reducing test concurrency did not recover Wazero's full public baseline within
8 GiB. A second attempt with earlier Go garbage collection also ended in OOM.
The larger-memory diagnostic remains the only successful full-suite run.

Both attempts used the same pinned image, sealed base revision, two CPUs,
4-GiB temporary filesystem and 1,800-second command timeout. Both selected all
packages with `./...`; neither used short mode or excluded individual tests.

| Attempt | Additional Go test arguments | Outcome | Command duration |
| --- | --- | --- | --- |
| Serial execution | `-p 1 -parallel 1` | OOM | 322 seconds |
| Serial execution, earlier collection | `-p 1 -parallel 1 -exec 'env GOGC=20 GOMEMLIMIT=6GiB'` | OOM | 525 seconds |

During the first run, the live public test stream reported `signal: killed`
while running `TestEngineInterpreter/huge_binary` in
`internal/integration_test/engine`. The cgroup reached exactly 8 GiB and
recorded one OOM kill. The test constructs a module with 40,000 functions and
instantiates it; this is a substantial allocation workload even with one
package and one parallel test running.

The second attempt made Go collect unused heap earlier. Its last memory sample
was about 7.8 GiB while the same huge-binary test was active. It subsequently
ended in OOM. That sample is not the final memory peak, and the saved artifacts
do not identify the second run's final killed test.

The memory counters include tmpfs and cache as well as process memory. These
results show that the two attempted schedules could not complete within our
8-GiB container setup; they do not prove that every possible runtime setting
would fail or that DeepSWE's held-out verifier needs the same memory.

Neither attempt yielded a usable complete test inventory. The runner records
zero test cases for an OOM execution because it does not accept its report as
baseline evidence; this does not mean that no tests ran. The planned comparison
against all 155,967 outcomes in the successful diagnostic therefore could not
be performed.

The experimental task overrides were removed after verification. The checked-in
default command is unchanged, Wazero remains `out_of_memory`, and readiness is
still **81/113**. The attempts remain in the append-only local survey.

[The evidence summary](../experiments/deepswe/wazero_8g_retries_2026_10_06.json)
records both commands, sampled observations, resource settings and execution
hashes. The
[16-GiB diagnostic](wazero-memory-diagnostic-2026-10-05.md) retains the successful
full-suite result and converter validation. The existing runner and override
checks passed with 69 tests during this work.

Next, continue the other tasks that were blocked by Git links. Keep this
full-public-suite resource limitation documented rather than dropping the
stress test to turn the result into a passing baseline.
