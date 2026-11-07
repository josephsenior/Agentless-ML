# KaTeX with Sol high reasoning

Sol high produced a selected patch after the medium run had produced no
applicable candidates. DeepSWE reported 82/94 issue checks and 599/599 regression
checks passing. The task remains unresolved.

| Measure | Sol medium | Sol high |
| --- | ---: | ---: |
| Completed requests | 8 | 8 |
| Once-only content tokens | 77,143 | 98,150 |
| Provider-reported input tokens | 71,852 | 79,562 |
| Provider-reported output tokens, including reasoning | 14,311 | 49,606 |
| Provider-reported total tokens | 86,163 | 129,168 |
| Workflow time, excluding initial public baseline | about 8.5 minutes | about 24 minutes |
| Applicable repair candidates | 0/4 | 2/4 |
| Selected patch exported | No | Yes |

Both runs used the same pinned task/image, one edit-localization sample, four
repair samples, a two-hour limit, and the 2M content-token cap. The experiment
driver changed the launcher's medium-only acceptance guard for this high-effort
run. Requests saved high effort in their settings. This did not change the
shared benchmark contract. It was one development comparison on an exposed
task, with stochastic model outputs.

High selected the same three TypeScript files but more edit locations,
including more HTML layout context. All four repairs contained edit blocks.
One tried to edit an existing file outside the selected inventory. Two applied:
one passed all 1,252 public regression checks, while the other failed 14 of
1,252. The last response used a SEARCH signature with HTMLBuilder that did not
match the source. The controller selected the public-regression-passing patch.
The separate verifier's remaining failures covered matrix column-span handling
and empty content. Its feedback was inspected after export.

## What can be fixed deterministically

The earlier JavaScript-only inventory was a system defect and has already been
fixed. This run supplied the selected TypeScript files and applied two repairs;
the observed final failures are incorrect generated program behavior.

No new parser or range-tracking defect was found. The missing source signature
and the attempt to edit an unselected file are model outputs the current
controller correctly rejects. A deterministic check can detect such outputs,
but producing the missing correct code is a separate problem.

Providing imports or larger regions by a fixed rule, selecting more files, or
adding localization samples would change the context or sampling policy. Such
changes can be evaluated and declared as method adjustments. They should apply
consistently and be decided before the main experiment.

Our atomic rejection also differs from pinned upstream Agentless: upstream's
SEARCH/REPLACE application works within localized intervals and can skip
unmatched blocks; Agentless-ML rejects a repair if any required edit fails.
This deserves explicit method documentation. Skipping a block could leave an
incomplete patch and does not establish that a task would be solved.
[Published implementation](https://github.com/OpenAutoCoder/Agentless/blob/b150f28465a77a81a7f4776384957a4271f5bd69/agentless/util/postprocess_data.py#L514-L612)

High used about 50% more processed tokens and 2.8 times the workflow time.
It materially improved this attempt, which supports further development checks
before choosing the main benchmark configuration. One task cannot establish an
average solve-rate improvement.

[Exact result record](katex_sol_high_2026-11-07.json).
Local prompts, responses and verifier reports are under
`artifacts/agentless-katex-sol-high-2026-11-07`.
