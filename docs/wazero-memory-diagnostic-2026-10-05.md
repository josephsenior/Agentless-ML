# Wazero's full public suite with a larger memory limit

The full `go test -json -count=1 ./...` schedule completed with **155,928
passes, 39 skips and no failures** after raising the container limit from
8 GiB to 16 GiB. The published image and sealed base revision stayed the same.
The survey attempt, including preparation and reporting, took 299.1 seconds.

During test execution the container exceeded 8 GiB. A later cgroup sample
reported a peak of 11,752,079,360 bytes, about 10.95 GiB. This is total container
memory accounting, including tmpfs and cache; it does not measure test-process
RSS alone or establish the minimum memory the suite needs. Docker's Linux VM
reported 15.47 GiB of RAM despite the 16-GiB container limit.

That observation explains the earlier OOM results in our full public-test
schedule. The task metadata specifies 8 GiB, so this diagnostic does not make
Wazero ready under the published resource limit. The official survey remains
unchanged at **81/113**. We have not inspected or run held-out verifier tests.

The streaming Go-to-CTRF converter also completed on the full output. Its
compact report is 25,165,136 bytes, within the existing 32-MiB report bound,
and the runner parsed all 155,967 test outcomes. The converter and container
were cleaned up through the runner's normal cleanup path.

Before running, Docker had no containers or build cache to remove. We deleted
five unused older Checkov versions (`3.3.17` through `3.3.21`) and `hello-world`,
reducing image storage from approximately 116.2 GB to 112.9 GB. The current
Checkov version, Python test image, benchmark images and both data volumes were
retained. Deleted image versions can be restored by pulling them again.

[The diagnostic summary](../experiments/deepswe/wazero_memory_diagnostic_2026_10_05.json)
records the pins, resource settings, counts and hashes of the local execution
record and report. Large raw artifacts stay outside the repository under
`output/deepswe-diagnostics/wazero-16g/`, beside this checkout. They are separate
from `output/deepswe-survey/survey.jsonl`.

The subsequent [8-GiB retries](wazero-8g-retries-2026-10-06.md) tried serial
package/test execution and then earlier Go garbage collection. Both ended in
OOM, so neither supplied a passing baseline at the published resource limit.
