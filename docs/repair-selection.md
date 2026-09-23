# Repair and selection boundary

This boundary starts with focused source context and ends with one selected Git
patch. It contains no model client, test runner, benchmark verifier, or adaptive
tool loop. Recorded responses can therefore exercise it deterministically.

## Published behavior retained

- The Python repair prompt matches Agentless v1.5.0 at revision
  `b150f28465a77a81a7f4776384957a4271f5bd69` for its documented
  `--cot --diff_format` condition. A golden prompt checksum protects that seam.
- Responses use fenced SEARCH/REPLACE blocks with repository-relative paths.
- Candidate filtering prefers the minimum number of public regression failures.
- When reproduction evidence is enabled, reproduction-passing candidates are
  preferred and selection falls back to the best regression group if none pass.
- Remaining candidates are grouped by normalized patch, with majority vote and
  first appearance as the deterministic tie-break.

## Intentional changes

The published v1.5.0 post-processor applies only the first file named by a model
response. Agentless-ML applies every valid edit atomically in memory. This is
an intentional capability difference: tasks can require consistent changes across
multiple files, while candidate generation and selection remain fixed controller
stages. Preserving those stages does not make this behavior identical to upstream.

Agentless-ML also rejects unsafe paths, empty searches, missing files, ambiguous
matches, no-op edits, patch errors, and infrastructure-failed candidates. An
infrastructure failure (a timeout, an out-of-memory kill, a Docker error) is
never converted into a failed test result. A patch that breaks the build is not
an infrastructure failure: it counts as failing every counted regression test,
as in published Agentless, so it ranks last but can still be emitted when every
candidate is broken ([details](public-validation.md#a-patch-that-breaks-the-build)). Candidate
workspace isolation is provided separately by the [local workspace layer](workspaces.md).

Patch normalization removes Git framing metadata, normalizes line endings, and
strips trailing whitespace. It retains hunk offsets and source context. Upstream
instead normalizes Python source through AST operations and comment/docstring
removal before rebuilding a diff. The resulting voting groups can differ; the
current textual key is provisional and does not establish semantic equivalence.
See the [replication map](replication-map.md) for the rationale and alternative.

The selector sums `failure_count()` over each candidate's regression results. A
command that declared a test report contributes one unit per failing test; a
command without one contributes one unit if it failed. Every candidate runs the
same frozen schedule, so the same command always contributes the same kind of
unit. Example: two candidates both fail a 100-test suite command; one breaks two
tests and the other one test, so the second is kept, where command-level counting
would have tied them. See [per-test results](public-validation.md#per-test-results-from-reports).
Upstream also restricts the count to regression tests selected at the start; that
test-level selection is not implemented yet. Local policy tests do not establish
full upstream selection parity.

## Still outside this boundary

- syntax and language-specific static checks;
- public regression and reproduction-test execution (now provided separately by
  the [Docker runner](public-validation.md));
- clean workspace creation and real `git apply` checks (now implemented separately);
- model sampling and usage records;
- official benchmark verification.

Those operations will consume the contracts implemented here without allowing
their outcomes to initiate another model trajectory.
