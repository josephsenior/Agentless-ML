# First live task: engineering checkpoint, 29 October 2026

Task: `aiomonitor-task-snapshots-diff`. This checkpoint is not a completed
paired comparison or a benchmark score. The other four pilot tasks remain on
hold pending review of this task.

Both systems were configured for GPT-6.1 Sol, medium reasoning, a two-hour
attempt limit and two million combined input/output tokens. Agentless used one
edit-localization sample and four planned repair samples. The initial public
baseline passed all eight tests; it is excluded from the attempt budget.

## Agentless-ML

The original attempt stopped at the response-provider boundary. Its raw first
response and usage were not retained, so its exact response and token count are
unknown. The adapter was corrected to retain completed responses and account
usage before stage validation, including valid empty regression-selection
responses. That correction was committed as `7b052b1`.

Youssef explicitly authorized one labelled engineering retry. It made three
model calls and used **4,951 tokens**, then stopped at symbol localization after
about **47.1 budgeted seconds**. The response listed locations as plain text;
the existing parser requires fenced blocks and therefore obtained no repair
context. It also listed some proposed symbols absent from the base revision.

The Python prompt is deliberately identical to the published Agentless v1.5
prompt. It demonstrates fences but ends with “Return just the locations.” We
have preserved that prompt and the parser. Any format-policy adjustment should
be explicit, rather than silently accepting a new response form.

All three retry requests, responses and reported usage are retained locally.
There was no repair generation, candidate selection, final prediction or hidden
test evaluation. No further Agentless attempt was started.

## Grinta

Startup failures exposed two framework state directories under the read-only
container root. They were addressed using a private-framework state symlink and
supported writable data-directory settings under `/tmp`. The task source,
public tests and container protections were preserved. The stopped framework
error loop and its logs remain separate evidence; these setup attempts used no
model tokens.

The subsequent launch reached the model relay but was rejected before inference:
`relay request differs from agreed model settings`. Local reproduction showed
that the common request sanitizer put `reasoning_effort=medium` inside
`extra_body`, while the subscription adapter only read the top-level field.
The relay correctly refused to send a request without the agreed effort.

Grinta commit `ae9a2f8a7` recovers that setting before converting the request to
Responses format. Ten focused provider/pipe tests and static checks passed,
without inference. The prepared container still contains the earlier private
Grinta revision; this correction needs a refreshed runtime before a later run.
No successful Grinta model request or final patch was produced by these launches.

## Evidence and next boundary

The accompanying JSON records local evidence hashes, usage, image and task
pins. Raw logs and responses remain under the referenced local artifact paths;
they are not committed wholesale.

The common prepared image used for the labelled Agentless retry and the latest
Grinta startup was
`sha256:187fbe4dbd160574f16782cfed1fb2ef04423ae77b925108a1b7679d8df73345`.
Paired model-free runtime checks passed before launch. This does not establish
successful task repair or complete budget enforcement in a long live attempt.

Next: review Agentless's strict output-format behavior and refresh Grinta's
private runtime with the tested settings fix. Preserve the failed attempts when
agreeing on any further live retry. No benchmark readiness counts changed.

## Follow-up: format reviewed, runtime refreshed

The [pinned-source format review](../../../docs/agentless-response-format-review.md)
confirmed that our Python prompt is byte-identical to the reference and that
both block extractors reject the retained unfenced response. The prompt and
parser remain unchanged.

The replacement Aiomonitor image is
`sha256:3c558e3f6d7a50d73c829e9e29ac41179962b2583951d080b6949a1a4cdf7649`.
It contains committed Grinta revision
`ae9a2f8a78f629a932d170affe4d7d3ef836a66f`, including the reasoning-setting fix.
Task toolchain fingerprints and parent layers were verified. Both runners'
controlled fixture checks passed, and an offline request-construction check in
the image preserved `medium` reasoning through the common sanitizer.

The new registry and runtime evidence are under
`artifacts/paired-first-task-runtime-2026-10-29-reasoning-fix/` locally.
Earlier images and failed attempts remain retained. This follow-up does not
authorize or record another live model attempt.
