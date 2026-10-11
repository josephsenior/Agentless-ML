# Rust reproduction reporting

Rust now has a controller-owned reporting command for one new Cargo integration
test. It uses the cargo-nextest installation already present in our Rust images;
it does not install tooling or require nightly Rust.

```python
from agentless_ml.validation import ReproductionSpec, rust_reproduction_command

path = "tests/agentless_reproduction.rs"
spec = ReproductionSpec(path, rust_reproduction_command(path, test_name="issue"))
```

The caller chooses the path and literal test name. Recorded/generated source
cannot change the command. The file must be a new direct child of an existing
crate's tests directory. For crates/example/tests/reproduce.rs, the adapter uses
crates/example/Cargo.toml and Cargo's reproduce integration-test target. Module
names such as checks::issue are accepted too.

This first adapter covers ordinary auto-discovered Cargo/libtest integration
tests. It does not enable tests in crates with autotests disabled, change a Cargo
manifest, inject private-module tests, supply optional features, or provision
repository-specific build prerequisites. Those cases must fail closed until
their setup is explicitly supported.

## Why nextest

The Rust images already use nextest for public regression checks. It produces
[JUnit reports](https://nexte.st/docs/machine-readable/junit/) on stable Rust,
whereas native libtest's [JSON output](https://doc.rust-lang.org/rustc/tests/)
still requires unstable options. Reproduction reporting reuses nextest, not the
benchmark's hidden verifier or its full public test schedule.

The wrapper creates its own temporary config, Cargo home, build directory and
report store. It links to existing registry/git caches, builds the candidate
source offline, uses one build worker and one test worker, and disables retries.
It does not reuse compiled candidate binaries. Incremental compilation is off
and debug information is reduced to line tables, as in our existing Rust runner;
debug assertions and overflow checks remain enabled. Docker protections and
caller-selected resource/time limits are unchanged.

## Evidence rule

Nextest runs only the selected integration target and exact test name. The report
must contain exactly that test, with no retries or flaky-run markers.

In the verified nextest 0.9.97 image, a libtest failure has the structured JUnit
type "test failure with exit code 101". Only that verified type qualifies as an
ordinary failure, paired with nextest's test-failure exit 100. A normal passing
case must agree with nextest exit 0. Other failure types, including aborts,
timeouts and leaked-handle failures, are errors even if nextest represents them
with a failure element rather than an error element. Unknown type labels fail
closed; a nextest upgrade needs verification before expanding this allowlist.

Compilation errors, missing nextest, no matching tests, ignored tests, malformed
reports, extra test cases and contradictory outcomes cannot qualify a baseline.
An explicit process exit 1 is also rejected. These outcomes become harness errors
through the existing shared reproduction evidence rule; timeouts and OOM retain
the Docker runner's infrastructure classification.

The wrapper emits CTRF and embeds the original JUnit bytes as base64 in
rust_junit_base64. This preserves the original report, including error details,
after temporary files and the container are removed. JUnit input is capped at
16 MiB so its base64 representation fits within the shared 32-MiB report budget;
oversized input is rejected and only a bounded prefix is retained.

## What this cannot establish

Rust assertions are panics. An unrelated panic has the same libtest failure
classification, so this adapter cannot prove that the issue was reproduced.
Likewise, nextest treats process exit 0 as success without proving that an
assertion ran; a script can also swallow its own errors or explicitly mimic
libtest's exit 101. The tests record these limits rather than hiding them behind
traceback heuristics. Reports are execution evidence, not semantic proof or a
way to make untrusted source honest. Generated source still runs only in Docker.

## Verification and next step

The [pinned Wasmi image](../experiments/deepswe/corpus_pin.json) contains Python 3,
Rust 1.92.0 and cargo-nextest 0.9.97.
All 40 Rust checks passed, including nine offline authored-fixture container
checks. Those fixtures compile a tiny candidate crate, verify the same assertion
fails on subtraction and passes on addition, and exercise build errors, absent
and ignored tests, aborts, explicit exits and non-assertion panics.

The combined reproduction, workflow and selection suite passed 232 tests, with
29 opt-in Docker tests skipped in that run. The nine Rust container checks above
were run separately and passed.

No Wasmi benchmark tests, held-out verifier, model calls, tool downloads or host
changes were involved. DeepSWE readiness remains 109/113.

The [complete recorded Rust controller slice](recorded-rust-controller-slice.md)
now passes too: failing reproduction baseline, candidate validation, selection
and final prediction export. It is an authored fixture, not a benchmark solve.

The [real fd repository diagnostic](fd-rust-reproduction-diagnostic.md) also
passes: the reporter sees a passing public CLI check on the pinned base and a
failing check after a deliberately broken candidate-source change. This proves
real-repository compilation/discovery, not task-solving or failing-baseline eligibility.

An [issue-derived fd reproduction](fd-issue-derived-reproduction.md) now fails
on the pinned base and passes after a recorded partial path-sorting repair.
That real-task controller slice now combines reproduction and the existing
public regression suite through final prediction export. It preserves all 240
baseline-passing tests; both full public runs retain the same one failure out
of 241 tests. This is not a clean full-suite pass or a solution of the complete
multi-key sorting task.
