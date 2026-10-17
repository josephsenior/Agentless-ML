# KGateway: full schedule with 8-GiB scratch

> Development record. See [the documentation guide](../README.md) for current status.

KGateway was previously blocked because Go exhausted the runner's 4-GiB
temporary filesystem while compiling. The public task configuration declares
20 GiB of storage. To test whether our stricter `/tmp` cap was the cause, the
unchanged public `go test -json -count=1 ./...` schedule was rerun once with
only the disposable `/tmp` tmpfs raised to 8 GiB. The pinned image and base
commit were unchanged; memory remained 8 GiB, CPUs 2, network disabled, PID cap
2048, and the timeout 30 minutes.

The full schedule completed in 658.4 seconds and produced 1,057 report IDs:
**1,017 passed, 40 failed, 0 skipped**. It therefore provides a regression
inventory under the readiness rule, but is not an all-passing baseline. The
40 failures remain in the report and must count as regressions when comparing
candidate repairs.

The survey now records this task as ready (**111/113 overall**). The 8-GiB
scratch allowance is explicit in the task override and remains below the
task's declared 20-GiB storage. This is readiness under a labeled scratch
setting, not evidence that the same build fits in 4 GiB. Full evidence:
`experiments/deepswe/kgateway_full_schedule_8gib_tmpfs_2026_10_12.json`.
Raw artifacts are under
`../output/deepswe-survey/survey/kgateway-consistent-hash-policy/logs/agentless-ml-d493179835d846c986c648cd89f54db1/`.

No held-out tests or solutions were used.
