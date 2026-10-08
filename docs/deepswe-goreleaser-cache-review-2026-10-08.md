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

The original failure artifacts remain under
`../output/deepswe-survey/goreleaser-retry-publish-auditing/logs/agentless-ml-8d8e12ec5326429abef093a9e2481eff/`.
Readiness remains **100/113**.
