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
classified as multilingual plumbing: benchmark tasks can require consistent
changes across multiple files, while candidate generation and selection remain
fixed controller stages.

Agentless-ML also rejects unsafe paths, empty searches, missing files, ambiguous
matches, no-op edits, patch errors, and infrastructure-failed candidates. An
infrastructure failure is never converted into a failed test result. Candidate
workspace isolation is provided separately by the [local workspace layer](workspaces.md).

Patch normalization removes line-ending and non-semantic Git metadata variance.
It deliberately retains hunk offsets and source context so edits at different
locations cannot collapse into the same voting key.

## Still outside this boundary

- syntax and language-specific static checks;
- public regression and reproduction-test execution;
- clean workspace creation and real `git apply` checks (now implemented separately);
- model sampling and usage records;
- official benchmark verification.

Those operations will consume the contracts implemented here without allowing
their outcomes to initiate another model trajectory.
