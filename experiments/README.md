# Experiment configurations and evidence

This directory holds corpus pins, reviewed development configurations and
compact records of actual runs. Saved model responses and controlled repair
fixtures are development inputs; they are not live-model benchmark results.

The [proposed research protocol](research_protocol_draft.json) is still a draft
and is not enforced by the controller. See
[the configuration guide](../docs/experimental-configuration.md) for the method
differences and decisions that need review before an experiment is frozen.

## Where to look

| Directory | Contents |
| --- | --- |
| `deepswe/` | DeepSWE pins, environment/setup evidence and task-specific records. |
| `swe_bench_pro/` | V1/V2 corpus pins, recorded task inputs, public plans and provisioning evidence. |
| `reproduction/` | Evidence from structured reproduction reporting and real-task replays. |
| `rust/` | Controlled Rust workflow inputs and development fixtures. |

Other configurations are used by the controlled workflows. The
[tools guide](../tools/README.md) identifies their runners.

## Raw outputs and cleanup

Large reports, logs, predictions and workspaces are kept locally under
`artifacts/` or the parent workspace's `output/`, rather than committed here.
Records may refer to those paths and retain SHA-256 hashes. Git ignoring a
file does not mean it is disposable.

Keep raw evidence cited by a record, pinned benchmark inputs, fixture sources
and registered image manifests. Preserve failure and skip outcomes as well as
passes. If raw evidence is archived elsewhere, verify the copy and document
how to restore the cited paths before removing the original.

Python bytecode, pytest caches and linter caches can be regenerated. They can
be cleared after checking that the directory belongs to this checkout and is
not an active workspace. A filename containing `test`, `old` or a date is not
enough to classify a run artifact or script as disposable.

Detailed setup investigations are indexed in
[the development history](../docs/history/README.md). Updating documentation
does not rewrite the outcomes in these evidence records.
