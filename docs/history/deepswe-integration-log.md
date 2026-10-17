# DeepSWE integration checkpoints

> Development record. See [the current DeepSWE guide](../deepswe.md) for current readiness and commands.

These checkpoints were previously embedded in the integration guide. Counts and
next-step statements describe the point at which each investigation was recorded.

## What is not implemented

Current public-baseline readiness is **112/113**, with only Numba remaining.
Of those ready tasks, 108 use their published pinned images; Testem, Cliffy,
GoReleaser and Pwntools use explicitly labelled, verified modified environments. The original corpus
pins and held-out scorer are unchanged. The chronology below retains earlier
counts as historical checkpoints.

Both Helm tasks now have an exact-pin, container-only setup for their four
special public fixture links. The [short link-behavior diagnostics](deepswe-helm-container-fixtures-2026-10-10.md)
passed in both original images, with general unsafe-link rejection and Docker
protections unchanged. Both unchanged public baselines then completed with
2,239 passes, 58 failures and 10 skips each, bringing official readiness to
108/113. All fixture-related tests passed. The four passing child IDs containing
random temporary-directory names now have an opt-in
[stable matching policy](deepswe-helm-stable-test-ids-2026-10-10.md), verified by
replaying both raw reports without changing outcomes. Ready still does not mean
an all-green suite.

Pebble's [short single-worker compile diagnostic](deepswe-pebble-valblk-compile-2026-10-10.md)
successfully compiled the previously killed `sstable/valblk` test binary, with
about 688 MiB peak cgroup memory and no OOM events or observed Docker cutoff.
This isolated-package check is not a baseline or proof that the full schedule
fits; at that checkpoint Pebble remained unready and readiness was 108/113.
The later approved [full-schedule single-worker diagnostic](deepswe-pebble-full-single-worker-2026-10-10.md)
still OOMed: 8 GiB peak, one cgroup kill and Docker `OOMKilled=true`. This confirms
a memory kill in that attempt, rather than merely a connection cutoff. No
accepted inventory or official survey update resulted.

Wasmi's normal workspace test build embeds public fixtures from two submodules.
Its setup now verifies both pinned image submodules and supplies only 352 pinned
WAST files to the temporary candidate directories. The existing nextest baseline
passed all 791 tests, including 633 in `wasmi_wast`. The benchmark-only submodule
stays empty; no image Rust source or compiled artifacts are copied.

Tomlkit's normal public schedule needs the `tests/toml-test` submodule data.
Its runner now verifies the exact submodule revision and complete tracked-file
manifest in the original image, then supplies only the fixture index and its
referenced TOML/JSON files inside the temporary candidate checkout. The fresh
unchanged baseline passed all 964 cases, including all 680 conformance cases.
No source code, test code or Git metadata is copied from the image, and no
submodule fetch or modified image is needed.

Adaptix's submodule refusal was stale: the current workspace provider leaves
its performance-data submodule uninitialized and the normal public schedule
runs without it. A task-specific import-path fix now selects candidate helpers
and verifies their origins before pytest. The fresh run passed with 2,824 passes,
28 skips, no collection errors and exit 0. Adaptix's report declaration now opts
into collision-checked Python-repr address normalization. All 2,852 case IDs and
outcomes match across the previous and fresh processes; raw XML stays unchanged.

- **Runner and environment gaps.** The [4 October review](deepswe-runner-review-2026-10-04.md)
  recovered four of the six missing-runner tasks. The subsequent
  [Yjs reporting check](deepswe-yjs-reporting-2026-10-04.md) recovered a fifth,
  using its original lib0 runner. Cliffy's Deno suite cannot load offline
  with the published image's incomplete dependency cache.
  The [harness review](deepswe-harness-review-2026-10-04.md) then recovered
  Kea, SQL Formatter, mnamer and Vitest through their public setup steps.
- **Baseline eligibility across the corpus.** The survey has attempted all 113
  pinned tasks. The [28 September triage](deepswe-survey-2026-09-28.md) records
  which 71 had a usable baseline and why the other 42 did not. The 4 October
  checks, including Yjs, the harness review, and the Python symlink-task rerun,
  brought the count to 81. The subsequent
  [contained-symlink reruns](deepswe-symlink-reruns-2026-10-06.md) recovered
  six more public baselines, bringing the count to 87/113. The
  [Pest bootstrap step](pest-bootstrap-baseline-2026-10-06.md) then recovered
  another baseline, bringing the count to 88/113. The
  [Arktype and Clack runner review](deepswe-delegated-runners-2026-10-06.md)
  then recovered both delegated scripts, bringing the count to 90/113.
  [Optique and Valibot](deepswe-optique-valibot-runners-2026-10-06.md) recovered
  the last two missing-runner tasks, bringing the count to 92/113.
  The [Meriyah fresh-preparation retry](deepswe-meriyah-baseline-2026-10-08.md)
  then passed the complete public Vitest schedule in its pinned published image,
  bringing the latest count to **93/113**, with 20 tasks still not ready.
  Pwntools is parked; tasks outside these reviews retain their earlier outcomes.
  The [Drizzle and LangChain repository retries](deepswe-repository-retries-2026-10-08.md)
  clear both old preparation failures and verify their published images.
  Drizzle needs its delegated Turbo schedule (`no_runner`); LangChain's
  root-level pytest invocation fails during collection (`harness_error`).
  Neither adds a usable baseline, so readiness remains 93/113.
  The subsequent [package-level LangChain invocation](deepswe-package-schedules-2026-10-08.md)
  follows the public core unit schedule and verifies candidate imports. It
  yields 1,664 passing report IDs, bringing the latest count to **94/113**
  (19 tasks not ready); its 21 baseline failures remain visible.
  The same [package-schedule follow-up](deepswe-package-schedules-2026-10-08.md)
  implements Drizzle's public Turbo graph with its build/type prerequisites,
  pinned offline tools and all nine namespaced package reports. Its completed
  run yields 3,100 passing IDs and brings the latest count to **95/113**
  (18 tasks not ready). Failed and skipped baseline cases remain visible;
  readiness does not mean either complete suite is all-green.
  [Mobly's missing-image retry](deepswe-mobly-baseline-2026-10-08.md) then
  verifies the pinned published image and passes its unchanged public suite:
  804 passing IDs, two skipped, zero failed. The latest count is **96/113**
  (17 tasks not ready), with no remaining `no_image` records.
  [Boa's temporary-workspace retry](deepswe-boa-baseline-2026-10-08.md)
  completes without its old Windows cleanup lock and yields 1,609 passing IDs.
  One nested macro compilation still fails on temporary-storage exhaustion;
  it remains visible and does not empty the usable inventory. The latest count
  is **97/113** (16 tasks not ready), with no remaining `survey_error` records.
  [Igel's working-directory correction](deepswe-igel-baseline-2026-10-08.md)
  starts pytest from `tests/test_igel` before Igel binds its output paths.
  Both unchanged public tests pass in the pinned image. The latest count is
  **98/113** (15 tasks not ready), with three `no_passing_tests` records left.
  [Skrub's public-package baseline](deepswe-skrub-baseline-2026-10-08.md)
  uses its supported writable data directory and declared package schedule.
  The report contains 2,859 passing IDs, four failures and 357 skipped or
  expected-failure cases. The latest count is **99/113** (14 tasks not ready);
  only Eicrud and Numba still have `no_passing_tests` records.
  [Eicrud's offline MongoDB baseline](deepswe-eicrud-baseline-2026-10-08.md)
  rebuilds its candidate CLI and generated clients and starts the image's
  existing database under `/tmp`. All 24 public MongoDB suites run: 147 passing
  and 69 failed report IDs. The latest count is **100/113** (13 tasks not ready);
  Numba is the only remaining `no_passing_tests` task.
  [Numba's candidate-build and native-runner review](deepswe-numba-baseline-2026-10-08.md)
  verifies source-built extensions and candidate imports, then preserves the
  public runner's hardware-aware discovery. Its full serial schedule times out
  at the unchanged 30-minute limit without a complete report. Numba remains
  unready, now classified as `timeout`; the latest count stays **100/113**
  (13 tasks not ready). No latest `no_passing_tests` records remain, which does
  not mean every task now has a passing baseline.
  The separate [two-worker resource sample](deepswe-numba-two-worker-diagnostic-2026-10-08.md)
  exercised parallel-result recording and worker recycling, with a 1.54-GiB
  observed peak and no OOM events. Host/container timing disagreed; this sample
  does not establish full-suite runtime or change the official baseline.
  A clean repeat stopped at the intended five-minute cutoff, with at least
  350 completions, a 1.42-GiB observed peak and no OOM events. It resolved the
  timing discrepancy for that short window, not full-suite readiness.
  The subsequent [full two-worker attempt](deepswe-numba-full-attempt-2026-10-08.md)
  was interrupted without a recoverable report. Its completion is unknown;
  neither readiness nor a parallel-runtime conclusion was recorded.
  An explicitly approved fresh full attempt then stopped at the container's
  unchanged 30-minute cutoff, with at least 1,950 completions, a 4.99-GiB
  observed memory peak and no recorded OOM events. No complete report was
  accepted; readiness stays **100/113**. Its raw exit 124 is retained, and the
  full-attempt review documents the host sampling gap rather than claiming
  an uninterrupted runtime measurement. No further retry was started.
  Numba is now explicitly parked at the user's request under the current
  limits, not excluded from the dataset. Work has moved to
  [GoReleaser's hidden image caches](deepswe-goreleaser-cache-review-2026-10-08.md).
  Its approved separate cache-relocation image passed the offline module check
  and completed the unchanged full-package Go plan in 303.6 seconds, with
  2,907 passed, 46 failed and 47 skipped report IDs. No limits or test exclusions
  changed. This substituted-image inventory is not a canonical readiness
  update; the official count remains **100/113**.
  The later approved [cache registration and official refresh](deepswe-goreleaser-registered-readiness-2026-10-10.md)
  retained the exact image and cache-seeding setup and reproduced all passing,
  failed and skipped ID sets in a fresh full attempt. GoReleaser is now ready
  with 2,907 passed, 46 failed and 47 skipped; the native result remains FAIL,
  exit 1. Overall readiness is **103/113**, including three labelled modified
  environments. No failures were hidden or reclassified as passing.
  [Cliffy's cache inventory](deepswe-cliffy-cache-review-2026-10-08.md) confirms
  a different problem: eight declared JSR packages have no entries in its
  published Deno cache. The first saved failure is missing `@std/io` metadata.
  No dependencies were downloaded, image supplemented or baseline rerun in
  that inspection; readiness remains unchanged.
  The [public dependency audit](deepswe-cliffy-public-dependencies-2026-10-09.md)
  subsequently verified 956 files across 28 explicit package/version pairs,
  including missing dependency graphs and the image's existing versions.
  No image was built, tests run or canonical readiness changed. Full offline
  import resolution and Deno 2.0.0 compatibility remain the next checks.
  The approved [cache-image and offline graph check](deepswe-cliffy-offline-graph-2026-10-09.md)
  then identified and checksum-verified the image-resolved assert 0.225.3,
  taking the artifact set to 29 version pairs / 1,011 files. The separate image
  passed native no-run discovery and type checking for all 119 candidate test
  modules in 21.3 seconds, offline with unchanged Deno and limits. No tests
  executed, and the official count remains **100/113**.
  Its subsequent approved [full public baseline](deepswe-cliffy-public-baseline-2026-10-09.md)
  passed in 58.8 seconds with 822 native tests and 76 steps. The raw XML has
  898 passing entries; existing duplicate-label normalization yields 878 IDs.
  No tests were filtered, no failures hidden and no runtime protections changed.
  This completes the labelled supplemented-image baseline, not a canonical
  survey update; the original-image count stays **100/113**.
  The later approved [cache registration and official refresh](deepswe-cliffy-registered-readiness-2026-10-10.md)
  rechecked all 1,067 saved artifacts and marked Cliffy ready after another
  unchanged full run passed with 878 normalized IDs. Overall readiness is now
  **102/113**, including two explicitly registered modified environments;
  original-image readiness remains 100/113.
  [KGateway's build-space inspection](deepswe-kgateway-space-review-2026-10-09.md)
  confirms compiler ENOSPC on our 4-GiB scratch mount. Its Go 1.26.1 toolchain
  and 2.1-GB module cache are already accessible outside `/tmp`; the image's
  build cache is only 59 MB and is not seeded by the current runner. No retry
  or resource change was made during that inspection. The subsequently approved
  [five-minute compile-only check](deepswe-kgateway-compile-diagnostic-2026-10-09.md)
  used one build worker and reached its cutoff without a space error; highest
  sampled scratch use was 1.88 GiB. Compilation was incomplete, so this is not
  proof the full graph fits, a baseline, or a readiness change.
  The approved [full compile attempt](deepswe-kgateway-full-compile-2026-10-09.md)
  encountered a 77-minute monitoring gap consistent with host suspension and
  was stopped. It provides no usable uninterrupted full-build timing result;
  no automatic repeat or readiness change was made.
  A separately approved [keep-awake repeat](deepswe-kgateway-awake-compile-2026-10-09.md)
  ended with build failures after 317.9 seconds and no long sampling gap.
  Scratch reached 98% in the last probe, with no observed OOM. The exact compiler
  error was not retained; this is consistent with the prior space blocker,
  not direct new ENOSPC evidence. One build worker did not yield a successful
  compile, and canonical readiness remains unchanged.
  KGateway is now explicitly parked under these limits (work priority only).
  After work resumed, the [full public schedule with 8-GiB scratch](deepswe-kgateway-8gib-tmpfs-full-2026-10-12.md)
  completed with 1,017 passes and 40 visible failures. The 8-GiB `/tmp` stays
  within the task's declared 20-GiB storage; the other limits and full schedule
  were unchanged. KGateway is now ready under that labeled scratch setting,
  bringing readiness to **111/113**.
  The next [Testem setup inspection](deepswe-testem-setup-review-2026-10-09.md)
  found no discoverable Firefox in its pinned image, despite the public CI
  installing it and public Mocha tests requiring Headless Firefox. No retry or
  image change was made; the saved timeout's precise cause remains unproven.
  Its subsequent [pre-build verification](deepswe-testem-firefox-verification-2026-10-09.md)
  authenticated Firefox ESR 140.17.0 and 87 Debian package archives. Extracted
  payloads cover all 21 missing ELF dependency names; runtime compatibility is
  untested. APT proposes two existing-library upgrades as well as 85 new packages,
  so this is not an implicitly approved minimal image recipe. No image was built
  and no browser or tests ran; canonical readiness is unchanged.
  An [offline upgrade review](deepswe-testem-upgrade-review-2026-10-09.md) found
  a valid smaller plan: preserve both existing libraries and explicitly select
  Debian's `dbus-x11` session-bus provider. It proposes 71 new packages, no upgrades
  and no removals. Seventy archives are already verified; the new `dbus-x11`
  archive and revised static dependency coverage remain to be checked before
  any build. No installation, download, browser execution or test retry occurred.
  The subsequent approved [revised-set verification](deepswe-testem-no-upgrade-verification-2026-10-09.md)
  acquired and verified the one new `dbus-x11` archive, rehashed all 71 selected
  packages and checked 143 ELF files offline. No missing library names were
  found; `libudev1` and `libsystemd0` remain unchanged. This is static coverage,
  not a browser startup result, image build, test retry or readiness change.
  The approved [separate image and startup check](deepswe-testem-firefox-startup-2026-10-09.md)
  then added exactly the verified 71 packages without changing existing package
  versions. Headless Firefox rendered a local page offline with JavaScript under
  the original Docker protections. Namespace/GPU-probe warnings are retained;
  no sandbox-disable flag or protection relaxation was used. This is not a full
  public baseline. The subsequent [full public attempt](deepswe-testem-public-baseline-2026-10-09.md)
  ended in timeout without a report after an observed host/tool interruption.
  It is not a clean runtime measurement or a readiness change. The approved
  [uninterrupted repeat](deepswe-testem-public-repeat-2026-10-09.md) then completed
  in 370.937 seconds: 489 passed, three skipped, eight failed after normalization.
  Browser-result/timeouts and report-file failures remain; the separate image
  has a completed failing baseline, not a canonical readiness update.
  A [targeted Firefox trace](deepswe-testem-firefox-connection-2026-10-09.md)
  then observed no server requests in one existing public test. Synthetic
  connection controls succeeded with writable home/cache paths under either
  argument order, but not with the image home. No benchmark fix was applied.
  The [minimal-path follow-up](deepswe-testem-minimal-home-2026-10-09.md) found
  HOME alone sufficient, unlike cache-only or config-only. The same public
  test connected and completed its browser run with HOME alone, but still
  failed its exit-status assertion. No shared configuration or readiness change.
  The [reporter trace](deepswe-testem-qunit-failure-2026-10-09.md) captured
  `QUnit is not defined`: the public QUnit template loads version 1.20.0 from
  an external CDN unavailable offline. The follow-on
  [asset assessment](deepswe-testem-offline-assets-assessment-2026-10-09.md)
  verified the exact two files, including publisher JS SRI and upstream byte
  equality, and assessed a labelled loopback-only delivery condition. No service
  image was built or benchmark test started during that assessment. The approved
  [separate image and HTTP preflight](deepswe-testem-offline-assets-preflight-2026-10-09.md)
  then passed all nine native delivery/rejection checks offline under unchanged
  protections. The subsequent [single unchanged public test](deepswe-testem-offline-public-test-2026-10-09.md)
  passed in the labelled setup with exit code 0: its browser fixture had two
  passes and one declared skip. The approved [full schedule](deepswe-testem-offline-full-schedule-2026-10-09.md)
  then completed in 48.282 seconds with 496 passed, three skipped and one failed
  after normalization. The remaining todo fixture requests QUnit 2.9.2 assets
  outside the two-file allowlist. The subsequent
  [2.9.2 verification and targeted todo check](deepswe-testem-qunit-todo-2026-10-10.md)
  added the exact assets alongside 1.20.0 in another separate image. All 13
  delivery checks passed, and the unchanged todo test passed in 18.093 seconds.
  The subsequently approved
  [four-asset full schedule](deepswe-testem-four-asset-full-schedule-2026-10-10.md)
  passed in 61.734 seconds: 497 passed, three skipped and zero failed after
  normalization. The subsequent
  [registration and official survey refresh](deepswe-testem-registered-readiness-2026-10-10.md)
  reran the full schedule successfully through the shared tools and marked
  Testem ready, bringing overall readiness to **101/113**. Its environment
  stays explicitly labelled as modified; the published image pin is unchanged.
  The [Pwntools doctest review](deepswe-pwntools-doctest-2026-10-07.md) replaces
  its incorrect pytest invocation with the public Sphinx runner. The published
  image lacks Sphinx; a separately augmented diagnostic also exposed missing
  native tools and repeated stalls. Its interrupted run is not a completed
  baseline and does not change the 92/113 count.
  The follow-on [native-tool/SSH review](deepswe-pwntools-native-2026-10-07.md)
  verifies loopback SSH with the runner's capabilities still dropped. Selected
  public pages completed with one MSP430-toolchain failure; this augmented,
  non-root environment is still diagnostic evidence, not a full baseline.
  The [MSP430 follow-up](deepswe-pwntools-msp430-2026-10-07.md) verifies a
  checksum-pinned source-built toolchain: all 431 selected examples pass.
  The documented public Docker schedule completed with 42 passing and 12
  failing groups, using only its three documented page exclusions and our
  existing container restrictions. These derived-image results leave
  canonical readiness unchanged.
  The [RISC-V/patchelf follow-up](deepswe-pwntools-riscv-2026-10-07.md) adds
  two checksum-verified, version-pinned packages without upgrading the parent.
  The same schedule now has 44 passing and 10 failing groups; ELF and RISC-V
  shellcraft groups recovered. No exclusions or execution permissions changed.
  The [process-failure diagnosis](deepswe-pwntools-process-2026-10-07.md)
  reproduces a denied ASLR request, an upstream relative-path bug and a
  nonportable PID-1 expectation. No benchmark code or runner was patched;
  the 44/10 diagnostic result and canonical readiness remain unchanged.
  The [libcdb diagnosis](deepswe-pwntools-libcdb-2026-10-07.md) verifies local
  lookup while identifying missing historical library/package/debug data
  and an upstream provider-list mutation. No data snapshot or new image was
  added, and no public failures were hidden.
  The [public dependency audit](deepswe-pwntools-public-assets-2026-10-07.md)
  verifies all required lookup libraries, the complete symbol-query snapshot,
  matching debug files and pinned tool archives. Some original URLs are gone,
  but exact files remain available through provider/publisher fallbacks.
  That audit did not build an image. The subsequent
  [offline-data diagnostic](deepswe-pwntools-offline-2026-10-08.md) supplies
  those pinned dependencies in a separate image and passes all 42 libcdb
  examples. The unchanged public Docker schedule improves to 45 passing
  groups / 9 failing groups, with no new exclusions or permission changes.
  Canonical readiness remains 92/113.
  The separately approved [temporary host core-dump diagnostic](deepswe-pwntools-host-core-2026-10-08.md)
  restores native core retrieval and improves the same schedule to 46/8.
  It also introduces six ARM/QEMU failures, so it is not a general fix.
  The original WSL host setting was restored; readiness remains unchanged.
  The approved [non-colliding filename follow-up](deepswe-pwntools-noncolliding-core-2026-10-08.md)
  tests `core.native.%p` and passes all 107 core-file and 176 ROP examples.
  The same schedule improves to 47/7, with no new exclusions or container
  permission changes. The host setting was restored again; readiness stays 92/113.
  The [SSH filesystem follow-up](deepswe-pwntools-ssh-aligned-2026-10-08.md)
  uses a separate offline-derived image to align the public home path and
  SFTP creation mask. The unchanged filesystem page passes 148/149 examples,
  up from 144/149; its tmpfs block-allocation expectation remains failed.
  This is a selected-page result, not another full schedule or readiness change.
  A separate [offline HTTPS service diagnostic](deepswe-pwntools-services-2026-10-08.md)
  serves pinned genuine public data without external networking. The unchanged
  update page passes all 11 examples through a real cold HTTPS fetch; no update
  cache is seeded. A follow-up with the exact same image also passes all six
  unchanged public download examples through real HTTPS. These are separate
  selected-page runs, explicitly a modified environment, not a canonical
  readiness improvement or a new full-schedule result.
  The [shared HTTP/TLS follow-up](deepswe-pwntools-protocol-services-2026-10-08.md)
  passes all 164 context and 35 socket examples using real local connections.
  Sphinx also includes 219 passing related tube examples: 418 total, with zero
  setup/cleanup failures. This explicitly labelled three-host condition does
  not demonstrate live Google access or change canonical readiness.
  The [repository review](deepswe-repository-review-2026-10-04.md) found that
  all 22 old unsupported-task trees are accepted by the current provider, but
  Linux symlink semantics and submodule requirements still need runtime checks.
  [Git-aware Linux snapshots](../git-aware-linux-snapshots-2026-10-04.md) now
  preserve contained relative links and Git executable modes. The Python
  symlink task now has a passing full public baseline. All 15 remaining
  contained-symlink tasks have since been revisited: six were recovered in that
  batch; Pest, Arktype, Clack, Optique and Valibot recovered five more.
  Four retain setup or memory blockers. Absolute-link fixtures remain
  unsupported, and three submodule-only tasks still need runtime checks.
  A separate [Wazero memory diagnostic](wazero-memory-diagnostic-2026-10-05.md)
  passed the full public schedule at a 16-GiB container limit, with observed
  memory above the published 8-GiB cap. It validates report conversion on the
  large suite but did not change readiness; it remains outside the current
  92/113 count.
  The subsequent [8-GiB retries](wazero-8g-retries-2026-10-06.md) also ended in
  OOM with serial execution and earlier garbage collection. The serial run
  identified the public `TestEngineInterpreter/huge_binary` stress test as an
  OOM victim under that earlier runner setup.
  The [2026-10-12 scratch/swap review](deepswe-scratch-swap-2026-10-12.md)
  replaces the RAM-backed checkout with disposable disk scratch and restores
  Docker-default swap for Wazero and Numba. Wazero's unchanged full public
  schedule completes under 8 GiB, two CPUs and 30 minutes: 155,928 passed,
  zero failed and 39 expected upstream skips. Numba builds and imports from
  candidate source but still times out without a complete report. Latest
  public-baseline readiness is **112/113**, with only Numba unready.
- **Workflow and scoring over many tasks.** The survey establishes each task's
  regression inventory, but running the workflow needs repair responses, and
  actionlint and fd have recorded workflow evidence. The fd task also has an
  issue-derived reproduction and a completed multiple-sample replay with public
  regression checks and final export. These are hand-written development inputs,
  not model-generated benchmark results. Live sampling and broader workflow
  coverage remain unfinished; the scorer handles one selected patch at a time.
