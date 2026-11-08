# Koota live follow-up after overload resolution fix

The new run produced three applicable repair candidates and exported
`loc-0-repair-2`. DeepSWE reported 5/51 issue checks and all 172 regression
checks passing. Koota remains unresolved.

The run used Sol xhigh, one edit-localization sample, four parallel repair
samples, the same pinned checkout and Docker image, a 2M content-token cap and
a two-hour limit. All eight requests completed. Provider-reported usage was
137,860 tokens (39,570 input and 98,290 output including reasoning).
The content ledger counted 53,583 tokens. The workflow took about 16.5 minutes,
excluding the initial public baseline.

File localization selected the same five paths as the previous attempt.
Symbol localization selected createWorld, and the fixed resolver provided
world.ts lines 18–408 to edit localization. The resulting repair excerpts
included the subscription hook regions. The earlier attempt had dropped that
entire file at symbol resolution.

Three responses contained applicable edits; one returned no SEARCH/REPLACE
blocks. Candidate 0 failed seven reported public cases, candidate 3 failed
eight, and selected candidate 2 passed its public report of 181 cases. The
frozen baseline and separate verifier retain their own test inventories.
Scoring happened after patch export.

The original five-task batch keeps its 3/5 outcome and its unsuccessful Koota
attempt. This follow-up demonstrates restored context and an exported patch
under the fixed resolver. One fresh stochastic run does not isolate all model
variation or establish a solve-rate improvement from the fix.

[Exact results](koota_after_overload_fix_2026-11-08.json) and
[selected patch](koota_after_overload_fix_selected.patch).
Local prompts, responses and validation evidence are under
`artifacts/agentless-koota-overload-fix-xhigh-2026-11-08`.
