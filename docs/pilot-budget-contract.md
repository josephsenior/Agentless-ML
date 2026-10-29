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
Use `--pilot-budget` on the live shared-task launcher, together with
`--edit-samples 1 --repair-samples 4`, to enable enforcement. Grinta's prepared-
workspace launcher also accepts `--pilot-budget`, with
`--model chatgpt-plan/gpt-6.1-sol --reasoning-effort medium`. Normal defaults
are unchanged. Both use the same accounting implementation.

Agentless checks before requests and validation work, charges reported usage
before accepting a response, and caps model subprocess and Docker command
timeouts at the remaining allowance. It saves `budget.json`. Grinta checks model
and tool boundaries, charges completed provider usage once, and cancels the
running attempt at its deadline; its manifest retains `attempt_budget` and
`budget_exhausted`. Missing usage stops further work. No new response is
requested after the threshold, including when an in-flight response overshoots.

Budget exhaustion terminates the attempt rather than exporting a new prediction
from a partially completed workflow. Cleanup and writing diagnostic evidence may
continue after the work deadline. This is cooperative cancellation of the Grinta
controller; it is not an independent OS kill switch for arbitrary detached child
processes. The deadline tests verify cancellation and cleanup on controlled async
operations, not a real two-hour benchmark run.

Focused local tests cover matching thresholds, overshoot, initial-baseline
exclusion, unavailable usage, candidate timeout clamping, provider accounting and
deadline cancellation. No pilot was started. Grinta's shared-record launcher
still deliberately blocks live execution until the paired container launch path
is integrated; the budget flag does not bypass that gate. Historical preparation
bundles keep their original configuration and checksums.
