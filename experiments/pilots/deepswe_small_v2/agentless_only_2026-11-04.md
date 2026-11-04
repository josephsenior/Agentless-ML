# Agentless-ML only on three DeepSWE tasks

The run list was fixed before inference. Pebble, KaTeX and Meriyah came from the prepared pilot list. The aiomonitor development task was excluded. This was a small engineering pilot for the resource discussion.

All three attempts used Agentless-ML revision `8fe247b2c19afdaca899088e468f7b650ab84590`, DeepSWE revision `0b9fabbb63b9104d678fe965e1632f2dd9eaa2ea`, GPT-6.1 Sol at medium reasoning through the subscription, one edit sample and four repair samples. Each task had a two-hour workflow cap and a one-million once-only content-token cap. Initial baseline and separate scoring are outside the workflow clock.

| Task | Completed model calls | Provider-reported tokens | Outcome |
| --- | ---: | ---: | --- |
| Pebble durability wait APIs | 8 | 514,975 | Resolved. DeepSWE passed 59/59 issue checks and 44/44 regression checks. |
| KaTeX multicolumn array spans | 2 | 36,535 | Stopped at file localization. The returned paths had a task-name prefix, and none matched the source inventory. No patch exported. |
| Meriyah explicit resource declarations | 0 | 0 | The initial regression-selection prompt measured 1,679,982 content tokens and was blocked before submission. No patch exported. |

Pebble used 523,200 once-only content tokens and about 55 minutes on the workflow clock. The selected patch SHA-256 is `4955a12d53a90d34d1d40c6431b58d3f3895e55f769073285f604b59181c3e39`. KaTeX used 37,397 once-only content tokens. Total provider-reported usage was 551,510 tokens across the pilot.

The pilot produced one scored prediction in three attempts. There were no subscription refusals. This establishes one end-to-end solve and identifies two workflow blockers. Three prepared tasks do not establish a benchmark-wide solve rate or a comparison with Grinta. Local raw evidence is under `artifacts/agentless-only-deepswe-2026-11-04`.
