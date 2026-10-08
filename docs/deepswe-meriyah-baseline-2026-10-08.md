# Meriyah public baseline — 8 October 2026

Meriyah is now ready for a workflow run. This raises the latest DeepSWE survey
count from **92 to 93 ready tasks out of 113**; 20 still need setup attention.
Pwntools is parked at its documented diagnostic stopping point.

## What changed

The old Meriyah attempt failed because repository references retained commits
outside the pinned base history. A fresh preparation with the existing sealing
code succeeded. The seal checks were not relaxed, and no partial clone was
salvaged. The first retry then found that the published image was absent locally;
pulling the pinned image was the only additional setup needed.

The unpatched repository at `d141eb14a40b79c04d1b1db5c20c6afa3844c0d9`
ran its complete public Vitest schedule in image
`sha256:43ce618452b29610b682ea77e384dcb8c57308957a7eb65734a47d76a7ff47dc`.
Vitest reports **137 passing files and 94,471 passing test executions**, with
exit code zero. The accepted JUnit inventory contains **51,497 unique test IDs**,
all passing: the existing report parser merges repeated classname/name IDs
and keeps their worst outcome. These are different counts, not omitted failures.

No source, runner, dependency, image, test exclusions or execution-limit changes
were needed. Held-out tests and solutions were not inspected; no model was called.
This is a public baseline, not a repair result or a benchmark score.

## Reproduce

```powershell
.\.venv\Scripts\python.exe tools/survey_deepswe.py `
  --tasks-root ../benchmarks/deepswe/corpus/tasks `
  --repositories ../benchmarks/deepswe/repos `
  --task-id meriyah-explicit-resource-declarations `
  --rerun --pull `
  --results ../output/deepswe-survey/survey.jsonl `
  --artifacts ../output/deepswe-survey `
  --timeout-seconds 1800
```

Evidence is in
`../output/deepswe-survey/meriyah-explicit-resource-declarations/logs/agentless-ml-0f5cd7af0d954c888274d1ec6b536b2e/`:
the original JUnit report, stdout, empty stderr and execution metadata. The
latest appended survey record is `ready`, with 51,497 passing IDs and no failed
or skipped IDs. The complete retry took 216.7 seconds, including the image pull.

Next, retry Drizzle's repository preparation using the current cleanup code,
then LangChain's fresh staged clone. Neither old failure justifies weakening
the repository verifier.
