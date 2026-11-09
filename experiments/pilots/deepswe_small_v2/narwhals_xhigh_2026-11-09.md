# Narwhals rolling windows: fresh Agentless attempt

Selected task: `narwhals-rolling-window-suite` (Python), with no known prior
repair attempt in the inspected local model-call history and pilot reports.
This is an Agentless-only development attempt; Grinta remains paused.

The previous deterministic ranking is reused, excluding completed Dasel and
Aiomonitor's documented October development exposure. Narwhals is next. The
saved public baseline passed 10,093 cases, with 1,699 skips, in about 106 seconds.
A fresh baseline precedes model calls. This short-baseline selection is a
practical development choice, not a representative benchmark sample.

Settings remain Sol (`gpt-6.1-sol`), xhigh reasoning, one edit-localization
sample, four concurrent repair samples, sequential Docker validation, 2M
once-only content tokens and a two-hour workflow cap. The ten-line repair context
is unchanged. No interface appendix, context fallback or feedback loop is enabled.
The exported selected patch is scored separately by the pinned DeepSWE verifier.

[Selection record](narwhals_xhigh_2026-11-09_selection.json).
Local output: `artifacts/agentless-narwhals-xhigh-2026-11-09`.
Results will be recorded after this single attempt.
