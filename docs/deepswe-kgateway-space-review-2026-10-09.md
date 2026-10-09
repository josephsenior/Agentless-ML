# KGateway: temporary build-space failure

The saved baseline stopped because Go compilation exhausted our **4-GiB
`/tmp` mount**. Its image already has the required Go toolchain and an accessible
module cache. This is not the hidden-cache issue seen in GoReleaser or the
missing-dependency issue seen in Cliffy.

No suite was rerun, image built, limits increased or test configuration changed
in this inspection. KGateway remains unready; canonical readiness is **100/113**.

## Evidence from the stopped run

Task: `kgateway-consistent-hash-policy`.
Public base: `7abc5278782e3280fec8292b39807ec1b537eaf4`.
Pinned image:

```
sha256:a4f7250f435dd05fa354c8ea5f54e3d0228678f5203887d98863c5da7ceaf1b9
```

The existing command ran the full `go test -json -count=1 ./...` plan with
`GOCACHE=/tmp/go-build`. It shared the 4-GiB mount with the candidate checkout,
temporary compilation/linking work and command/report files.

The retained stderr contains concrete compilation failures:

```
helm.sh/helm/v3/pkg/action:
compile: writing output: write $WORK/b1833/_pkg_.a: no space left on device

.../extensions2/plugins/sandwich:
write /tmp/go-build817442992/b2111/importcfg: no space left on device

.../extensions2/plugins/kubernetes:
write /tmp/go-build817442992/b2113/importcfg: no space left on device
```

The run then failed report conversion with
`invalid character 'T' after object key:value pair`, followed by exit 125.
The recorded execution is `harness_error`, about 292.4 seconds, with zero
accepted report cases. The converter error is a second observed failure, not
proof that the suite completed. The raw Go event stream was not retained, so
this inspection cannot establish the exact malformed bytes or prove their
cause. Do not repair malformed events into a passing partial report.

The underlying build-space failure is established directly by the compiler
messages, independently of that reporter problem. There is no retained
resource journal establishing the precise peak, byte shortfall, or which
combination of cache and working files consumed the mount.

## What the pinned image provides

A disposable, offline, read-only inspector confirmed:

- `go version go1.26.1 linux/amd64`, matching public `go.mod`.
- `GOMODCACHE=/root/go/pkg/mod`, approximately **2.1 GB** on disk.
- `GOCACHE=/root/.cache/go-build`, approximately **59 MB** on disk.
- Default `GOTOOLCHAIN=auto`; no special `/tmp` module-cache environment.

Both cache paths are outside the mount covering `/tmp`. The module cache is
therefore not copied into or hidden by that scratch mount. Its contents being
accessible is not proof that every future dynamic dependency is covered, but
the saved failure is compilation ENOSPC, not a missing-toolchain download.

The public Dockerfile downloads modules and installs the report helper. It
does not warm the main repository's complete build/test graph. Our runner
also redirects the writable build cache to fresh `/tmp/go-build` instead of
seeding it from the image's small cache. This makes the baseline a cold build
in the relevant writable cache. Copying the existing 59-MB cache might reuse
some artifacts, but there is no evidence that doing so alone makes the build
fit. Relocating the module cache would not address this failure.

The sealed Git tree has **2,066 tracked blob entries**, totalling
**15,683,895 bytes** (about 15 MiB). This is raw tracked content, not a measured
filesystem allocation, but rules out a multi-gigabyte source checkout as the
obvious explanation. The large data in the recorded errors are compiler
archives and import configuration from the dependency graph.

## Our limit versus the published configuration

The public task config declares `storage_mb=20480`; our execution record
declares `tmpfs_mb=4096`. The former is the task's environment storage request,
not proof of 20 GiB of free `/tmp` in an upstream run. The latter is our actual
writable scratch mount cap. We are testing under a stricter scratch condition;
the failure is not evidence that the benchmark's own environment cannot run.

The existing plan has no e2e build tag and covers the default full package
graph. The public Makefile documents a separate tagged e2e condition and its
unit/coverage recipes use other runner and reporting flags. This inspection
does not claim our plain Go plan reproduces every CI race/coverage/retry flag,
and does not authorize narrowing its packages to reduce space.

## Next bounded check

Before another full attempt, measure a **compile-only full-package diagnostic
with one compiler worker**, under the same image, 4-GiB scratch and other caps.
Retain periodic scratch/cache/work-directory sizes and memory events. This
tests whether reducing concurrent build work can fit without increasing space
or excluding packages. Use an actual compile-only command: merely selecting
zero test names can still execute initialization and `TestMain`.

At the time of this inspection, this was a proposed diagnostic, not a
demonstrated fix, and had not been started.
The subsequently approved [five-minute check](deepswe-kgateway-compile-diagnostic-2026-10-09.md)
has now reached its cutoff with 1.88 GiB highest sampled scratch use, without
finishing compilation. It does not establish that the full build fits.
If retained build artifacts alone exceed the mount, concurrency reduction will
not solve that total-space problem. Resource changes or a deliberately warmed
separate environment would need their own explicit assessment and approval.

Original evidence:
`../output/deepswe-survey/kgateway-consistent-hash-policy/logs/agentless-ml-46399de0b37b4c559c9f81dec7c1b354/`.
Only public task configuration, public repository files, saved execution
artifacts and image toolchain/cache paths were inspected. No held-out tests or
solutions were read. The owned inspection container was automatically removed.
