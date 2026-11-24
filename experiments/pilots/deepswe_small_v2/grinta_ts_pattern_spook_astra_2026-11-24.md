# Grinta on ts-pattern with GPT-6 Astra via SpookAPI

The public baseline passed on both launches. Grinta used GPT-6 Astra at xhigh with the usual two-hour task cap and two-million-token budget. A run-specific host relay sent Chat Completions requests to SpookAPI while the task container stayed offline. The gateway returned no cache-read or cache-write counts in either run.

The first launch received five responses and stopped on HTTP 524. The streaming launch received 11 responses and recorded 263,178 processed tokens. The twelfth request failed to deliver a complete response for about ten minutes, so the operator stopped the run. Neither launch exported a patch. DeepSWE has no Astra score for this task.

Local evidence and relay sources are under `artifacts/grinta-ts-pattern-spook-astra-2026-11-24/`. The two launches are in `attempt/` and `streaming-attempt/`.

A fresh streaming retry with the same settings passed the public baseline and received an error event from SpookAPI on its first model request. The relay reported the event without retaining the provider's detailed error. The runner exited on its own after about 35 seconds of inference time, with zero completed responses and no patch to score. Evidence is under `streaming-retry/`.

The local streaming relay now records the HTTP status and any provider error code, type, and message in `agent.log` and the run result. It redacts the API key and authorization values and caps the saved message length. This change applies to future requests. The details of the earlier error were not retained.

The retry under `error-logging-retry/` passed the public baseline and completed two model responses, with 30,569 processed tokens. Spook returned HTTP 429 on the third request with code `upstream_http_429` and message `Upstream rate limited the request`. The runner exited on its own without exporting a patch. The provider error does not specify the scope or duration of the rate limit.

An earlier Spook streaming relay retried connection failures, incomplete streams, timeouts, HTTP 502/503/504/524, and recognized temporary rate limits itself. The new launcher under `setup-native-retry/` replaces that retry loop with a structured error response. The container client turns it into Grinta's native provider exceptions. Grinta applies its existing exponential backoff and retry limits, including `Retry-After`, inside the existing task budget. The relay still owns the key and buffers model output until a complete response arrives. Tokens that the provider processed without reporting usage are unavailable to local accounting and may still be billed.

The launcher attempts to save the worktree diff and any available trajectory and manifest under `interrupted/` on a failed launch before removing the container. These files are diagnostic artifacts. A subsequent launch still starts a new Grinta session.

The offline `native-retry-simulation/` passed the pinned public baseline, received a simulated read timeout followed by an upstream 429 with `Retry-After`, and reached two successful simulated responses in the same container. Grinta recorded `AgentState.FINISHED` and exited normally. The simulation made no paid inference requests and its output was not scored. The native retry launcher and derived image are local to this workspace.
