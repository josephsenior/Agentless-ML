# DeepSWE scratch and swap: Wazero and Numba

The earlier survey runner stored both the checkout and build output in a
4-GiB `/tmp` tmpfs and explicitly disabled swap. Those choices tightened the
environment beyond the task's RAM and CPU settings: tmpfs data consumes
container memory as well as having its own size limit.

For these two tasks, the registered override now uses an anonymous Docker
volume at `/tmp` and leaves swap at Docker's default. This follows the local
Pier Docker backend's memory mapping. Each task still has 8 GiB of RAM,
two CPUs and a 1,800-second command timeout. Images, public schedules, offline
networking, read-only root, dropped capabilities and the PID limit are retained.
Other tasks retain their existing settings.

The volume is removed with its container. It uses Docker's disk rather than
RAM and has no separate 20-GiB quota; the local Pier Docker backend likewise
does not enforce the declared storage allowance. Docker reported a 16-GiB
combined memory/swap allowance, while the host actually had 4 GiB of swap.
The allowance therefore does not guarantee 8 GiB of available swap.

The survey, single-task public-test command and recorded workflow all forward
the same override. Execution records include `scratch_mode`, `scratch_mb`
(null for a volume), `swap_policy` and the existing memory/CPU/time limits.

## Wazero

The unchanged `go test -json -count=1 ./...` schedule completed successfully:
155,928 passed, zero failed and 39 skipped. The command record reports
314.52 seconds; the complete survey operation took 329.1 seconds.

All 39 skips are explicit in the pinned repository's tests. The backend's
`TestE2E` skips 38 cases on amd64 when an amd64 expected output is absent
(`internal/engine/wazevo/backend/backend_test.go:2383`). The remaining TinyGo
directory-read case cites an upstream issue in
`imports/wasi_snapshot_preview1/wasi_stdlib_test.go:128`. These are skips, not
failed tests or extra exclusions introduced by this setup.

Evidence directory, relative to the checkout:
`../output/deepswe-survey/wazero-multi-module-snapshots/logs/agentless-ml-02ad4ac790c64a60a8d79539d0068ad7/`.

## Numba

One fresh full native run used base
`5781334aa654972fdc749003e7c1e93e6d277110` and pinned image
`sha256:d30747d56f59cb61bb9a4e87ba8dc4df29ccbb471a1a1146f20d5d9d58fa90ac`.
Docker was initially stopped; the first startup check ran no tests. After
starting Docker and verifying the image, the full baseline was launched once.

`python setup.py build_ext --inplace` succeeded. All seven candidate import
checks passed, and the default `runtests.py` schedule started. This used the
registered native default, without the earlier diagnostic's `-m 2` option.
The runner stopped it at the configured 1,800-second command timeout. The
execution record's 1,826.33 seconds includes surrounding runner work; the
complete survey operation took 1,841.1 seconds. No complete JUnit report was
accepted, and no partial results became a regression inventory.

The last live memory check, at 20:54:56 UTC, recorded a kernel memory peak of
5,294,567,424 bytes (4.93 GiB), with zero OOM and OOM-kill events. These are
sampled observations rather than a continuous resource journal or a final
peak measurement. The result is `timeout`, not an observed memory failure.
Source-build and import success do not establish full-suite readiness.

The owned container and anonymous volume were removed. Retained evidence:
`../output/deepswe-survey/numba-stencil-boundary-modes/logs/agentless-ml-cfdadaf8fe7542c6896f247d0b75a7c6/`
contains `execution.json`, `stdout.log` and `stderr.log`. There is no final
test report. No further full retry was started.

The latest survey has **112/113 ready**, with Numba the only remaining task.
That count describes usable public regression inventories, not repair scores.

The subsequent [thread inspection](deepswe-numba-threads-2026-10-12.md) records
the requested BLAS-only cap and discovery checks. That change was made after
this timed-out attempt; there has been no new full baseline with the cap.

The focused Docker, DeepSWE execution, environment and Numba recorder checks
passed: **203 passed, 12 skipped**. The skipped checks require explicit local
Docker or pinned-repository integration opt-ins. The three public execution
entry points also passed syntax checks, and `git diff --check` was clean.
