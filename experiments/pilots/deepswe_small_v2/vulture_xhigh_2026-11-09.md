# Vulture persistent analysis cache: fresh Agentless attempt

Task: `vulture-persistent-analysis-cache` (Python). It is next in the existing
SHA-256 ranking after removing completed Narwhals. No prior repair response or
live pilot result for this task was found in the inspected history. Its pinned
image and checkout are available. The saved public baseline passed 295 cases
in about 7.5 seconds; a fresh baseline precedes inference.

The workflow is unchanged: `gpt-6.1-sol`, xhigh reasoning, one edit-localization
sample, four concurrent repair samples, sequential Docker validation, a 2M
once-only content-token cap and a two-hour workflow limit. Five-file localization
and ten-line repair context remain unchanged. No declaration appendix, retrieval
fallback or test-feedback model loop is enabled. Grinta remains paused.

[Selection record](vulture_xhigh_2026-11-09_selection.json).
Local output: `artifacts/agentless-vulture-xhigh-2026-11-09`.
The exported selected prediction will be scored by the pinned DeepSWE verifier.
## Result

DeepSWE reported 24/24 issue checks and 294/295 regression checks passing.
The exported sample zero is unresolved: the existing
`tests.test_config.test_config_merging` regression fails. Passing every issue
check does not override a regression failure in the benchmark's binary score.
The verifier completed normally, and no budget or infrastructure stop occurred.

All eight model responses completed and all four repair patches applied. Each
public validation report contained failures; report counts also include tests
added by candidates. The existing selector considered sample zero at its final
ranking step and exported it. No alternative candidate was scored afterward,
and the selected patch was not manually modified.

Provider-reported usage was 118,387 tokens: 23,091 input and 95,296 output,
including reasoning. The once-only content ledger counted 48,897 tokens. The
recorded workflow took about 13.1 minutes, with the separate verifier completing
shortly afterward. Full attempt timing is retained in the summary.

[Result](vulture_xhigh_2026-11-09/result.json),
[selection and candidate evidence](vulture_xhigh_2026-11-09/summary.json),
[exported patch](vulture_xhigh_2026-11-09/selected.patch), and
[native regression failure](vulture_xhigh_2026-11-09/regression-failure.json).

Next, inspect the configuration-merging failure against the saved patch and
prompts without another model request. The result and workflow stay unchanged.
