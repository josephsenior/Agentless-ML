# ts-pattern matchEach

On 11 November 2026, `ts-pattern-match-each` was the next fresh task in the
existing ranking after Geo. The public baseline passed 442 tests. Agentless-ML
used Sol xhigh, four concurrent repair samples and sequential Docker validation.
All eight model responses completed and all four patches reached validation.

The selected patch, sample 0, scored **0/85 issue checks** and **6/6 verifier
regression checks**. TypeScript rejected a type assertion in `match-each.test.ts`
that expects the compiled matcher to accept `'b' | 'c'` and return `number[]`.
Jest reported zero executed tests in that suite. DeepSWE counted all 85 missing
issue results as failures, leaving the task unresolved.

The run used 105,991 provider-reported tokens and took 13.6 minutes
from the public baseline through final scoring.

[Run evidence](ts_pattern_xhigh_2026-11-11/summary.json) and
[exported patch](ts_pattern_xhigh_2026-11-11/selected.patch).
