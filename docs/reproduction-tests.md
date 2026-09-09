# Recorded reproduction tests

The controller now accepts one recorded generated test, verifies it against the
original revision, and runs it unchanged against repair candidates. It renders
the generation prompt but makes no model calls.

## Inputs

The caller supplies a `ReproductionSpec`: a repository-relative destination path
and a trusted `PublicTestCommand` with reproduction kind. The response bundle's
`reproduction_test` field contains one code block labelled with the task language.
The response supplies source only; it cannot choose the path or execution command.
The prompt contains the issue, destination, language and command—not repair patches,
reference solutions or hidden tests.

The destination must not exist, its parent directory must already exist, and its
path cannot traverse symlinks or Git metadata. This supports adding a standalone
test in an existing test directory, not changing build manifests or creating a
new test project. The trusted command must arrange compilation/discovery as needed.
No language-specific test-runner integration is implied by accepting a code block.

## Baseline and candidate checks

The generated source is written only into an isolated checkout. Its command must
report an ordinary failure on the unpatched revision. A pass means it did not
reproduce a failure; a timeout or harness error is not accepted as reproduction.
Either stops this recorded run. There is no retry or feedback-driven test revision.

The same source is then installed temporarily for its reproduction command in
each candidate workspace. It is absent during regression checks, cannot overwrite
repository files, and is removed after execution. The exported patch contains
only the candidate's repair, not the generated test. Existing reproduction-aware
selection favors passing candidates after regression filtering; its fallback
behavior is unchanged.

Generated source is untrusted executable code. Production execution uses the
existing isolated Docker runner, not a host interpreter. The test fixtures use
controlled runners that inspect source without executing generated code.

## Differences and limits

Upstream Agentless uses printed markers such as “Issue reproduced” and “Issue
resolved”. This implementation uses the runner's PASS/FAIL/infrastructure statuses.
That is a disclosed difference, not marker-protocol parity. A trusted wrapper or
framework report parser must distinguish assertion failures from import, build
and setup failures; an exit code alone cannot always do that. The prompt asks
for correct failure handling, but that request is not a technical guarantee.

Failing on the original revision is necessary, not sufficient: a test can fail
for the wrong reason or encode the wrong expected behavior. This milestone does
not prove semantic validity, detect flakiness, select among several generated
tests, normalize duplicates, or reproduce every upstream test-generation option.
There is one recorded source per run. Live generation remains later work.

## Evidence

`reproduction-generation.txt` records the prompt. `reproduction-source.json`
records the trusted specification, source and SHA-256 digest.
`reproduction-baseline.json` records baseline results, workspace provenance and
log location. Candidate execution records retain reproduction outcomes separately
from regression outcomes.

[Source and overlay tests](../tests/test_reproduction.py) check fences, path
constraints, collisions and cleanup. [Controller tests](../tests/test_fixed_workflow.py)
check baseline eligibility, unchanged test use, regression isolation, candidate
selection and patch export. This is controlled workflow coverage, not a live
Docker test of generated source or a benchmark result.
