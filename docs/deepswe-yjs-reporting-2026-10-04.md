# Yjs public test reporting — 4 October 2026

Yjs now has a usable public regression inventory: **231 passed, six skipped,
zero failed** at the pinned base revision. The latest DeepSWE survey has **76
ready tasks out of 113**. This checks infrastructure, not task-solving ability;
no model was called.

Follow-up: the [harness review](deepswe-harness-review-2026-10-04.md) records
the next recoveries. The counts here describe the Yjs checkpoint.

## Why an adapter was needed

The tests and runner already exist. The public `tests/index.js` calls
`lib0/testing.runTests`, which prints results but does not write a per-test
report. Validation needs individual outcomes to identify passing baseline tests
and compare candidates. A successful process exit cannot provide that inventory.

The adapter wraps registered functions, records their outcomes, and delegates
to the original `runTests`. Lib0 still owns discovery, order, filtering, test
contexts, random seeds, repetition and failure handling. Genuine skips are
identified by their actual error class, not its name. Tests that the filter
never invokes are skipped, not passed. CTRF is written only after the original
runner completes: import or runner-level errors leave no partial passing report.

The container copies the public entry point alongside the original and changes
only its `runTests` import. If that import no longer matches the reviewed form,
preparation fails for review. The original file stays unchanged, and these
temporary files do not enter the exported repair patch.

Installed dependencies are copied into the candidate directory. Yjs's relative
`node_modules/@y/y` self-link must resolve there; the command checks this before
running. Otherwise a package-name import could silently test the image's old
source instead of the candidate.

## Checks and evidence

The baseline ran offline with the package's `NODE_ENV=development` and
`--repetition-time 50`, reporting 237 tests in 28.4 seconds. The
[snapshot](../experiments/deepswe/yjs_review_2026_10_04.json) records its base
revision, image digest, counts and candidate probe.

A temporary candidate added a source export and imported it through `@y/y` in
a new test. Its expected failure confirms that package-name imports reached
candidate source. Another test failed only on its second repetition, and a
third called lib0's skip function. With the `agentless` filter, both failures
were reported and all other tests stayed skipped. The sealed repository was
not modified.

[Reporter tests](../tests/test_deepswe_yjs.py) also cover asynchronous tests,
non-test helpers, a fake skip error, the narrow entry rewrite, and runner errors
without partial reports. The real-image check is opt-in:

```powershell
$env:AGENTLESS_YJS_REPOSITORY = '<sealed Yjs repository>'
.\.venv\Scripts\python.exe -m pytest tests/test_deepswe_yjs.py -q
```

The full package suite passed with 542 tests and 15 opt-in checks skipped.
The seven Yjs checks, including the real-image probe, passed in a separate run.

The append-only survey and candidate-probe artifacts remain under
`output/deepswe-survey/`, beside this repository. Only public repository tests
and installed dependency source were inspected; benchmark held-out tests and
the reference solution were not read.

## What remains

Yjs was the last `no_runner` task. The remaining 37 tasks comprise 22 unsupported
repositories, five harness errors, four baselines without passing tests, three
repository preparation failures, and one each of missing image, survey error
and timeout. Other task outcomes are unchanged.

Cliffy's incomplete offline Deno cache is unchanged. Next, review the five
harness errors and distinguish missing dependencies from runner problems before
making further changes to the public test schedule.
