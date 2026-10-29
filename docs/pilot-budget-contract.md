# Agreed small-pilot budget

The user agreed to these limits for the initial DeepSWE comparison:

| Setting | Both systems, for each task independently |
| --- | --- |
| Model | GPT-6.1 Sol |
| Reasoning | Medium |
| Connection | ChatGPT-plan subscription |
| Attempt time | 2 hours (7,200 seconds) |
| Token threshold | 2,000,000 combined input and output tokens |

The first reached limit stops the run. Finishing early ends it immediately.
Model requests, tool execution and candidate validation count toward the attempt.
Provisioning and the initial public baseline happen beforehand and are excluded.
Repeated input/history counts whenever the provider reports it as input usage.
Reasoning tokens included in output usage must not be counted twice.
An already-started response may cross the token threshold; retain its actual usage
and report the overshoot.

Agentless-ML uses one edit-localization sample and four repair candidates. These
are the initial pilot settings; first run one task with both systems, inspect
actual usage and limits, then review the configuration before the other four.

The machine-readable source is
[agreed_contract.json](../experiments/pilots/deepswe_small_v2/agreed_contract.json).
This agreement does not make the current launchers enforce aggregate limits.
That implementation and its paired verification are the next step. No pilot has
been started by recording this contract, and historical preparation bundles keep
their original configuration and checksums.
