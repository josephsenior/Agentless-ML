# Should repair retain interface declarations?

The batch runner now supports `--retain-declarations` and
`--maximum-files 10` as independent settings. The default remains five files
with the original repair prompt.

Declaration retention reuses the language resolver to recover symbol spans
from the earlier localization response. It includes spans of up to 25 lines
that are missing from the edit excerpts, with a total excerpt budget of 4,000
characters per repair prompt. The repair prompt labels these spans as reference
material. Candidate validation still uses the edit locations and their ten-line
windows. The run plan and controller record both settings.

Python already uses LibCST to resolve globals that its `FileNode` leaves out.
That lookup happens during symbol resolution. Declaration retention addresses
what happens after the controller has found those locations and narrows the
source for repair.

## Original review

Review date: 9 November 2026. Decision: do not adopt this extension in the
current condition. The user confirmed that the workflow and ten-line context
window should remain unchanged. Dasel stays included as a failed attempt, with
the missing-interface context recorded as a workflow limitation. The proposal
below is retained for research history, not as pending implementation work.

Retaining declarations is a reasonable extension to evaluate, but it is not a
correction needed to reproduce the pinned Agentless method. Keep the present
baseline while deciding whether a separate context variant belongs in the study.

## What the source comparison establishes

Pinned Agentless v1.5.0 constructs repair context from the edit locations and
passes a configurable context window into its location resolver. Its command-line
default is ten lines. The reviewed path does not automatically recover referenced
interface or factory declarations outside those intervals. Its optional sticky
scope display supplies enclosing Python scopes, not general dependency signatures.

Sources: [repair.py, context construction and default](https://github.com/OpenAutoCoder/Agentless/blob/b150f28465a77a81a7f4776384957a4271f5bd69/agentless/repair/repair.py#L172)
and [preprocess_data.py, windowing and scope rendering](https://github.com/OpenAutoCoder/Agentless/blob/b150f28465a77a81a7f4776384957a4271f5bd69/agentless/util/preprocess_data.py#L10).
Our selected-context code uses a ten-line window too. This comparison does not
claim complete orchestration parity or that every upstream experiment uses the
default setting.

In Dasel, symbol localization selected the factory types, but edit localization
narrowed to registry-adjacent lines. Repair consequently lost the factory and
Reader/Writer declarations. The saved requests prove that omission. The
windowing code applied the requested locations correctly.

## A defensible extension

If we evaluate a variant, the smallest justified scope is retaining compact
interface/type declarations already selected during symbol localization from
the selected files. For Dasel, that would preserve `Reader`, `NewReaderFn`,
`Writer` and `NewWriterFn`. It would not search other repositories or choose
extra context from a failing held-out test.

Keep these declarations in a separately marked reference section. The repair
prompt may read them, but the original localized intervals still govern edits.
Simply merging reference lines into the existing interval map would silently
expand modification permissions as well as model visibility; that is a different
change. The implementation would need to distinguish reference context from
editable context.

Use a deterministic source order and the same context for every repair sample
in a localization group. Define which declarations qualify and their size limit
before evaluation, record included/omitted declarations, and count the additional
input against the existing budget. Language adapters would need an explicit
shared definition of a declaration: a Go function type is not equivalent to
an entire Python class body. No general cross-file dependency resolver is
justified by this single case.

This remains a fixed workflow: source parsing and context assembly happen before
repair sampling, with no test-driven follow-up model calls. It changes the
information available to repair, so it must have a separate declared condition.

## Benefit, cost and evidence limit

The proposed declarations would reveal the exact two-result factory contract
that the generated Dasel code violated. Two samples explicitly requested those
missing definitions. This gives a concrete reason to evaluate the proposal,
but does not demonstrate an improved solve rate or a correct HTML implementation.

An illustrative appendix adds 694 characters to Dasel's 4,185-character repair
prompt, yielding 4,879 characters. This is an offline character measurement,
not a token estimate or an implemented general policy. On other repositories,
declarations can be much larger and reference further types.

Increasing the window is simpler and already resembles an upstream configuration
choice, but provides no guarantee that dependencies fit. Retaining the entire
coarse context preserves more information at a larger input cost. The compact
declaration proposal targets the observed loss while requiring a clearly defined
cross-language rule. None should be enabled only when a task fails.

## Recommendation for this project

Do not silently change the current baseline. Document this as a context-selection
limitation and discuss with Professor Zhang whether the study should include an
explicit declaration-context variant. If adopted, freeze the general rule before
new evaluation tasks and keep earlier results under their original configuration.
Treat Dasel as a development example, not independent evidence of improvement.
No additional inference or implementation is needed to make this decision.

[Saved-prompt evidence](../experiments/pilots/deepswe_small_v2/dasel_xhigh_2026-11-09/prompt-inspection.json)
and [illustrative appendix measurement](../experiments/pilots/deepswe_small_v2/dasel_xhigh_2026-11-09/interface-context-review.json).
