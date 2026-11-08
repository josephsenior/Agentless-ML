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

Next, inspect whether the correct factory type definitions were included in the
saved repair context. That can distinguish missing context from a reasoning
mistake without another model call. Do not change the generated patch based on
held-out checks.
