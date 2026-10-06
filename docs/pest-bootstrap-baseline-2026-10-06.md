# Pest public baseline — 6 October 2026

Pest now has a usable public regression baseline: **508 passes and one failure**
in 509 reported cases. This brings the latest DeepSWE readiness count to
**88/113**. The previous run stopped during compilation because the bootstrap
executable was missing.

## The missing setup step

Pest's public `meta/build.rs` regenerates `meta/src/grammar.rs` from the candidate
`grammar.pest`. It launches `../target/debug/pest_bootstrap` to do that. Its
error message and `.github/actions/setup/action.yml` both specify building
`pest_bootstrap` first.

The task-specific `pest-cargo-nextest` command now builds that executable from
the candidate checkout before nextest. Both steps use the same writable Cargo
home, cached registry, temporary build directory and existing debug-profile
settings. A `target` link in the temporary checkout points to `/tmp/target`,
so the build script finds the executable at its hard-coded location.

The setup does not copy generated grammar code or a prebuilt bootstrapper from
the image. If setup or the bootstrap build fails, it exits 125 before tests
run; that remains a harness failure. Nextest's test-failure exit 100 and its
existing JUnit report location are unchanged. Other Rust tasks keep their
original command.

## What the run established

The pinned image and sealed base revision were unchanged. The baseline used
two CPUs, the published 8-GiB memory limit, 4-GiB tmpfs and the existing
1,800-second timeout. It completed in about 115 seconds including survey setup.
Networking stayed disabled; no model, held-out tests or reference solution was
used. No test filters were added.

The one failing case is `pest_vm::surround::quote`. Its public error says
`PUSH_LITERAL requires feature grammar-extras`. This change deliberately
retains the existing default nextest features and profile; it does not adopt
the separate feature-enabled release-mode schedule from Pest's CI or repair
that test. Only the 508 passing cases enter the regression inventory.

Nextest's console summary also lists one skipped case. The emitted JUnit file
does not include that case, so our accepted report has 509 cases and zero
reported skips. The evidence records both counts rather than treating console
and report coverage as identical. Nextest does not run Rust doctests; this is
not a claim that every public test or every CI job passed.

## Evidence

[The execution summary](../experiments/deepswe/pest_bootstrap_baseline_2026_10_06.json)
records the image ID, base commit, resource limits, result counts, failing test
ID and execution-file SHA-256. Raw logs and JUnit remain outside Git under
`../output/deepswe-survey/pest-character-class-coalescing`.

[The task override](../experiments/deepswe/test_overrides.json) explains why
bootstrap is required. [Command tests](../tests/test_deepswe_execution.py)
check build ordering, the expected target path, offline settings, failure
codes and unchanged nextest arguments. All **72 command tests passed**. The
full local suite also passed: **595 passed, 19 skipped**. Those skips are
opt-in integration checks and unavailable host-native symlink checks; the
real pinned Pest Docker baseline above was run separately.

Next: review the public delegated test scripts for Arktype and Clack, which
still have `no_runner` outcomes. That is separate from this bootstrap fix.
