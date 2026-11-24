# Grinta on Koota composite traits with GPT-6.2 Sol

Grinta attempted the DeepSWE composite trait task using GPT-6.2 Sol at xhigh through the ChatGPT subscription. The public baseline passed. The provider accepted 30 model requests and refused the next one because the subscription sharing allowance was exhausted. No patch was exported, so Koota has no Grinta verifier score.

Completed responses accounted for 3,125,694 processed tokens, including repeated context. The runner recorded 313,810 against the two-million-token task budget, including the content of the rejected request. Around 14 minutes of the two-hour task allowance had elapsed when the provider stopped the run.

Agentless-ML's earlier attempt with the same model and reasoning setting passed 35/51 issue tests and 172/172 regression tests. The Grinta launch and error record are under `artifacts/grinta-koota-composite-sol62-2026-11-21/attempt/`.

## Local allowance recovery

The local ChatGPT launcher in `artifacts/grinta-chatgpt-allowance-recovery-2026-11-24/setup/` accepts `--allowance-wait-hours` to opt into recovery and set a total waiting ceiling. The host recognizes a subscription allowance rejection, keeps the pending request and container alive, and waits for the provider's reset hint when present. If no hint is present, it retries the pending request after ten minutes. Both task clocks pause only during those waits, which are recorded separately. Launches without the flag use the original wall-clock rule. Recovery runs are engineering evidence and use different timing from the standard comparison.

An offline reset simulation completed in the same container after a synthetic allowance rejection. A second simulation reached the wait ceiling and preserved an untracked diagnostic file in the saved work-in-progress patch. Neither simulation used ChatGPT allowance or produced a benchmark score. Recovery requires the launcher and Docker container to stay running across the wait. A live allowance reset and recovery across a shutdown have not been verified.
