# Boa temporary-workspace retry — 8 October 2026

Boa now has a usable public baseline: **1,609 passing and one failed report
ID**, with no Windows file-lock exception during cleanup. The latest DeepSWE
readiness count is **97/113**, leaving 16 tasks needing attention. No latest
records remain in `survey_error`.

## What the retry establishes

The old record was a Windows `WinError 32` while cleaning a checkout under the
editor-visible output directory. The current survey creates candidate checkouts
under the system temporary directory. This retry completed test execution,
workspace cleanup and survey recording without that exception. No code change,
lock bypass or deletion of an old workspace was needed.

The sealed base remains `70409a5052984325dccfdc5f6520818568a81f39` and the
verified pinned image is
`sha256:9ab97da2ebb88bc71beeb2434d198d4adca6e1abe14f45d52250666249fb7a1e`.
The existing `cargo-nextest` runner compiled and tested the candidate workspace
offline. There was no task-specific override or target filter, and no changed
dependency, image, test expectation or execution limit.

The report contains all 1,610 executed IDs: 1,609 passed and one failed.
Nextest's console also lists one skipped test; it does not appear as a skipped
case in the emitted JUnit inventory. Exit code 100 is the runner's declared
test-failure status, not a missing-report or harness exception.

## Remaining failure

`boa_macros_tests::derive::try_from_js` launches a nested trybuild compilation.
It exhausted the runner's existing 4-GiB temporary filesystem: stderr records
`No space left on device`, compiler-output errors and a linker bus error. The
failure remains in the report and outside the passing regression inventory.
This retry did not increase temporary storage, disable that test or repair
source code. A usable inventory does not mean an all-green suite.

Held-out benchmark tests and solutions were not inspected, and no model was
called. The next setup review can move to Igel's `no_passing_tests` result;
Boa does not need another diagnostic to establish its current inventory.

## Reproduce and evidence

```powershell
.\.venv\Scripts\python.exe tools/survey_deepswe.py `
  --tasks-root ../benchmarks/deepswe/corpus/tasks `
  --repositories ../benchmarks/deepswe/repos `
  --task-id boa-hierarchical-evaluation-cancellation `
  --rerun --pull `
  --results ../output/deepswe-survey/survey.jsonl `
  --artifacts ../output/deepswe-survey --timeout-seconds 1800
```

The JUnit report, stdout, stderr and execution metadata are under
`../output/deepswe-survey/boa-hierarchical-evaluation-cancellation/logs/agentless-ml-c56b11dfe9f547209838ec1ac8f0c7cd/`.
The complete retry took 694.3 seconds; nextest reports 59.487 seconds for test
execution after compilation. The latest appended survey record is `ready`.
