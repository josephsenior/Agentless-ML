# Helm public baselines

Both Helm tasks completed the unchanged public Go schedule, `go test -json
-count=1 ./...`, using their original pinned images and the
[scoped container fixture setup](deepswe-helm-container-fixtures-2026-10-10.md).
Each task ran once, sequentially, without retries or target filtering.

| Task | Passed | Failed | Skipped | Execution time |
|---|---:|---:|---:|---:|
| `helm-array-merge-strategies` | 2,239 | 58 | 10 | 304.21 seconds |
| `helm-unified-manifest-stream` | 2,239 | 58 | 10 | 280.64 seconds |

Both commands exited 1 and produced valid reports containing 2,307 test IDs.
The official survey marks them ready because they ran and produced passing
regression inventories. This does not mean the whole suite passed, nor that a
candidate solves either benchmark task. The 58 failed IDs match between runs;
the failure causes were not investigated in this step.

The six fixture-related report IDs passed in both runs: the two
`TestLoadDirWithDevNull` tests, `TestCopyFileSymlink` itself, and its three
relative, dangling and Windows-literal child cases. Successful reconstruction
of all four special links is recorded in each `execution.json`.

## Regression-matching follow-up

Comparing the reports also exposed four passing `TestSave` child IDs containing
random temporary-directory names: two each in `internal/chart/v3/util` and
`pkg/chart/v2/util`. Their `outDir=/tmp/TestSave<digits>/001` names vary across
runs. The survey's readiness definition does not check cross-run ID stability.
At this checkpoint, these four IDs needed a narrow normalization policy before
candidate regression matching. No IDs or reports were rewritten
in this baseline step. The later approved
[stable-ID policy and report replay](deepswe-helm-stable-test-ids-2026-10-10.md)
now address these four cases without changing tests or raw evidence.

## Protections and records

Live inspection of both owned containers confirmed no network, read-only root,
all capabilities dropped, no-new-privileges, no host binds, no privileged mode,
no added hosts or published ports. Limits stayed at 8 GiB RAM with no extra
swap, two CPUs, 2,048 PIDs, 4 GiB temporary storage and a 1,800-second command
cap. Both containers were removed after completion.

No images, test sources, command flags, corpus pins, environment registrations
or held-out scoring rules changed. No model calls or hidden tests were involved.
The official append-only survey now shows **108/113 ready**: 105 with original
images and three with previously registered modified environments.

Five tasks remain unready: KGateway and Pwntools (harness errors), Numba
(timeout), Pebble and Wazero (out of memory). Previously parked tasks stay parked.

[Compact evidence](../experiments/deepswe/helm_public_baselines_2026_10_10.json)
records image IDs, limits, timings, artifact paths and SHA-256 hashes. Raw
execution records and reports remain under `../output/deepswe-survey/survey/`.
