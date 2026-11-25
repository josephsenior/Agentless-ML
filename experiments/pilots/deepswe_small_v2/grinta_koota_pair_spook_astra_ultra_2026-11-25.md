# Grinta on Koota pair relation tracking with Astra and requested ultra effort

SpookAPI accepted a short GPT-6 Astra request with `reasoning_effort=ultra`. The local Grinta image and relay then used that value for the Koota run. The gateway identified the model as GPT-6 Astra and provided no confirmation of the effective upstream reasoning effort. The pinned task image, native verification guidance, two-hour task cap, and two-million-token budget matched the xhigh run.

| Requested effort | Export | Issue tests | Regression tests | Processed tokens |
|---|---|---:|---:|---:|
| xhigh | One-file patch | 0/38 | 172/172 | 240,384 |
| ultra | Empty patch | 0/38 | 172/172 | 347,678 |

The public baseline passed. Grinta completed 17 model requests and used 42,100 once-only budget tokens in about four and a half minutes. Its final answer said pair-level tracking was already implemented. It exported an empty patch. The unchanged checkout was scored with the official verifier and returned reward 0 on corpus revision `0b9fabbb63b9104d678fe965e1632f2dd9eaa2ea`.

Local evidence is under `artifacts/grinta-koota-pair-spook-astra-ultra-2026-11-25/`, with the verifier result under `empty-score/`. See the [xhigh run](grinta_koota_pair_spook_astra_2026-11-25.md) for the earlier patch and trajectory outcome.

A fresh attempt used Grinta prompt revision `128c29f62a5cb586f42c5c63d4ae6d8850f021cf` with the same task and requested ultra setting. The prepared image contained the new guidance. The public baseline passed, and Spook returned 21 completed responses totaling 569,665 processed tokens. On request 22 the host relay raised `SpookAPI did not return a complete model turn`. That error covers empty output and two terminal reasons (length and content filtering). The log does not identify which occurred. The run ended after about 8 minutes 37 seconds with no saved patch or trajectory and no verifier score. The effect of the guidance is undetermined. Evidence is in `artifacts/grinta-koota-pair-spook-astra-ultra-2026-11-25-guidance/`.
