# KaTeX with Sol xhigh reasoning

One Agentless-ML xhigh run exported a patch that passed 84/94 DeepSWE issue
checks and all 599 regression checks. The task remains unresolved. The prior
high run passed 82/94 issue checks and the same 599 regression checks.

| Measure | Sol medium | Sol high | Sol xhigh |
| --- | ---: | ---: | ---: |
| Completed requests | 8 | 8 | 8 |
| Applicable repairs | 0/4 | 2/4 | 4/4 |
| Repairs passing all 1,252 public checks | 0 | 1 | 2 |
| Selected patch's issue checks | No patch | 82/94 | 84/94 |
| Provider-reported input tokens | 71,852 | 79,562 | 80,514 |
| Provider-reported output tokens, including reasoning | 14,311 | 49,606 | 106,489 |
| Total provider-reported tokens | 86,163 | 129,168 | 187,003 |
| Once-only content tokens | 77,143 | 98,150 | 97,654 |
| Workflow time | 8.5 minutes | 24.0 minutes | 50.5 minutes |

The xhigh attempt used one edit-localization sample and four repair samples,
the same pinned KaTeX checkout and image, and the same 2M content-token and
two-hour limits. The saved experiment driver permits xhigh through the
launcher's medium-only guard. Request records confirm xhigh settings; the
shared benchmark contract is still medium. Earlier held-out feedback was not
included in the stage prompts.

The selected candidate was `loc-0-repair-0`. Candidates 0 and 3 passed all
1,252 public checks. Candidates 1 and 2 applied but their public checks failed
without individual case results. The controller retained these failures and
selected from the passing candidates before separate held-out scoring.

Xhigh increased applicability on this attempt. Its selected patch passed two
more issue checks than high while consuming about 45% more processed tokens
and 2.1 times the workflow time. This result alone does not justify adopting
xhigh for the main benchmark. The task has now been used repeatedly for
development, and one attempt per effort does not estimate average performance.

[Exact results](katex_sol_xhigh_2026-11-07.json).
Local artifacts are under `artifacts/agentless-katex-sol-xhigh-2026-11-07`.

## Diagnosis of the ten remaining failures

All ten verifier failure sections report the same exception at
`parseArray`, patched `src/environments/array.ts:285`. The affected cases
exercise matrix variants and their delimiters.

The generated patch calculates a hard column limit from either
`maxNumCols` or the number of alignment entries in `cols`. Matrix handlers
initially pass one centered alignment entry as a default style. They infer the
actual column count from parsed rows afterward. The patch mistakes that initial
style entry for a one-column limit.

For example, the verifier's matrix input contains a cell spanning two columns
followed by a third cell. The generated check compares the first cell's span of
two with an inferred limit of one and throws before the matrix handler can
determine its real width. Parentheses and bracket checks fail at this same
parsing exception before the delimiters are rendered.

This is a shared defect in the generated repair's column-limit logic. The
framework applied that repair and the verifier executed it. A correction would
need to distinguish an explicitly declared array width from a matrix alignment
default and account for spans when inferring matrix width. No patch correction
or verifier retry was performed during this inspection. The shared exception
can mask later errors, so this finding does not establish that one code change
would make all 94 checks pass.
