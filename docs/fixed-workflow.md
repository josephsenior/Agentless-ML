# Recorded fixed workflow

`FixedWorkflowController` connects the first complete Python path: pinned source,
file localization, symbol localization, focused repair context, multiple repair
samples, isolated patch application, public Docker tests, deterministic selection,
and prediction/run export.

The input is `RecordedStageResponses`. It contains one file-localization response,
one symbol-localization response, and an ordered collection of repair responses.
The controller renders and saves the prompts that would have produced them, but
has no model client. Recorded execution therefore reports zero model calls and
zero input/output tokens. It cannot react to validation output or request another
sample.

The file-localization parser accepts only tracked Python paths at the pinned
commit and limits output to five files. Symbol locations must resolve to parsed
program elements or explicit lines. Repair edits can touch only the selected
context intervals. Invalid repair samples are recorded and skipped. Valid patches
receive independent Git workspaces and fresh public-test containers before the
existing selection policy chooses one final patch.

## Provenance and artifacts

Construction requires explicit implementation, benchmark, harness, container,
and recorded-model provenance. The controller verifies the task commit through
the workspace provider, checks the configured image reference, and checks the
resolved immutable image ID when `TaskSpec.container_digest` is present.

Every run receives a unique directory containing:

- all three rendered prompts and the exact recorded responses;
- selected files, parsed locations, authorized intervals, and repair context;
- accepted and rejected candidate attempts;
- per-command Docker evidence nested under the candidate ID;
- deterministic selection evidence;
- the final prediction and `RunRecord`.

If the run stops before prediction export, `failure.json` records the exception
type and message. Such a run has no final prediction. The current format uses
plain JSON and is an internal prototype rather than a versioned interchange format.

This boundary does not load a benchmark dataset, contact a model provider, or run
a hidden verifier. It proves that recorded stage outputs can traverse the complete
fixed controller without gaining access to repository tools or test feedback.

## Controlled demonstration

After pulling `python:3.11-slim`, run the complete controller from the repository
root. It uses three checked-in response patterns: one malformed repair, one valid
patch that fails the public test, and one valid patch that passes and is selected.

```powershell
$env:PYTHONPATH = 'src'
python tools/demo_fixed_workflow.py
```

The summary prints the outcome of each repair, the selected candidate, zero LLM
API calls, and the unique artifact directory. This controlled task verifies the
workflow mechanics; it is not a reported SWE-bench Pro or DeepSWE result.
