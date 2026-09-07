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
infrastructure failure is never converted into a failed test result. Candidate
workspace isolation is provided separately by the [local workspace layer](workspaces.md).

Patch normalization removes Git framing metadata, normalizes line endings, and
strips trailing whitespace. It retains hunk offsets and source context. Upstream
instead normalizes Python source through AST operations and comment/docstring
removal before rebuilding a diff. The resulting voting groups can differ; the
current textual key is provisional and does not establish semantic equivalence.
See the [replication map](replication-map.md) for the rationale and alternative.

The selector counts supplied regression results. With the current Docker runner,
each result describes one command, which may execute many tests. This is not
equivalent to upstream individual failed-test counts unless the schedule or report
adapter supplies that granularity. Local policy tests do not establish full
upstream selection parity.

## Still outside this boundary

- syntax and language-specific static checks;
- public regression and reproduction-test execution (now provided separately by
  the [Docker runner](public-validation.md));
- clean workspace creation and real `git apply` checks (now implemented separately);
- model sampling and usage records;
- official benchmark verification.

Those operations will consume the contracts implemented here without allowing
their outcomes to initiate another model trajectory.
