# First-task development fixes

These were development runs on `aiomonitor-task-snapshots-diff`, not official
benchmark results. Their failed-run folders were deleted on 30 October 2026 at
Youssef's request. The tracked checkpoint JSON remains a historical summary;
its raw-run paths and hashes no longer point to retained files.

The fixes were:

- Accept a valid empty regression-selection response, and retain/account a
  completed response before checking its stage-specific contents (`7b052b1`).
- Put Grinta framework state and streaming checkpoints in supported writable
  locations inside the disposable container.
- Recover medium reasoning after the common request sanitizer moves the setting
  into `extra_body` (`ae9a2f8a7`).
- Explicitly request a fenced Python symbol-localization response (`aeec64e`).
  This clarifies an ambiguity inherited from pinned Agentless; parsing is unchanged.
- Preserve Agentless text from finalized output-item and text events before
  accepting stream completion (`c05f533`). Previously the worker inspected only
  the terminal response body. Empty regression-selection answers remain valid;
  interrupted or failed streams remain rejected.
- Use Grinta's actual response-ID property in its asynchronous streaming adapter,
  and preserve finalized output items in the host relay (`cb61d4c84`). The missing
  property previously stopped tool delivery and caused repeated controller errors.

The [format review](../../../docs/agentless-response-format-review.md) explains
that last change. Verified runtime/setup evidence and the prepared Docker images
were preserved, including image
`sha256:3c558e3f6d7a50d73c829e9e29ac41179962b2583951d080b6949a1a4cdf7649`.

No successful paired repair or benchmark score came from these development runs.
The task has been used during development and should not be described as unseen.
No new model run was started during cleanup.
