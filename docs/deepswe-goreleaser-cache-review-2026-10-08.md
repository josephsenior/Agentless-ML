# GoReleaser: image caches hidden by the temporary mount

After parking Numba, the next task reviewed was
`goreleaser-retry-publish-auditing`. Its latest survey result is still
`harness_error`; no new baseline was launched during this review.

## What stopped the saved baseline

The saved command tried to download Go 1.26.1 while offline, both for the tests
and for report conversion. The candidate's public `go.mod` requires that
version. This is not evidence that the published image lacks it.

The public environment Dockerfile sets `GOMODCACHE=/tmp/gomodcache`,
`GOCACHE=/tmp/gocache` and `GOTOOLCHAIN=auto`, then downloads modules and warms
build caches during image construction. Our runner mounts a fresh writable
tmpfs over `/tmp`. That hides the image's cached toolchain and dependencies.
Setting the build cache to `/tmp/go-build` does not restore the module cache.

## Read-only image inspection

The inspected image was the existing pinned image:

```
sha256:778c43a00bb317e8e0b266b212b187be7765a12dbdadde3ba2f4bceba9c40080
```

A disposable inspector used no `/tmp` overlay and no host mounts, with
network disabled, a read-only root, dropped capabilities, no-new-privileges,
8-GiB memory, two CPUs and the 2,048 PID limit. It read only toolchain/cache
paths, not held-out tests or solutions. It was automatically removed.

The image contains:

- The default local Go installation, version 1.25.5.
- The required `golang.org/toolchain@v0.0.1-go1.26.1.linux-amd64/bin/go`.
- Approximately 3.9 GB of module cache and 1.4 GB of build cache, as reported
  by `du -sh`.

Copying both complete caches into the existing 4-GiB tmpfs cannot fit. The
inspection does not establish the size of a sufficient smaller subset or
whether the full test schedule would complete after cache access is restored.

## Approved separate diagnostic

Use a separately labelled derivative of this exact pinned image to relocate
its existing caches outside `/tmp`. No dependency download, toolchain upgrade,
source patch or extra internet access is needed for the relocation itself.
Keep the candidate checkout as the source under test and keep writable build
outputs under the existing temporary mount. Confirm that Go can use the
relocated module cache read-only before attempting the unchanged public
schedule.

The user approved building and running this separate diagnostic. It remains
a substituted environment, not the canonical pinned-image baseline. Do not
silently promote its eventual result into the official survey, increase
limits, downgrade `go.mod`, or replace candidate code with image-built code.

The recipe is `experiments/deepswe/goreleaser/Dockerfile.cache`. It moves the
existing caches to `/opt/agentless-go`, explicitly selects the image's existing
Go 1.26.1 binary, disables proxy downloads and automatic toolchain switching,
and builds with `--network=none --pull=false`. Verify the parent ID above before
building; the build log also records the resolved parent digest.

```powershell
docker build --pull=false --network=none -f experiments/deepswe/goreleaser/Dockerfile.cache -t agentless-ml/goreleaser-cache:2026-10-08 experiments/deepswe/goreleaser
$diagnosticImageId = docker image inspect --format '{{.Id}}' agentless-ml/goreleaser-cache:2026-10-08
.\.venv\Scripts\python.exe tools/run_goreleaser_cache_diagnostic.py --image-id $diagnosticImageId --check-only
.\.venv\Scripts\python.exe tools/run_goreleaser_cache_diagnostic.py --image-id $diagnosticImageId
```

The first command check uses `go list -m all` from a fresh candidate checkout
with the usual read-only root, offline network and 4-GiB `/tmp` mount. It is
not a test baseline. Full mode seeds the writable Go build cache from the
image's existing content-addressed cache, then preserves the current public
Go plan (`go test -json -count=1 ./...`) and CTRF converter. This is the
survey's existing full-package plan, not an assertion that it reproduces
every race/coverage flag in the repository's separate Taskfile recipe.
Go still compiles candidate source according to its cache keys; test result
caching remains disabled. The wrapper adds a container-side 1,800-second
deadline covering preparation, tests and report conversion, as well as the
unchanged host timeout. It has no automatic retry or official survey write.

Focused verification passed **94 tests**, with four existing opt-in checks
skipped. No benchmark result is implied by those unit tests.

## Result

The image built offline from the verified parent. The saved recipe now also
pins that same parent digest directly in its default `FROM` argument. The
derivative image ID is:

```
sha256:a02ee6ffddb93fa736a2d8d345669d966a3c15db99d4333f151eeb1c08fed085
```

The Go binary's SHA256 is identical before and after relocation:
`548e61b2d08ae52043be2f1924ed3c1d2b2c41967e360f3e317667f6fa912fc2`.
Both checksum inspections were disposable, offline, read-only containers with
the same CPU/memory/PID protections. No replacement toolchain was installed.

The read-only module check passed in **28.0 seconds**, including enumeration
of the full module graph and verification of Go 1.26.1, `GOTOOLCHAIN=local`
and `GOPROXY=off`. It wrote no test report and is not counted as a public test.

One full attempt then finished in **303.6 seconds** with native exit **1** and
an accepted CTRF report: **2,907 passed, 46 failed, 47 skipped**, or 3,000 report
IDs. Go reports parent tests and subtests separately; these are report IDs,
not a claim about 3,000 independent assertions. The result is `fail`, not an
all-passing baseline. No tests, flags, exclusions or failures were changed.

The failure IDs include builder/tool checks, Git and changelog cases, Go module
proxy cases, and release-provider cases. Their exact assertion failures have
not been diagnosed: the standard converter retains terminal outcomes, not the
full Go event stream. Do not attribute all 46 failures to networking or assume
they are harmless. This diagnostic deliberately changes module/toolchain
environment variables, which subprocess-based tests may also inherit.

Resource probes during execution saw temporary usage rise to 3.3 GB before
dropping after compilation. The largest observed cgroup memory peak was
4,311,711,744 bytes (4.02 GiB), with zero OOM events in the observed counters.
These were occasional observations, not a continuously retained final peak.
There was no timeout, OOM classification or reported setup error in the final
execution record. The owned container and temporary candidate clone were
cleaned up normally, and no retry was launched.

Evidence remains in `../output/deepswe-survey/goreleaser-cache/logs/`:

- `agentless-ml-23d8067e01b64074a451f705d9160c2f/`: module check.
- `agentless-ml-a6549b840b2d4938bf48313ad64a6e7d/`: full attempt, including
  `execution.json`, `cache-diagnostic.json`, `report.json` and command logs.

The substitution removed the demonstrated cache-access blocker and yielded a
passing regression inventory for this labelled environment. It did **not**
recover the canonical pinned-image baseline. The official survey, overrides
and corpus pin remain unchanged at **100/113 ready**. Numba remains parked.

The original failure artifacts remain under
`../output/deepswe-survey/goreleaser-retry-publish-auditing/logs/agentless-ml-8d8e12ec5326429abef093a9e2481eff/`.
Readiness remains **100/113**.

Follow-up: the approved [registration and official refresh](deepswe-goreleaser-registered-readiness-2026-10-10.md)
reproduced the same 2,907 passed, 46 failed and 47 skipped ID sets. GoReleaser
is now ready in the explicitly registered cache environment, bringing overall
readiness to 103/113. The native result is still FAIL/exit 1, and the earlier
diagnostic and published image pin remain unchanged.
