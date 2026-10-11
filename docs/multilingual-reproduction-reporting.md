# Reproduction reporting in Go, JavaScript and TypeScript

The three recorded SWE-bench Pro V2 smoke commands previously returned only an
exit code. They now declare CTRF reports and use controller-owned adapters.
The workflow, source voting, candidate selection and Docker protections have
not changed. No benchmark score or readiness count follows from this migration.

## JavaScript and TypeScript

`javascript_reproduction_command(path)` runs a CommonJS `.js` or `.cjs` script.
The wrapper handles synchronous exceptions, asynchronous uncaught exceptions and
unhandled rejections. Only a Node `AssertionError` reports a failed test. Other
exceptions, missing imports and syntax errors report an error. Normal event-loop
completion reports passed; explicit process exits and nonzero `exitCode` do not.

`typescript_reproduction_command(path, node_path=...)` also accepts `.ts` entry
points. It uses the image's existing TypeScript compiler to transpile to CommonJS,
refuses syntax diagnostics and preserves entry-point-relative module resolution.
It does not type-check, install dependencies or register a global TypeScript
import hook. Imported `.ts` modules still need the repository's supported loader.
Existing `.cjs` scripts that load TypeScript themselves are supported too.

The NodeBB and Tutanota fixtures no longer swallow their final promise rejection
and turn it into an undifferentiated exit 1. Tutanota's own transpilation check
now throws `SyntaxError`, not an assertion, for invalid candidate syntax.
Assertions about the behavior under study are unchanged.

This uses Node's documented [AssertionError](https://nodejs.org/api/assert.html)
and [process lifecycle events](https://nodejs.org/api/process.html). Explicit
exit is deliberately not accepted as successful completion. The adapters are
standalone-script runners, not generic Jest/Mocha/Vitest integration or ESM support.

## Go

`go_reproduction_command(path, test_name="TestIssue")` compiles the containing
package with `go test -c`, then executes the resulting binary with a literal,
anchored test-name filter. Compilation and execution share the Docker command's
timeout. The selected test's subtests remain included, and the test cache is
disabled. Dependency downloads are disabled through `GOPROXY=off` and `GOSUMDB=off`;
Docker networking remains disabled as before.

The binary's exit status stays separate from its structured output. This matters:
a compile failure or panic must not become an ordinary reproduction failure.
The wrapper converts the binary's verbose output through Go's official
[`test2json`](https://pkg.go.dev/cmd/test2json), embeds the raw JSONL events in the
CTRF report so Docker retains them, and checks that the named test completed, no started test is missing
its outcome, and the binary's exit matches its test failures. No matching test,
abnormal exit or incomplete evidence produces an adapter error. Skips remain
visible and are rejected by the shared reproduction evidence rule.

The image must contain Python 3 and Go; both were checked in the pinned Vuls
image. The wrapper does not fetch tooling or borrow compiled candidate extensions.

## Limits and verification

A report still cannot prove that a check describes the issue. A Go `t.Fatal`
used for setup is indistinguishable from an intentional behavior check; similarly,
a Node assertion can be irrelevant. Scripts that catch their own errors and
return normally can mislead any external runner. These adapters do not make
generated code honest, and generated code must still run inside Docker.

`tests/test_multilingual_reproduction.py` exercises controlled, authored fixtures:
assertions, asynchronous errors, imports, syntax, skips, Go build failures,
panics, subtests and absent test execution. Its opt-in pinned-image diagnostics
use the existing benchmark images but only tiny authored fixture workspaces,
not benchmark tests or reference repairs. Historical smoke outputs remain intact.

Verification for this update: the combined reproduction/workflow/selection suite
passed 201 tests, with 20 opt-in Docker tests skipped in that run. Separately,
all 11 pinned-image authored-fixture checks passed, followed by a passing Go
raw-event retention recheck. No live model, benchmark schedule or held-out tests
were run. DeepSWE readiness remains 109/113.

The [three recorded slices have now been replayed end to end](multilingual-reproduction-replay-2026-10-11.md)
under this reporting contract. Their new artifacts and committed summary remain
separate from the historical runs.

The remaining language now has a [Rust reporting adapter](rust-reproduction-reporting.md),
using the images' existing Cargo-nextest installation with explicit limits around
panic classification and early successful exits.
