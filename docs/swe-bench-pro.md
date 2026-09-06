# SWE-bench Pro integration

This integration starts with three real Python tasks before additional languages.
The smoke set covers a two-file API relocation, a Qt signal update, and a larger
method-level error-message change at three distinct qutebrowser base commits.

## Trust boundary

The official dataset places agent inputs, gold patches, test patches, and
verifier test lists in the same row. Agentless-ML therefore does not accept an
unfiltered dataset row. A loader must project exactly these columns first:

```text
repo
instance_id
base_commit
problem_statement
requirements
interface
repo_language
dockerhub_tag
```

Any additional column makes the adapter fail. In particular, `patch`,
`test_patch`, `fail_to_pass`, `pass_to_pass`, and
`selected_test_files_to_run` never enter `TaskSpec`, prompts, candidate
selection, or model-visible artifacts.

## Recorded vertical slice

The checked-in experiment contains one file-localization response, one symbol-
localization response, and three repair samples. They were prepared from the
agent-visible issue and pinned base checkout only. The controller rejects the
malformed sample, constructs and validates the two well-formed patches in
independent workspaces, and chooses deterministically.

Candidate selection runs the pre-existing
`tests/unit/utils/test_log.py::TestHideQtWarning` tests. These tests are already
present at the base commit and are public repository evidence. The benchmark's
test patch and official verifier are deliberately not used during selection.
They are reserved for post-selection scoring.

The Parquet loader verifies the pinned file SHA-256 and expected row count before
returning tasks. PyArrow receives an explicit projection of the eight approved
columns, so answer and verifier columns are not deserialized into Python records.
The current pin contains 731 tasks, of which 266 normalize as Python tasks.

The environment is the task's official Docker image, pinned by resolved digest.
Containers run without network access, credentials, host mounts, Docker socket,
or Git history and are removed after each candidate.

## Scope of the result

The three development runs all rejected one malformed response, validated two
candidate patches, and selected `repair-2`. The signal and process-message tasks
used both regression and issue-derived reproduction checks; in each case the
weaker candidate passed compilation but failed reproduction, while the selected
candidate passed both.

This establishes that real benchmark records, multiple repository commits,
language adaptation, the fixed workflow, candidate workspaces, official
environments, public validation, deterministic selection, and prediction export
compose correctly. It is an engineering milestone, not a benchmark score: the
responses are recorded rather than model-generated, and the official hidden
verifier is not part of candidate selection.
