# Agreed small-pilot budget

Youssef revised the token measure on 30 October 2026: use once-only content,
not the sum of input/output usage over repeated requests.

| Setting | Each system, independently for each task |
| --- | --- |
| Model | GPT-6.1 Sol, medium reasoning |
| Connection | ChatGPT-plan subscription |
| Attempt time | 7,200 seconds |
| Content allowance | 1,000,000 once-only content tokens |
| Actual provider usage | Recorded separately, including repeated input |

The first reached limit stops work. Provisioning and the initial public baseline
remain excluded. Model requests, tool execution and candidate validation are
inside the time allowance. Agentless retains one edit-localization sample and
four repair candidates. The first task is a development run; review it before
starting the remaining four pilot tasks.

## What counts once

The counter normalizes messages, function calls/results, system instructions and
tool schemas, then tokenizes their canonical JSON with `tiktoken==0.14.0` and
`o200k_base`. This is a reproducible custom content measure, not a claim to match
OpenAI's model-specific wire-token count, dollar cost or compute consumption.

Replayed input is matched by normalized content and occurrence count. Replaying
history does not add tokens. Two identical messages present twice in history
count as two occurrences, not one. Every newly generated reply is a new occurrence,
even if its text repeats an earlier reply; replaying it afterward does not count
again. Function call IDs distinguish tool calls and results. Dropping history
does not refund previously counted content. Changed messages count as new whole
messages; overlapping source snippets in different prompts are not deduplicated
word by word. In Agentless, repeated identical repair prompts count once, while
each newly generated repair counts.

Visible assistant text and tool arguments count as content. Opaque reasoning
items are excluded from this content ledger; their reported generation tokens
remain included in actual provider usage. The ledger stores hashes and counts,
not raw message text. The initial implementation targets the text/function-call
messages of this pilot, not image/audio token accounting.

## Enforcement and reporting

`AttemptBudget.pilot()` selects this policy in both launchers. Their accounting
modules are byte-identical. The generic constructor retains the older cumulative
mode for historical callers/tests; this does not select the current pilot policy.
Normal Grinta outside the opt-in comparison scope is unchanged.

Before inference, the counter observes the request and stops if its new content
hits the threshold. After completion it observes generated output, reports any
content overshoot, and stops further work. The fixed workflow saves `budget.json`;
Grinta saves its attempt-budget snapshots. Both retain `processed_input_tokens`,
`processed_output_tokens` and `processed_tokens` from provider usage separately
from `used_tokens`, which measures the selected content allowance. The snapshot
includes `token_accounting` and `content_tokenizer`. Missing provider usage still
stops the run rather than silently losing resource reporting.

The two-hour deadline and validation timeout clamping remain enforced. Cleanup
and evidence writing can continue after work stops. No subscription quota or
billing fallback is changed by this local measurement policy.

The machine-readable agreement is
[agreed_contract.json](../experiments/pilots/deepswe_small_v2/agreed_contract.json).
Older runs, snapshots and `budget_verification.json` describe the previous
2,000,000 cumulative-token policy; they are historical evidence and were not
relabelled. Local verification of the new policy used no model calls. End-to-end
live verification of the revised policy remains pending.
