# First-task development run, 30 October 2026

Task: `aiomonitor-task-snapshots-diff`. Both systems used GPT-6.1 Sol with
medium reasoning through the ChatGPT subscription connection. The per-system
cap remained two hours and two million combined input/output tokens.

| System | Outcome | Reported tokens | Budgeted runtime |
|---|---|---:|---:|
| Agentless-ML | Stopped at edit-line validation; no repair generated | 17,635 | 68.1 seconds |
| Grinta | Subscription-sharing usage allowance exhausted; no final patch exported | 1,703,112 | 764 seconds |

These are the runs after the streaming adapter corrections, not total usage
across all development launches. Grinta completed 27 model responses; its 28th
request was rejected by the service. That account limit was reached before the
configured two-million-token cap. No paid API fallback was used.

Agentless's fence clarification worked in this run. The later failure was our
line-boundary bug, not an invalid model response: `aiomonitor/types.py:62` was
shown in the prompt. The controller used a shorter line count when validating
it. Local replay of the saved response now accepts all 14 locations after the
fix described in [edit localization](../../../docs/edit-localization.md).
The controller, edit-localization, live-workflow and location-parity checks passed:
73 tests, with one optional Docker integration test skipped. The regression
cases cover both recorded edit modes and still reject a line beyond the shown
trailing blank. No new model calls were made for this verification.

Grinta executed repository tools and edited source after its asynchronous
response-ID and streamed-output fixes. It had not exported a prediction when
the service refused further inference. Its source archive also lacked a Git
tracking index; that host-side setup issue was fixed for fresh archives without
altering the active workspace. Consequently this run is development evidence,
not a clean matched benchmark comparison.

The shared runtime used for these runs was
`sha256:e04f1825b7e699f0b597f7eaa29aa534d25d1dab21a143e222fb19d5a29ce27a`,
with private Grinta revision `cb61d4c8469bbb9bd8b067498d8b63ba1c0c072d`.
Task toolchain fingerprints and paired controlled fixture checks matched.
Both systems' initial public baselines passed eight tests.

Raw local outputs are under
`artifacts/deepswe-first-paired-2026-10-30/agentless-stream-fixed/` and
`artifacts/deepswe-first-paired-2026-10-30/grinta-stream-fixed/`.
Neither run produced a final prediction or a held-out benchmark score.
The other four pilot tasks were not started.

Next: once subscription-sharing allowance is available, rerun the first task
with the corrected line boundary and a freshly initialized Git index. The task
has been used for development; no claim of unseen-task exposure is made.
