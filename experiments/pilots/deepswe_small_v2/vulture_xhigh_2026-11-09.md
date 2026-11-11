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

## Regression inspection: added defaults change the exact dictionary

`test_config_merging` passes CLI options and TOML settings to `make_config`, then
compares the entire result with an exact nine-key dictionary. The native failure
reports those nine original entries as identical. It fails solely because the
patch adds three keys:

```python
"cache": False,
"cache_clear": False,
"cache_dir": ".vulture-cache",
```

The generated patch puts these in `DEFAULTS`. The existing `make_config` loop
copies defaults into missing keys, including when the caller supplied no cache
flags. Thus a no-cache configuration acquires three extra entries. The evidence
does not show CLI values losing precedence over TOML, nor a cache execution error.

The issue expressly requests the three CLI options. The patch implements them
through the existing default/configuration mechanism, but the old equality test
still insists on the previous exact result shape. This is a feature-related
compatibility assertion worth flagging when reviewing benchmark contracts. It
is not sufficient evidence to declare the benchmark invalid or exclude the task;
a representation preserving old no-cache output could conceivably satisfy both,
and no such alternative was evaluated here.

### What the prompts and selection knew

The original `DEFAULTS` dictionary was visible in all repair prompts. The full
`make_config` merge loop appeared in the earlier edit-localization prompt, but
was omitted from the narrower repair context. The exact test body and its
dictionary-equality assertion did not appear in repair. All four patches exposed
the same configuration-test failure in public validation; sample one also failed
`tests.test_script::test_tests`.

Crucially, the regression-selection response had excluded
`tests.test_config::test_config_merging` before repair generation, along with
three other configuration tests. This was an upfront response using the issue
and public test names, not a manual exclusion after seeing the failure. The test
therefore did not count against candidates in workflow selection. DeepSWE's
independent final verifier still includes it in its 295 p2p checks. Workflow
exclusions do not change the benchmark's grading requirements.

The accurate finding is: all 24 issue checks passed, while an exact legacy
configuration-shape assertion prevents a solve under the pinned final scorer.
There is no established Agentless-ML bug here. We retain the unresolved outcome
and flag the compatibility question in the evidence. No generated code, test,
workflow or benchmark rule was changed, and no rerun was performed.

[Prompt checks, exact diff and pre-repair exclusion evidence](vulture_xhigh_2026-11-09/failure-analysis.json).

## Reference patch check on 11 November 2026

The pinned DeepSWE reference patch passed `test_config_merging` in the same
verifier and image used for the Agentless prediction. The native report records
the named check as passed. The reference passed all 24 issue checks and all
295 regression checks, earning a reward of 1. This confirms that the cache
feature and the existing configuration check can both pass under this verifier.

The Agentless prediction remains unresolved with 24/24 issue checks and
294/295 regression checks. Keep the pinned benchmark for this comparison.

Reference patch SHA-256: `77c66982cfd975463308c104d07eef99543c5868337ca193ff556e2c15ecc940`.
Local verifier evidence: `artifacts/vulture-reference-2026-11-11/vulture-persistent-analysis-cache/agentless-ml-verifier-ca0c9551fe5f4db096e9daffa1fdb380`.
