# Dasel HTML format: one fresh Agentless attempt

Selected task: `dasel-html-document-format` (Go). This is an Agentless-only
development attempt. Grinta is not running.

Selection used the same short-baseline eligibility idea as the earlier five-task
pilot: passing saved public baseline taking at most 120 seconds, local pinned
image and checkout, and no known prior repair exposure. Eligible task IDs were
sorted by SHA-256 of `agentless-fresh-xhigh-2026-11-09:<task_id>`. Dasel ranked first.
Its saved public baseline passed 1,012 cases in about 41 seconds. The workflow
runs a fresh public baseline before inference. This practical selection does not
establish a representative benchmark sample.

Settings: `gpt-6.1-sol`, xhigh reasoning, one edit-localization sample, four repair
samples generated concurrently, sequential Docker validation, a 2M once-only
content-token cap and a two-hour workflow limit. Scoring uses DeepSWE's separate
verifier after prediction export. No held-out test content is supplied to the
workflow. The attempt output is
`artifacts/agentless-dasel-xhigh-2026-11-09`.

[Selection record](dasel_xhigh_2026-11-09_selection.json).
## Result

The exported patch was unresolved: 0/146 issue checks and 406/1,012 regression
checks passed. The verifier completed normally. The run made eight model calls,
using 89,201 provider-reported tokens (30,240 input and 58,961 output including
reasoning). The once-only content ledger counted 48,831 tokens. The workflow's
recorded wall time was about 11.6 minutes; the full attempt including scoring
was about 12 minutes. Neither budget limit was reached.

Two responses produced applicable patches (samples 0 and 3), and two were
rejected for lacking SEARCH/REPLACE edits. Both applicable patches failed public
compilation. Selection exported sample 0 under the existing rule; a candidate's
`validated` status means validation was executed, not that its tests passed.

The generated reader factory returns `Reader` but the pinned `NewReaderFn`
requires `(Reader, error)`. The writer has the analogous mismatch. These
compiler errors appeared during public validation before final scoring. The
verifier also reported parsing-package build failures. Test IDs absent because
of build failures do not count as passed, explaining the large regression loss.
This evidence identifies invalid generated code; no framework bug has been
established by this run. We did not manually repair or rescore its candidates.

[Full result](dasel_xhigh_2026-11-09/result.json),
[summary and compiler errors](dasel_xhigh_2026-11-09/summary.json), and
[exported patch](dasel_xhigh_2026-11-09/selected.patch).

## Saved repair-context inspection

Neither factory signature appeared in any of the four repair prompts. Both were
visible in the symbol-localization and edit-localization requests. Symbol
localization even selected `NewReaderFn` and `NewWriterFn` explicitly.

Edit localization then chose reader lines 3 and 5, and writer lines 3 and 10.
The configured ten-line context window produced reader lines 1–15 and writer
lines 1–20. The actual declarations are at reader line 25 and writer line 34:

```go
type NewReaderFn func(options ReaderOptions) (Reader, error)
type NewWriterFn func(options WriterOptions) (Writer, error)
```

The Reader and Writer interface declarations were also outside the repair
excerpts. All four repairs received the same 4,185-character prompt. Each repair
request contains its own prompt and does not inherit earlier localization
messages, so the earlier visibility does not provide that information to repair.

Samples 1 and 2 explicitly said those interfaces and constructor signatures were
missing and requested more source instead of returning edits. Samples 0 and 3
guessed incompatible factories, which the public compiler rejected.

The context ranges match the selected lines and configured padding. This shows
a limitation of this run's edit localization and narrow repair context; it does
not establish a resolver malfunction. It would be inaccurate to say the repair
model saw and ignored the correct factory signatures. It still produced invalid
code from incomplete context. Adding the missing declarations might prevent
these type errors, but would not establish correctness of the rest of the HTML
implementation.

No model request, Docker execution, patch modification or rescore was needed.
[Exact prompt checks, hashes and selected context](dasel_xhigh_2026-11-09/prompt-inspection.json).

## Decision: preserve the workflow

On 9 November 2026, the user confirmed that the current study should preserve
the workflow and its ten-line context window. No declaration appendix, larger
window, extra retrieval call or task-specific fallback will be added.

Dasel remains an unsuccessful attempt in the evaluation. The observed limitation
is that edit localization can identify where a change belongs while dropping
declarations needed to implement it. A larger fixed window would improve the
chance of including a dependency, not guarantee it. This is a useful documented
failure mode of the fixed workflow, rather than a reason to exclude the task.
The public compiler errors and all original results remain unchanged.

The [interface-context review](../../../docs/interface-context-review.md) is
retained as analysis of a possible future variant, outside the current condition.
