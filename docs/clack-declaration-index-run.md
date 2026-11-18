# First fresh task with the declaration index

Agentless-ML ran Clack's async-autocomplete task on 18 November 2026 with the
new file-localization index. It selected both expected implementation files.
The final DeepSWE result is **unresolved**: the selected patch passed 81 of 82
issue checks and all 643 verifier regression checks.

The configuration stayed at GPT-6.1 Sol xhigh, one edit-localization sample and
four parallel repair samples. Candidate validation ran sequentially, offline,
under the shared 8-GiB/two-CPU environment. The attempt limits remained two
hours and two million once-only context tokens. Grinta was not run.

## What file localization saw and selected

The index contained 59 source files and 516 recognized declarations, with no
parser or encoding warnings. Its text was 6,141 estimated tokens. The complete
file-selection request was 7,149 estimated tokens; the provider reported 7,155
input tokens including request overhead.

The model selected:

```text
packages/core/src/prompts/autocomplete.ts
packages/prompts/src/autocomplete.ts
```

These contain `AutocompletePrompt` and its options, and the public `autocomplete`
and `autocompleteMultiselect` wrappers. Symbol localization selected those
declarations too. The public issue and source review identified the same two
files; that review was not supplied as extra hints to the model.

This establishes that this run found the expected files. It does not isolate an
improvement over the old tree-only prompt: there was no paired control attempt.
The task already names the autocomplete functionality explicitly.

## Validation and selection

The fresh baseline passed all 640 public tests. The model excluded none.
All four candidates produced valid patches and each passed all 640 public
regression tests. They had distinct voting keys, so the normal first-appearance
tie-break selected `loc-0-repair-0` with one vote. No verifier feedback influenced
that choice.

| Post-selection verifier | Passed | Total |
| --- | ---: | ---: |
| Issue checks | 81 | 82 |
| Regression checks | 643 | 643 |

The single failure was `previous AbortController is aborted when new fetch
starts`. The issue explicitly requires a new fetch to abort the previous signal.

The generated patch discards its controller when a fetch completes, without
aborting it. A later search tries to abort the previous controller, but that
reference is already gone. The verifier saves the signals and observes that
an earlier one remains unaborted. That is the concrete mismatch behind the
failure, even though obsolete in-flight requests and other behavior passed
their checks.

This is generated-patch lifecycle logic failing the stated contract. It does
not establish a framework defect or a missing-file problem. The inspection took
place after final selection and scoring. We did not modify the patch, score
alternative candidates or request another repair after seeing the failure.

## Usage and evidence

The controller made eight model calls and took 748.5 seconds, about 12.5 minutes,
before export. Separate post-selection scoring followed. Provider usage was
43,279 input and 72,082 output tokens: **115,361 processed tokens**, including
reasoning reported in output usage. The once-only context budget recorded 61,735
tokens. These are different accounting measures, not competing totals.

The implementation was commit `eb7c671`. The run revision carries `+dirty` for
pre-existing unrelated edits; retained hashes verify that the controller, index
and subscription-provider sources matched their committed versions.

[Compact result](../experiments/pilots/deepswe_small_v2/clack_declaration_index_2026-11-18/result.json),
[selected patch](../experiments/pilots/deepswe_small_v2/clack_declaration_index_2026-11-18/selected.patch)
and [post-selection failure inspection](../experiments/pilots/deepswe_small_v2/clack_declaration_index_2026-11-18/failure-inspection.json)
are retained. Raw prompts, all responses, public executions and verifier reports
remain under `artifacts/agentless-clack-declaration-index-2026-11-18/`.

Clack stays included as an unresolved development attempt. A useful next check
is another fresh task with the same configuration, rather than tuning this
workflow against the now-exposed verifier failure.
