# HTTPX attempt interrupted by host sleep

The fresh Python task `httpx-deterministic-cookie-store` did **not** reach
candidate validation or scoring. Windows entered a low-power state while two
repair requests were unfinished. On wake, their remaining task deadline had
expired. This is an **incomplete, host-interrupted attempt**, with no benchmark
score or selected prediction. It is not a scored unresolved repair.

The configuration was unchanged: GPT-6.1 Sol xhigh, the default declaration
index, one edit-localization sample, four parallel repair samples, sequential
public validation, two hours and two million once-only context tokens. No
Grinta run, model retry or partial-response validation followed the interruption.

## Work completed before the interruption

The unmodified public baseline reported 1,413 passes, four failures and one skip.
The existing policy froze the 1,413 passing IDs for candidate regression checks.
The model excluded none. The four original failures concerned proxy closing and
a Trio write timeout; they are retained in the compact result, not hidden or
treated as failures introduced by a patch.

The declaration index contained 23 source files and 608 declarations, without
parser or encoding warnings. It was 6,704 estimated tokens; the complete file
prompt was 7,649 estimated tokens. File localization selected:

```text
httpx/_models.py
httpx/_client.py
httpx/_types.py
httpx/__init__.py
```

These cover cookie/request/response handling, client integration, input types
and public exports. Symbol and edit localization completed. Two of the four
repair responses completed and remain saved, but the controller did not advance
to validation because the other two calls timed out.

## Retained timing evidence

All times below are UTC on 18 November 2026:

| Event | Time |
| --- | --- |
| First model request | 03:09:54 |
| Four repair requests started | 03:12:54 |
| First repair response completed | 03:18:32 |
| Second repair response completed | 03:19:06 |
| Windows sleep began | 03:19:07.963 |
| Windows woke | 10:17:38.478 |
| Pending calls recorded as timed out | 10:17:41 |

The sleep and wake timestamps come from Windows System event 1,
`Microsoft-Windows-Power-Troubleshooter`. The nearly seven-hour low-power
interval overlaps the two unfinished calls. Timeout handling ran after wake;
the elapsed wall-clock interval is not seven hours of active model execution
under an increased allowance. The configured attempt limit remained two hours.

There is no evidence here of a model repair failure or a provider-side root
cause independent of that interruption. No new request was launched to replace
the pending responses, and no selected patch or verifier report exists.

## Accounting and next boundary

Eight calls were attempted and six returned completed responses: the four
localization/selection calls and two repairs. Their reported usage totals
66,053 input plus 38,093 output tokens: **104,146 known processed tokens**.
Usage for the two timed-out calls is unknown, so this is not a complete total
of provider consumption. The once-only context record contains 79,735 tokens.

The raw launcher records `model_calls: 0` because it populates that counter
after successful export. The request ledger and workflow failure record instead
establish eight attempted calls and six completed responses. The compact record
preserves both values and explains the distinction.

[Compact evidence](../experiments/pilots/deepswe_small_v2/httpx_declaration_index_2026-11-18/result.json)
and [host event](../experiments/pilots/deepswe_small_v2/httpx_declaration_index_2026-11-18/host-power-events.json)
are committed. Full responses, baseline reports and timeout records remain under
`artifacts/agentless-httpx-declaration-index-2026-11-18/`.

Clack and Awilix remain unchanged as scored unresolved attempts. A new HTTPX
attempt would need an uninterrupted, awake host and a fresh declared time
allowance. No such attempt has started; the completed partial responses have
not been substituted for the planned four-sample condition.
