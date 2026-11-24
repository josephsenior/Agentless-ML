# Grinta on ts-pattern with GPT-6 Astra via SpookAPI

The public baseline passed on both launches. Grinta used GPT-6 Astra at xhigh with the usual two-hour task cap and two-million-token budget. A run-specific host relay sent Chat Completions requests to SpookAPI while the task container stayed offline. The gateway returned no cache-read or cache-write counts in either run.

The first launch received five responses and stopped on HTTP 524. The streaming launch received 11 responses and recorded 263,178 processed tokens. The twelfth request failed to deliver a complete response for about ten minutes, so the operator stopped the run. Neither launch exported a patch. DeepSWE has no Astra score for this task.

Local evidence and relay sources are under `artifacts/grinta-ts-pattern-spook-astra-2026-11-24/`. The two launches are in `attempt/` and `streaming-attempt/`.
