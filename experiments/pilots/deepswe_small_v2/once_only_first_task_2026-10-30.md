# First task with once-only content accounting

Task: `aiomonitor-task-snapshots-diff`. Both systems used GPT-6.1 Sol, medium
reasoning, a two-hour limit and one million once-only content tokens. Actual
provider usage remained separately recorded.

| System | Content tokens | Processed tokens | Outcome |
| --- | ---: | ---: | --- |
| Agentless-ML | 34,665 | 45,032 | Selected patch; task unresolved |
| Grinta | 202,696 | 1,709,501 | Subscription-sharing allowance exhausted; no final prediction |

Agentless completed eight model requests: regression selection, file, symbol and
edit localization, then four repairs. Postprocessing exposed a coordinate bug:
earlier insertions moved later SEARCH blocks outside stale authorized ranges.
The original source matches were valid. After correcting range tracking, the
same saved responses were replayed through public validation, selection and
prediction export with **zero new model calls**. Three repairs were applicable;
the fourth lacked a SEARCH/REPLACE edit. The fix does not broaden the original
localized source permissions, and regression tests retain protection for lines
outside those regions.

Selection chose `loc-0-repair-0`. DeepSWE's separate post-selection verifier
reported **38/53 issue-specific checks passing and 8/8 regression checks passing**.
The task is unresolved, with reward 0. The selected patch is retained as
[agentless_aiomonitor_selected.patch](agentless_aiomonitor_selected.patch).
Held-out results were not fed back into generation or selection.

Grinta completed 27 model responses and performed repository work. The service
then refused further inference because its subscription-sharing allowance was
exhausted. Its local content limit was not reached. This is a capacity-blocked
run, not evidence that Grinta cannot solve the task. No API-key fallback was used
and no final patch was exported or scored.

The shared prepared image was
`sha256:694a2a50c55aec432ebe43a0cdeb5aca03ae29a7b5ca546106128c1a8ba735ef`.
Both runners passed the controlled setup checks, and the initial public baseline
passed eight tests. The private tokenizer and its verified vocabulary were
available offline. Grinta's fresh source archive included its Git tracking index.

This is development evidence: the task has been exposed during debugging,
Agentless's postprocessing required a replay, and Grinta was interrupted by an
external service limit. It is not a clean paired research comparison. No other
pilot task was started. Exact usage, patch digest and local evidence references
are in [the result record](once_only_first_task_2026-10-30.json).

The counting policy is implemented and observed on live requests. A complete
paired task remains pending adequate subscription-sharing allowance.
