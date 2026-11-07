# KaTeX with GPT-6 Astra medium reasoning

Astra medium produced one applicable repair and exported it after the other
three responses contained no SEARCH/REPLACE edits. The candidate passed 1,251
of 1,252 public checks. DeepSWE's separate verifier reported 0/94 issue checks
and 599/599 regression checks passing. The task remains unresolved.

| Measure | Sol medium | Sol high | Sol xhigh | Astra medium |
| --- | ---: | ---: | ---: | ---: |
| Completed requests | 8 | 8 | 8 | 8 |
| Applicable repairs | 0/4 | 2/4 | 4/4 | 1/4 |
| Selected patch's issue checks | No patch | 82/94 | 84/94 | 0/94 |
| Provider-reported total tokens | 86,163 | 129,168 | 187,003 | 79,776 |
| Workflow time | 8.5 min | 24.0 min | 50.5 min | 6.1 min |

Astra input usage was 72,524 tokens; output usage, including reasoning, was
7,252 tokens. The once-only content ledger counted 74,522 tokens. Workflow
time was about 367 seconds, excluding the initial public baseline. There was
no subscription refusal or budget stop.

The run used the same pinned checkout and Docker image, one edit-localization
sample, four repairs, and the 2M content-token and two-hour limits. Request
records confirm `gpt-6-astra` at medium reasoning. The experiment driver
changed only the launcher's Sol-only acceptance guard. The shared comparison
contract remains unchanged.

File localization chose the same three TypeScript paths as the Sol runs.
Edit localization produced its own source excerpts. The first three repair
responses requested more context or explained missing functionality without
providing edits. The fourth supplied an applicable patch; the controller
selected it before separate verifier scoring. Verifier failures include
incorrect rejection of valid multicolumn cells.

On this development attempt, Sol high and xhigh produced better issue-check
results. One stochastic run per setting on an exposed task cannot establish a
general model ranking. The held-out diagnosis was inspected after export and
was not inserted into stage prompts.

[Exact results](katex_astra_medium_2026-11-07.json).
Local artifacts are under `artifacts/agentless-katex-astra-medium-2026-11-07`.
