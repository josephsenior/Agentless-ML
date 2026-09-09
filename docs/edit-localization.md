# Edit-line localization

The recorded controller can now follow files → symbols → edit lines → repair.
Previously it built repair context directly from symbol locations. The extra
stage is inherited from Agentless, not an interactive tool loop.

Set `RecordedStageResponses.edit_localization` to a recorded response such as:

````text
```
src/lib.rs
line: 24
line: 27
```
````

The controller first builds numbered source context from the symbol response.
Numbers refer to the original file, not positions in the shortened prompt.
The edit response selects lines in that visible context. Repair context uses
the existing ten-line window around those lines, without line-number prefixes.
That window can extend beyond the earlier symbol window; it is the resulting
repair-context intervals, not just the selected lines, that bound patch edits.

## Choices and limits

The new field is optional so existing recorded fixtures and benchmark smoke
inputs still replay unchanged. `controller.json` records `edit-samples`, `edit-lines` or
`symbols-only`; these should not be presented as identical conditions.

We accept exact line locations for this first implementation. Unknown files,
malformed entries, empty selections and lines absent from the shown context fail
the run. Falling back to the coarse context would conceal a failed stage and
change the allowed repair region. This strict policy is a local choice, not a
claim of identical upstream error handling.

Multiple recorded responses are supported as explicit localization/repair groups.
Live sampling remains unfinished. The prompt is a shared multilingual prompt,
not a byte-for-byte copy of upstream.
The reference is `localize_line_from_coarse_function_locs` in the pinned
[Agentless FL.py](https://github.com/OpenAutoCoder/Agentless/blob/b150f28465a77a81a7f4776384957a4271f5bd69/agentless/fl/FL.py).

## Several localization samples

Use `RecordedStageResponses.edit_samples` with a tuple of `RecordedEditSample`
records. Each record contains an `edit_localization` response and its own tuple
of `repairs`. Leave the older `repairs` and `edit_localization` fields unset;
mixing the two formats raises an error instead of guessing which one wins.

Every sample sees the same numbered symbol context. Its returned lines produce
its own repair prompt and allowed edit intervals. A repair belongs only to that
sample, so it cannot borrow another sample's context. All repairs start from the
same pinned source, never from a previous candidate's patch.

The controller processes samples in tuple order, then repairs within each sample.
IDs such as `loc-1-repair-0` retain both positions. Applicable candidates enter
one common validation and selection pool. Voting still counts repair candidates,
not localization groups; identical patches from different groups can vote together.
Ties keep the existing first-appearance rule. Supplying more repairs to one group
can therefore affect voting; experiment budgets must specify those counts.

Explicit groups avoid inferring an association from two independent lists. They
also allow unequal recorded sample counts without allocating a live sampling
budget yet. This implements local grouping and selection behavior; it does not
establish parity with every upstream sampling or merge configuration.

All localization samples are checked before any candidate is executed. A malformed
sample stops the run, matching the strict single-response policy. We do not
silently skip it, retry it, or redistribute its repairs. The input bundle and
failure are saved so it can be corrected deliberately.

## Evidence and artifacts

[Localization tests](../tests/test_edit_localization.py) exercise numbered context
and line resolution in all five languages, including malformed responses.
[Controller tests](../tests/test_fixed_workflow.py) check a complete Python repair
and failure without fallback. Existing symbols-only tests remain regression checks.
These are framework tests with recorded inputs, not evidence of model accuracy.

`symbol-context.json` retains the coarse context, intervals, edit prompt and
response, including when parsing fails. Successful runs also save
`prompts/edit-localization.txt`; `selected-context.json` records the final
repair context. For grouped runs, `localizations/<rank>/selected-context.json`
and `localizations/<rank>/repair.txt` hold each group's evidence; there is no
misleading single repair prompt. `responses.json` retains the complete grouping,
and candidate attempts retain their localization rank even when repair parsing
fails. Controller tests cover common selection, duplicate votes, distinct line
windows, input conflicts and failure before execution. No model calls are made.
