# Dasel HTML format: one fresh Agentless attempt

Selected task: `dasel-html-document-format` (Go). This is an Agentless-only
development attempt. Grinta is not running.

Selection used the same short-baseline eligibility idea as the earlier five-task
pilot: passing saved public baseline taking at most 120 seconds, local pinned
image and checkout, and no known prior repair exposure. Eligible task IDs were
sorted by SHA-256 of `agentless-fresh-xhigh-2026-11-09:<task_id>`. Dasel ranked first.
Its saved public baseline passed 1,012 cases in about 41 seconds. The workflow
runs a fresh public baseline before inference. This practical selection does not
establish a representative benchmark sample.

Settings: `gpt-6.1-sol`, xhigh reasoning, one edit-localization sample, four repair
samples generated concurrently, sequential Docker validation, a 2M once-only
content-token cap and a two-hour workflow limit. Scoring uses DeepSWE's separate
verifier after prediction export. No held-out test content is supplied to the
workflow. The attempt output is
`artifacts/agentless-dasel-xhigh-2026-11-09`.

[Selection record](dasel_xhigh_2026-11-09_selection.json).
Results will be added after this single attempt finishes.
